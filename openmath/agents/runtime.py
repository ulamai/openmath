from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from openmath.memory.sessions import (
    add_message,
    get_provider_thread,
    get_session,
    provider_thread_storage_key,
    update_message,
    upsert_provider_thread,
)
from openmath.workspace.project import ProjectRecord, slugify

from .engines import get_chat_engine
from .providers import list_chat_providers, validate_effort, validate_model

_RUN_LOCK = threading.RLock()
_RUN_THREADS: dict[str, threading.Thread] = {}
_RUN_STOP_REQUESTS: set[str] = set()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _run_dir(project: ProjectRecord, run_id: str) -> Path:
    return project.workspace / "runs" / run_id


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    _write_json(path, payload)


def _update_manifest(path: Path, **changes: Any) -> dict[str, Any]:
    with _RUN_LOCK:
        manifest = _read_manifest(path)
        manifest.update(changes)
        _write_manifest(path, manifest)
    return manifest


def _build_run_id(provider_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{stamp}-{slugify(provider_id)}-{os.getpid()}-{suffix}"


def _normalize_run_mode(mode: str | None) -> str:
    normalized = str(mode or "once").strip().lower()
    aliases = {
        "single": "once",
        "once": "once",
        "auto": "autoresearch",
        "loop": "autoresearch",
        "autoresearch": "autoresearch",
    }
    resolved = aliases.get(normalized)
    if resolved is None:
        raise ValueError("Unsupported run mode.")
    return resolved


def _normalize_max_iterations(run_mode: str, raw_value: Any) -> int:
    if run_mode == "once":
        return 1
    if raw_value in (None, "", 0):
        return 12
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError("Loop count must be an integer.") from error
    if value < 2 or value > 500:
        raise ValueError("Loop count must be between 2 and 500.")
    return value


def _normalize_max_minutes(run_mode: str, raw_value: Any) -> int:
    if run_mode == "once":
        return 30
    if raw_value in (None, "", 0):
        return 240
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError("Time budget must be an integer number of minutes.") from error
    if value < 10 or value > 24 * 60:
        raise ValueError("Time budget must be between 10 and 1440 minutes.")
    return value


def _loop_summary(run_mode: str, *, iteration_count: int, max_iterations: int) -> str:
    if run_mode != "autoresearch":
        return "Single turn"
    return f"Loop {iteration_count}/{max_iterations}"


def _stop_requested(run_id: str) -> bool:
    with _RUN_LOCK:
        return run_id in _RUN_STOP_REQUESTS


def _mark_stop_requested(run_id: str) -> None:
    with _RUN_LOCK:
        _RUN_STOP_REQUESTS.add(run_id)


def _clear_stop_requested(run_id: str) -> None:
    with _RUN_LOCK:
        _RUN_STOP_REQUESTS.discard(run_id)


def _append_log(path: Path, heading: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{heading}]\n")
        handle.write(content)
        if not content.endswith("\n"):
            handle.write("\n")


def _recent_transcript(
    session: dict[str, Any],
    *,
    limit: int = 8,
    exclude_message_ids: set[str] | None = None,
) -> str:
    selected: list[str] = []
    excluded = exclude_message_ids or set()
    for message in session.get("messages", [])[-limit:]:
        if str(message.get("id") or "") in excluded:
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        role = str(message.get("role") or "note").upper()
        provider = str(message.get("provider_label") or "")
        meta = f" ({provider})" if provider else ""
        selected.append(f"{role}{meta}: {content}")
    return "\n\n".join(selected)


def _engine_profile(engine: dict[str, Any]) -> str:
    engine_id = str(engine.get("id") or "none")
    if engine_id == "ulam":
        return (
            "Work like a math formalization engine. Decompose the problem into precise claims, "
            "surface missing hypotheses, suggest Lean-relevant lemma searches, and keep explicit "
            "proof obligations and verification steps in view."
        )
    if engine_id == "aristotle":
        return (
            "Work like an autonomous proof engine. Organize the task into proof jobs, likely tactics, "
            "artifact checkpoints, and exact next actions that can be verified or delegated."
        )
    if engine_id == "lean4_skills":
        return (
            "Stay close to Lean 4. Prefer small checkable steps, realistic tactic scripts, exact theorem "
            "shapes, and concrete lake or lean commands when they help."
        )
    return ""


def _agent_identity_label(provider: dict[str, Any], engine: dict[str, Any]) -> str:
    provider_label = str(provider["label"])
    if str(engine.get("id") or "none") == "none":
        return provider_label
    return f"{engine['label']} + {provider_label}"


def _build_agent_prompt(
    project: ProjectRecord,
    session: dict[str, Any],
    *,
    prompt: str,
    engine: dict[str, Any],
    provider_label: str,
    effort: str,
    exclude_message_ids: set[str] | None = None,
) -> str:
    transcript = _recent_transcript(session, exclude_message_ids=exclude_message_ids)
    thread_title = str(session.get("title") or "Untitled chat")
    engine_label = str(engine.get("label") or "None")
    engine_profile = _engine_profile(engine)
    engine_block = f"Engine instructions: {engine_profile}\n" if engine_profile else ""
    return (
        f"You are {provider_label} running inside OpenMath.\n"
        f"Engine: {engine_label}\n"
        f"Project: {project.name}\n"
        f"Project root: {project.root}\n"
        f"Objective: {project.objective}\n"
        f"Chat thread: {thread_title}\n"
        f"Requested reasoning effort: {effort}\n"
        "Mode: answer in a normal chat style, but use project context and files when useful. "
        "Do not edit files unless the user explicitly asks for code changes.\n\n"
        f"{engine_block}"
        "Recent conversation:\n"
        f"{transcript or 'No prior messages.'}\n\n"
        "Current user request:\n"
        f"{prompt}"
    )


def _build_loop_iteration_prompt(
    project: ProjectRecord,
    session: dict[str, Any],
    *,
    prompt: str,
    engine: dict[str, Any],
    provider_label: str,
    effort: str,
    run_mode: str,
    iteration: int,
    max_iterations: int,
    max_minutes: int,
    previous_result: str,
    continuation_mode: str,
    exclude_message_ids: set[str] | None = None,
) -> str:
    if run_mode != "autoresearch":
        if continuation_mode == "native_resume":
            return prompt
        return _build_agent_prompt(
            project,
            session,
            prompt=prompt,
            engine=engine,
            provider_label=provider_label,
            effort=effort,
            exclude_message_ids=exclude_message_ids,
        )

    loop_brief = (
        f"Research goal:\n{prompt}\n\n"
        "Autoresearch mode: continue iterating until the loop budget or time budget is hit.\n"
        f"Current loop: {iteration} of up to {max_iterations}.\n"
        f"Total time budget: {max_minutes} minutes.\n"
        "Do not end the run early. Even if you think the main answer is already known, "
        "use the remaining turns to verify claims, find stronger evidence, check edge cases, "
        "or expand the result in useful directions.\n"
        "Each turn should make concrete progress instead of restating prior context."
    )
    if previous_result.strip():
        loop_brief = f"{loop_brief}\n\nPrevious loop result:\n{previous_result.strip()[:1200]}"

    if continuation_mode == "native_resume":
        return loop_brief

    return _build_agent_prompt(
        project,
        session,
        prompt=loop_brief,
        engine=engine,
        provider_label=provider_label,
        effort=effort,
        exclude_message_ids=exclude_message_ids,
    )


def _extract_codex_thread_id(stdout_text: str) -> str | None:
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = str(payload.get("type") or "")
        if event_type in {"thread.started", "thread.resumed"}:
            thread_id = payload.get("thread_id") or payload.get("session_id")
            if isinstance(thread_id, str) and thread_id:
                return thread_id
    return None


def _parse_claude(stdout_text: str, stderr_text: str) -> tuple[bool, str]:
    payload = stdout_text.strip() or stderr_text.strip()
    if not payload:
        return False, "Claude Code returned no output."
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return False, payload
    result = str(parsed.get("result") or payload)
    return (not bool(parsed.get("is_error"))), result


def _unwrap_error_message(payload: Any) -> str | None:
    candidate = payload
    if isinstance(candidate, str):
        text = candidate.strip()
        if not text:
            return None
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return text
        return _unwrap_error_message(decoded)

    if isinstance(candidate, dict):
        nested_error = candidate.get("error")
        if nested_error is not None:
            nested_message = _unwrap_error_message(nested_error)
            if nested_message:
                return nested_message
        message = candidate.get("message")
        if isinstance(message, str) and message.strip():
            nested_message = _unwrap_error_message(message)
            if nested_message:
                return nested_message
        for key in ("detail", "title"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_codex_error(stdout_text: str, stderr_text: str) -> str | None:
    for channel in (stdout_text, stderr_text):
        for raw_line in channel.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = str(payload.get("type") or "")
            if event_type == "error":
                return _unwrap_error_message(payload) or _unwrap_error_message(payload.get("message"))
            if event_type == "turn.failed":
                return _unwrap_error_message(payload.get("error")) or _unwrap_error_message(payload)
    fallback = stderr_text.strip()
    return fallback or None


def _parse_codex(run_directory: Path, stdout_text: str, stderr_text: str) -> tuple[bool, str]:
    final_message_path = run_directory / "assistant-last-message.txt"
    if final_message_path.exists():
        text = final_message_path.read_text(encoding="utf-8").strip()
        if text:
            return True, text
    parsed_error = _extract_codex_error(stdout_text, stderr_text)
    if parsed_error:
        return False, parsed_error
    fallback = stdout_text.strip() or stderr_text.strip()
    if fallback:
        return False, fallback
    return False, "Codex returned no output."


def _parse_gemini(stdout_text: str, stderr_text: str) -> tuple[bool, str]:
    text = stdout_text.strip() or stderr_text.strip()
    if text:
        return True, text
    return False, "Gemini CLI returned no output."


def _run_ollama(
    provider: dict[str, Any],
    *,
    prompt: str,
    model: str,
) -> tuple[bool, str, str, str, int, str | None]:
    base_url = str(provider.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
    request = urllib_request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=120) as response:
            stdout_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as error:
        stderr_text = error.read().decode("utf-8", errors="replace")
        return False, stderr_text.strip() or str(error), "", stderr_text, error.code, None
    except (OSError, urllib_error.URLError) as error:
        stderr_text = str(error)
        return False, stderr_text, "", stderr_text, 1, None

    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False, stdout_text.strip() or "Ollama returned invalid JSON.", stdout_text, "", 1, None

    result = str(payload.get("response") or "").strip()
    if result:
        return True, result, stdout_text, "", 0, None
    return False, "Ollama returned no output.", stdout_text, "", 0, None


def _build_command(
    provider: dict[str, Any],
    *,
    project: ProjectRecord,
    prompt: str,
    model: str,
    effort: str,
    run_directory: Path,
    continuation_mode: str,
    provider_session_id: str | None,
) -> list[str]:
    provider_id = str(provider["id"])
    if provider_id == "codex_cli":
        if continuation_mode == "native_resume" and provider_session_id:
            return [
                "codex",
                "exec",
                "resume",
                "--skip-git-repo-check",
                "--model",
                model,
                "-c",
                f'model_reasoning_effort="{effort}"',
                "--output-last-message",
                str(run_directory / "assistant-last-message.txt"),
                "--json",
                provider_session_id,
                prompt,
            ]
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-C",
            str(project.root),
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            "--output-last-message",
            str(run_directory / "assistant-last-message.txt"),
            "--json",
        ]
        command.append(prompt)
        return command

    if provider_id == "claude_cli":
        command = [
            "claude",
            "-p",
            prompt,
        ]
        if continuation_mode == "native_resume" and provider_session_id:
            command.extend(["-r", provider_session_id])
        elif continuation_mode == "native_init" and provider_session_id:
            command.extend(["--session-id", provider_session_id])
        command.extend(
            [
                "--model",
                model,
                "--effort",
                effort,
                "--permission-mode",
                "plan",
                "--output-format",
                "json",
            ],
        )
        return command

    if provider_id == "gemini_cli":
        return [
            "gemini",
            "-p",
            prompt,
            "-m",
            model,
        ]

    if provider_id == "ollama":
        return [
            "ollama",
            "run",
            model,
            prompt,
        ]

    raise ValueError(f"Unsupported provider: {provider_id}")


def _run_process(
    provider: dict[str, Any],
    *,
    project: ProjectRecord,
    prompt: str,
    model: str,
    effort: str,
    run_directory: Path,
    continuation_mode: str,
    provider_session_id: str | None,
) -> tuple[bool, str, str, str, int, str | None]:
    if provider["id"] == "ollama":
        return _run_ollama(provider, prompt=prompt, model=model)

    command = _build_command(
        provider,
        project=project,
        prompt=prompt,
        model=model,
        effort=effort,
        run_directory=run_directory,
        continuation_mode=continuation_mode,
        provider_session_id=provider_session_id,
    )
    completed = subprocess.run(
        command,
        cwd=project.root,
        check=False,
        capture_output=True,
        text=True,
    )
    stdout_text = completed.stdout or ""
    stderr_text = completed.stderr or ""

    if provider["id"] == "codex_cli":
        ok, result = _parse_codex(run_directory, stdout_text, stderr_text)
        resolved_session_id = provider_session_id or _extract_codex_thread_id(stdout_text)
    elif provider["id"] == "claude_cli":
        ok, result = _parse_claude(stdout_text, stderr_text)
        resolved_session_id = provider_session_id
    elif provider["id"] == "gemini_cli":
        ok, result = _parse_gemini(stdout_text, stderr_text)
        resolved_session_id = provider_session_id
    else:
        ok, result = False, "Unsupported provider."
        resolved_session_id = provider_session_id

    return (
        ok and completed.returncode == 0,
        result,
        stdout_text,
        stderr_text,
        completed.returncode,
        resolved_session_id,
    )


def _resolve_execution_plan(
    session: dict[str, Any],
    provider: dict[str, Any],
    *,
    engine_id: str,
) -> dict[str, Any]:
    provider_id = str(provider["id"])
    provider_threads = session.get("provider_threads") or {}
    existing_thread = provider_threads.get(provider_thread_storage_key(provider_id, engine_id))
    if not isinstance(existing_thread, dict):
        existing_thread = None

    strategy = str(provider.get("session_strategy") or "transcript_replay")
    native_continuation = bool(provider.get("native_continuation"))

    if not native_continuation:
        return {
            "continuation_mode": "transcript_replay",
            "provider_session_id": None,
            "reserve_provider_thread": False,
            "thread_state": None,
        }

    if existing_thread and existing_thread.get("active_run_id"):
        return {
            "continuation_mode": "transcript_replay",
            "provider_session_id": None,
            "reserve_provider_thread": False,
            "thread_state": existing_thread,
        }

    if strategy == "assigned_session_id":
        provider_session_id = str(existing_thread.get("native_session_id") or uuid4())
        return {
            "continuation_mode": "native_resume" if existing_thread else "native_init",
            "provider_session_id": provider_session_id,
            "reserve_provider_thread": True,
            "thread_state": existing_thread,
        }

    if strategy == "capture_thread_id":
        provider_session_id = None
        continuation_mode = "native_init"
        if existing_thread and existing_thread.get("native_session_id"):
            provider_session_id = str(existing_thread["native_session_id"])
            continuation_mode = "native_resume"
        return {
            "continuation_mode": continuation_mode,
            "provider_session_id": provider_session_id,
            "reserve_provider_thread": True,
            "thread_state": existing_thread,
        }

    return {
        "continuation_mode": "transcript_replay",
        "provider_session_id": None,
        "reserve_provider_thread": False,
        "thread_state": existing_thread,
    }


def _stage_provider_thread(
    project: ProjectRecord,
    *,
    session_id: str,
    engine: dict[str, Any],
    provider: dict[str, Any],
    run_id: str,
    model: str,
    effort: str,
    provider_session_id: str | None,
) -> None:
    upsert_provider_thread(
        project,
        session_id,
        str(provider["id"]),
        engine_id=str(engine.get("id") or "none"),
        engine_label=str(engine.get("label") or "None"),
        provider_label=str(provider["label"]),
        native_session_id=provider_session_id,
        active_run_id=run_id,
        last_run_id=run_id,
        last_model=model,
        last_effort=effort,
        mode="native",
        session_strategy=str(provider.get("session_strategy") or "transcript_replay"),
        continuation_ready=bool(provider_session_id),
    )


def _finalize_provider_thread(
    project: ProjectRecord,
    *,
    session_id: str,
    engine: dict[str, Any],
    provider: dict[str, Any],
    run_id: str,
    model: str,
    effort: str,
    provider_session_id: str | None,
    final_status: str,
) -> None:
    existing = get_provider_thread(
        project,
        session_id,
        str(provider["id"]),
        engine_id=str(engine.get("id") or "none"),
    )
    if existing is None or existing.get("active_run_id") != run_id:
        return

    upsert_provider_thread(
        project,
        session_id,
        str(provider["id"]),
        engine_id=str(engine.get("id") or "none"),
        engine_label=str(engine.get("label") or "None"),
        provider_label=str(provider["label"]),
        native_session_id=provider_session_id or existing.get("native_session_id"),
        active_run_id=None,
        last_run_id=run_id,
        last_model=model,
        last_effort=effort,
        last_status=final_status,
        mode="native",
        session_strategy=str(provider.get("session_strategy") or existing.get("session_strategy") or "transcript_replay"),
        continuation_ready=bool(provider_session_id or existing.get("native_session_id")),
    )


def _execute_agent_run(
    project: ProjectRecord,
    *,
    session_id: str,
    engine: dict[str, Any],
    provider: dict[str, Any],
    model: str,
    effort: str,
    prompt: str,
    run_id: str,
    user_message_id: str,
    assistant_message_id: str,
    continuation_mode: str,
    provider_session_id: str | None,
    run_mode: str,
    max_iterations: int,
    max_minutes: int,
) -> None:
    run_directory = _run_dir(project, run_id)
    manifest_path = run_directory / "manifest.json"
    events_path = run_directory / "events.jsonl"
    stdout_path = run_directory / "stdout.log"
    stderr_path = run_directory / "stderr.log"

    started_at = datetime.now(UTC)
    iteration_mode = continuation_mode
    iteration_provider_session_id = provider_session_id
    resolved_provider_session_id = provider_session_id
    final_status = "finished"
    final_summary = ""
    result_text = ""
    last_return_code = 0
    iteration_count = 0
    latest_assistant_message_id = assistant_message_id

    try:
        agent_label = _agent_identity_label(provider, engine)
        _update_manifest(
            manifest_path,
            status="running",
            started_at=_now_iso(),
            summary=f"Running {agent_label} with {model}.",
            iteration_count=0,
            current_iteration=1,
            last_activity_at=_now_iso(),
        )
        _append_event(
            events_path,
            {
                "timestamp": _now_iso(),
                "event": "agent.run.started",
                "engine": engine["id"],
                "engine_label": engine["label"],
                "provider": provider["id"],
                "model": model,
                "effort": effort,
                "run_mode": run_mode,
                "max_iterations": max_iterations,
                "max_minutes": max_minutes,
                "continuation_mode": continuation_mode,
                "provider_session_id": provider_session_id,
            },
        )

        for iteration in range(1, max_iterations + 1):
            if _stop_requested(run_id):
                final_status = "stopped"
                final_summary = f"Stopped {agent_label} after {iteration_count} loops."
                if not result_text:
                    result_text = "Run stopped before the next loop started."
                break

            if iteration > 1 and datetime.now(UTC) >= started_at + timedelta(minutes=max_minutes):
                final_status = "finished"
                final_summary = f"Completed {agent_label} autoresearch budget after {iteration_count} loops."
                break

            session = get_session(project, session_id)
            if session is None:
                final_status = "failed"
                final_summary = "Session disappeared before the agent run started."
                result_text = final_summary
                last_return_code = 1
                break

            if iteration > 1:
                _assistant_session, loop_message = add_message(
                    project,
                    session_id,
                    role="assistant",
                    content="",
                    source="agent-runner",
                    engine=str(engine["id"]),
                    engine_label=str(engine["label"]),
                    provider=provider["id"],
                    provider_label=str(provider["label"]),
                    model=model,
                    effort=effort,
                    status="running",
                    run_id=run_id,
                    title=f"{agent_label} loop {iteration}",
                    continuation_mode=iteration_mode,
                    loop_iteration=iteration,
                    run_mode=run_mode,
                )
                latest_assistant_message_id = loop_message["id"]

            _update_manifest(
                manifest_path,
                status="running",
                current_iteration=iteration,
                last_activity_at=_now_iso(),
                summary=(
                    f"Running {agent_label} {_loop_summary(run_mode, iteration_count=iteration, max_iterations=max_iterations).lower()}."
                ),
            )
            _append_event(
                events_path,
                {
                    "timestamp": _now_iso(),
                    "event": "agent.run.iteration.started",
                    "engine": engine["id"],
                    "engine_label": engine["label"],
                    "provider": provider["id"],
                    "model": model,
                    "effort": effort,
                    "run_mode": run_mode,
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "max_minutes": max_minutes,
                    "continuation_mode": iteration_mode,
                    "provider_session_id": iteration_provider_session_id,
                },
            )

            built_prompt = _build_loop_iteration_prompt(
                project,
                session,
                prompt=prompt,
                engine=engine,
                provider_label=agent_label,
                effort=effort,
                run_mode=run_mode,
                iteration=iteration,
                max_iterations=max_iterations,
                max_minutes=max_minutes,
                previous_result=result_text,
                continuation_mode=iteration_mode,
                exclude_message_ids={user_message_id},
            )
            try:
                (
                    success,
                    iteration_result,
                    stdout_text,
                    stderr_text,
                    return_code,
                    resolved_provider_session_id,
                ) = _run_process(
                    provider,
                    project=project,
                    prompt=built_prompt,
                    model=model,
                    effort=effort,
                    run_directory=run_directory,
                    continuation_mode=iteration_mode,
                    provider_session_id=iteration_provider_session_id,
                )
            except FileNotFoundError:
                success = False
                iteration_result = f"{agent_label} is not installed. {provider['connect_hint']}"
                stdout_text = ""
                stderr_text = iteration_result
                return_code = 127
                resolved_provider_session_id = iteration_provider_session_id
            except Exception as error:  # noqa: BLE001
                success = False
                iteration_result = f"{agent_label} failed to start: {error}"
                stdout_text = ""
                stderr_text = iteration_result
                return_code = 1
                resolved_provider_session_id = iteration_provider_session_id

            _append_log(stdout_path, f"loop {iteration} stdout", stdout_text)
            _append_log(stderr_path, f"loop {iteration} stderr", stderr_text)

            finished_at = _now_iso()
            iteration_count = iteration
            result_text = iteration_result
            last_return_code = return_code

            update_message(
                project,
                session_id,
                latest_assistant_message_id,
                content=iteration_result,
                status="finished" if success else "failed",
                completed_at=finished_at,
                loop_iteration=iteration,
                run_mode=run_mode,
            )

            if iteration_mode != "transcript_replay" and resolved_provider_session_id:
                _stage_provider_thread(
                    project,
                    session_id=session_id,
                    engine=engine,
                    provider=provider,
                    run_id=run_id,
                    model=model,
                    effort=effort,
                    provider_session_id=resolved_provider_session_id,
                )

            _append_event(
                events_path,
                {
                    "timestamp": finished_at,
                    "event": f"agent.run.iteration.{'finished' if success else 'failed'}",
                    "engine": engine["id"],
                    "engine_label": engine["label"],
                    "provider": provider["id"],
                    "model": model,
                    "effort": effort,
                    "run_mode": run_mode,
                    "iteration": iteration,
                    "exit_code": return_code,
                    "continuation_mode": iteration_mode,
                    "provider_session_id": resolved_provider_session_id,
                },
            )
            _update_manifest(
                manifest_path,
                iteration_count=iteration_count,
                last_activity_at=finished_at,
                result_excerpt=iteration_result[:400],
                continuation_mode=iteration_mode,
                provider_session_id=resolved_provider_session_id,
                summary=(
                    f"{agent_label} completed {_loop_summary(run_mode, iteration_count=iteration_count, max_iterations=max_iterations).lower()}."
                    if success
                    else f"{agent_label} failed on loop {iteration_count}."
                ),
            )

            if not success:
                final_status = "failed"
                final_summary = f"{agent_label} failed on loop {iteration_count}."
                break

            if run_mode == "once":
                final_status = "finished"
                final_summary = f"{agent_label} replied with {model}."
                break

            if iteration >= max_iterations:
                final_status = "finished"
                final_summary = f"{agent_label} completed {iteration_count} autoresearch loops."
                break

            iteration_mode = (
                "native_resume"
                if continuation_mode != "transcript_replay"
                else "transcript_replay"
            )
            iteration_provider_session_id = resolved_provider_session_id or iteration_provider_session_id

        if not final_summary:
            if final_status == "finished":
                final_summary = f"{agent_label} completed {iteration_count} loops."
            elif final_status == "stopped":
                final_summary = f"Stopped {agent_label} after {iteration_count} loops."
            else:
                final_summary = f"{agent_label} failed."

        finished_at = _now_iso()
        if iteration_count == 0:
            update_message(
                project,
                session_id,
                latest_assistant_message_id,
                content=result_text or final_summary,
                status=final_status,
                completed_at=finished_at,
                run_mode=run_mode,
            )
        _update_manifest(
            manifest_path,
            status=final_status,
            finished_at=finished_at,
            summary=final_summary,
            exit_code=last_return_code,
            result_excerpt=result_text[:400],
            continuation_mode=iteration_mode,
            provider_session_id=resolved_provider_session_id,
            iteration_count=iteration_count,
            last_activity_at=finished_at,
            stop_requested=False,
        )
        _write_json(
            run_directory / "summary.json",
            {
                "headline": final_summary,
                "engine": engine["id"],
                "engine_label": engine["label"],
                "provider": provider["label"],
                "model": model,
                "effort": effort,
                "status": final_status,
                "run_mode": run_mode,
                "iteration_count": iteration_count,
                "max_iterations": max_iterations,
                "max_minutes": max_minutes,
                "result_excerpt": result_text[:600],
                "continuation_mode": iteration_mode,
                "provider_session_id": resolved_provider_session_id,
            },
        )
        _append_event(
            events_path,
            {
                "timestamp": finished_at,
                "event": f"agent.run.{final_status}",
                "engine": engine["id"],
                "engine_label": engine["label"],
                "provider": provider["id"],
                "model": model,
                "effort": effort,
                "run_mode": run_mode,
                "iteration_count": iteration_count,
                "exit_code": last_return_code,
                "continuation_mode": iteration_mode,
                "provider_session_id": resolved_provider_session_id,
            },
        )
        if continuation_mode != "transcript_replay":
            _finalize_provider_thread(
                project,
                session_id=session_id,
                engine=engine,
                provider=provider,
                run_id=run_id,
                model=model,
                effort=effort,
                provider_session_id=resolved_provider_session_id,
                final_status=final_status,
            )
    finally:
        _clear_stop_requested(run_id)
        with _RUN_LOCK:
            _RUN_THREADS.pop(run_id, None)


def launch_agent_run(
    project: ProjectRecord,
    *,
    session_id: str,
    engine_id: str = "none",
    provider_id: str,
    model: str,
    effort: str,
    prompt: str,
    run_mode: str = "once",
    max_iterations: int | None = None,
    max_minutes: int | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = next(
        (candidate for candidate in list_chat_providers(settings) if candidate["id"] == provider_id),
        None,
    )
    engine = get_chat_engine(project.root, engine_id, settings=settings)
    if engine is None:
        raise ValueError("Unknown engine.")
    if not engine["available"]:
        notes = [str(note) for note in engine.get("notes", [])]
        raise ValueError(notes[0] if notes else f"{engine['label']} is unavailable.")
    if provider is None:
        raise ValueError("Unknown provider.")
    if provider["status"] != "ready":
        raise ValueError(provider["connect_hint"])
    if not validate_model(provider_id, model, settings):
        raise ValueError("Unsupported model for provider.")
    if not validate_effort(provider_id, effort, settings):
        raise ValueError("Unsupported effort for provider.")
    normalized_run_mode = _normalize_run_mode(run_mode)
    normalized_max_iterations = _normalize_max_iterations(normalized_run_mode, max_iterations)
    normalized_max_minutes = _normalize_max_minutes(normalized_run_mode, max_minutes)
    normalized_engine_id = str(engine["id"])
    agent_label = _agent_identity_label(provider, engine)

    with _RUN_LOCK:
        session = get_session(project, session_id)
        if session is None:
            raise FileNotFoundError(f"Unknown session: {session_id}")
        execution_plan = _resolve_execution_plan(session, provider, engine_id=normalized_engine_id)

        run_id = _build_run_id(provider_id)
        run_directory = _run_dir(project, run_id)
        run_directory.mkdir(parents=True, exist_ok=True)
        (run_directory / "diffs").mkdir(exist_ok=True)
        (run_directory / "artifacts").mkdir(exist_ok=True)

        user_session, user_message = add_message(
            project,
            session_id,
            role="user",
            content=prompt,
            source="chat-ui",
            engine=normalized_engine_id,
            engine_label=str(engine["label"]),
            provider=provider_id,
            provider_label=str(provider["label"]),
            model=model,
            effort=effort,
            status="submitted",
            run_id=run_id,
            run_mode=normalized_run_mode,
            continuation_mode=execution_plan["continuation_mode"],
        )
        assistant_session, assistant_message = add_message(
            project,
            session_id,
            role="assistant",
            content="",
            source="agent-runner",
            engine=normalized_engine_id,
            engine_label=str(engine["label"]),
            provider=provider_id,
            provider_label=str(provider["label"]),
            model=model,
            effort=effort,
            status="running",
            run_id=run_id,
            title=f"{agent_label} is running...",
            run_mode=normalized_run_mode,
            loop_iteration=1,
            continuation_mode=execution_plan["continuation_mode"],
        )

        if execution_plan["reserve_provider_thread"]:
            _stage_provider_thread(
                project,
                session_id=session_id,
                engine=engine,
                provider=provider,
                run_id=run_id,
                model=model,
                effort=effort,
                provider_session_id=execution_plan["provider_session_id"],
            )

        manifest = {
            "id": run_id,
            "type": "chat_agent",
            "backend": provider_id,
            "engine": normalized_engine_id,
            "engine_label": engine["label"],
            "provider_label": provider["label"],
            "session_id": session_id,
            "user_message_id": user_message["id"],
            "assistant_message_id": assistant_message["id"],
            "status": "queued",
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "model": model,
            "effort": effort,
            "summary": (
                f"Queued {agent_label} for autoresearch."
                if normalized_run_mode == "autoresearch"
                else f"Queued {agent_label} with {model}."
            ),
            "prompt_excerpt": prompt[:400],
            "session_title": str(session.get("title") or "Untitled chat"),
            "run_mode": normalized_run_mode,
            "max_iterations": normalized_max_iterations,
            "max_minutes": normalized_max_minutes,
            "iteration_count": 0,
            "current_iteration": 1,
            "last_activity_at": _now_iso(),
            "stop_requested": False,
            "continuation_mode": execution_plan["continuation_mode"],
            "provider_session_id": execution_plan["provider_session_id"],
        }
        _write_manifest(run_directory / "manifest.json", manifest)
        _append_event(
            run_directory / "events.jsonl",
            {
                "timestamp": _now_iso(),
                "event": "agent.run.queued",
                "engine": normalized_engine_id,
                "engine_label": engine["label"],
                "provider": provider_id,
                "model": model,
                "effort": effort,
                "run_mode": normalized_run_mode,
                "max_iterations": normalized_max_iterations,
                "max_minutes": normalized_max_minutes,
                "continuation_mode": execution_plan["continuation_mode"],
                "provider_session_id": execution_plan["provider_session_id"],
            },
        )
        (run_directory / "stdout.log").write_text("", encoding="utf-8")
        (run_directory / "stderr.log").write_text("", encoding="utf-8")

        thread = threading.Thread(
            target=_execute_agent_run,
            kwargs={
                "project": project,
                "session_id": session_id,
                "engine": engine,
                "provider": provider,
                "model": model,
                "effort": effort,
                "prompt": prompt,
                "run_id": run_id,
                "user_message_id": user_message["id"],
                "assistant_message_id": assistant_message["id"],
                "continuation_mode": execution_plan["continuation_mode"],
                "provider_session_id": execution_plan["provider_session_id"],
                "run_mode": normalized_run_mode,
                "max_iterations": normalized_max_iterations,
                "max_minutes": normalized_max_minutes,
            },
            daemon=True,
        )
        _RUN_THREADS[run_id] = thread
        thread.start()

    return {
        "run": manifest,
        "session": assistant_session,
    }


def request_agent_stop(project: ProjectRecord, run_id: str) -> dict[str, Any]:
    manifest_path = _run_dir(project, run_id) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Unknown run: {run_id}")

    manifest = _read_manifest(manifest_path)
    status = str(manifest.get("status") or "")
    if status not in {"queued", "running"}:
        return manifest

    _mark_stop_requested(run_id)
    updated = _update_manifest(
        manifest_path,
        stop_requested=True,
        summary="Stop requested. The run will stop after the current provider turn.",
        last_activity_at=_now_iso(),
    )
    _append_event(
        _run_dir(project, run_id) / "events.jsonl",
        {
            "timestamp": _now_iso(),
            "event": "agent.run.stop_requested",
            "run_id": run_id,
        },
    )
    return updated


def list_agent_runs(
    project: ProjectRecord,
    *,
    statuses: set[str] | None = None,
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    runs_dir = project.workspace / "runs"
    if not runs_dir.exists():
        return []

    manifests: list[dict[str, Any]] = []
    for run_dir in runs_dir.iterdir():
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _read_manifest(manifest_path)
        if manifest.get("type") != "chat_agent":
            continue
        if statuses and manifest.get("status") not in statuses:
            continue
        manifest["path"] = str(run_dir)
        manifests.append(manifest)

    manifests.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if limit is not None:
        manifests = manifests[:limit]
    return manifests
