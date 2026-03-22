from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from openmath.workspace.project import ProjectRecord, slugify

_SESSION_IO_LOCK = RLock()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _transcripts_dir(project: ProjectRecord) -> Path:
    return project.workspace / "sessions" / "transcripts"


def _summaries_dir(project: ProjectRecord) -> Path:
    return project.workspace / "sessions" / "summaries"


def _transcript_path(project: ProjectRecord, session_id: str) -> Path:
    return _transcripts_dir(project) / f"{session_id}.json"


def _summary_path(project: ProjectRecord, session_id: str) -> Path:
    return _summaries_dir(project) / f"{session_id}.json"


def provider_thread_storage_key(provider_id: str, engine_id: str = "none") -> str:
    normalized_engine_id = (engine_id or "none").strip() or "none"
    normalized_provider_id = provider_id.strip()
    return (
        normalized_provider_id
        if normalized_engine_id == "none"
        else f"{normalized_engine_id}:{normalized_provider_id}"
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with _SESSION_IO_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    with _SESSION_IO_LOCK:
        return json.loads(path.read_text(encoding="utf-8"))


def _session_preview(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        source = str(message.get("source") or "")
        content = str(message.get("content") or "").strip()
        if source == "session-seed" or (
            message.get("role") == "assistant"
            and "is ready. This thread is stored in `.openmath/sessions/`" in content
        ):
            continue
        if content:
            compact = " ".join(content.split())
            return compact[:157] + "..." if len(compact) > 160 else compact
    return "New chat"


def build_session_summary(session: dict[str, Any]) -> dict[str, Any]:
    messages = [message for message in session.get("messages", []) if message.get("content")]
    return {
        "id": session["id"],
        "title": session.get("title") or "Untitled chat",
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "message_count": len(messages),
        "preview": _session_preview(messages),
        "pinned": bool(session.get("pinned")),
        "origin": session.get("origin") or "unknown",
    }


def _write_session(project: ProjectRecord, session: dict[str, Any]) -> None:
    _write_json(_transcript_path(project, session["id"]), session)
    _write_json(_summary_path(project, session["id"]), build_session_summary(session))


def _make_session_id(project: ProjectRecord, title: str) -> str:
    stem = slugify(title)[:48] or "chat"
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    base = f"{stem}-{stamp}"
    candidate = base
    index = 2
    while _transcript_path(project, candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _seed_messages(project: ProjectRecord, title: str) -> list[dict[str, Any]]:
    return []


def create_session(
    project: ProjectRecord,
    *,
    title: str | None = None,
    origin: str = "ui",
    pinned: bool = False,
) -> dict[str, Any]:
    session_title = title or "New Chat"
    now = _now_iso()
    session = {
        "id": _make_session_id(project, session_title),
        "title": session_title,
        "created_at": now,
        "updated_at": now,
        "origin": origin,
        "pinned": pinned,
        "messages": _seed_messages(project, session_title),
    }
    _write_session(project, session)
    return session


def ensure_default_session(project: ProjectRecord) -> dict[str, Any]:
    transcripts_dir = _transcripts_dir(project)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    if any(transcripts_dir.glob("*.json")):
        session = get_session(project, list_sessions(project)[0]["id"])
        if session is None:
            raise FileNotFoundError("Failed to load existing default session.")
        return session
    return create_session(
        project,
        title="Research Lead",
        origin="workspace.init",
        pinned=True,
    )


def list_sessions(project: ProjectRecord) -> list[dict[str, Any]]:
    transcripts_dir = _transcripts_dir(project)
    summaries_dir = _summaries_dir(project)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    if not any(transcripts_dir.glob("*.json")):
        ensure_default_session(project)

    summaries: list[dict[str, Any]] = []
    for transcript_path in sorted(transcripts_dir.glob("*.json")):
        session_id = transcript_path.stem
        session = _read_json(transcript_path)
        summary = build_session_summary(session)
        _write_json(_summary_path(project, session_id), summary)
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            not bool(item.get("pinned")),
            str(item.get("updated_at") or ""),
        ),
        reverse=False,
    )
    summaries.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    summaries.sort(key=lambda item: not bool(item.get("pinned")))
    return summaries


def get_session(project: ProjectRecord, session_id: str) -> dict[str, Any] | None:
    transcript_path = _transcript_path(project, session_id)
    if not transcript_path.exists():
        return None
    session = _read_json(transcript_path)
    session.setdefault("messages", [])
    return session


def add_message(
    project: ProjectRecord,
    session_id: str,
    *,
    role: str,
    content: str,
    source: str = "ui",
    **metadata: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    session = get_session(project, session_id)
    if session is None:
        raise FileNotFoundError(f"Unknown session: {session_id}")

    message_content = content.strip()
    if not message_content and not metadata.get("status"):
        raise ValueError("Message content cannot be empty.")

    now = _now_iso()
    message = {
        "id": f"msg-{uuid4().hex[:10]}",
        "role": role,
        "created_at": now,
        "content": message_content,
        "source": source,
        **metadata,
    }
    session.setdefault("messages", []).append(message)
    session["updated_at"] = now
    _write_session(project, session)
    return session, message


def append_message(
    project: ProjectRecord,
    session_id: str,
    *,
    role: str,
    content: str,
    source: str = "ui",
    **metadata: Any,
) -> dict[str, Any]:
    session, _message = add_message(
        project,
        session_id,
        role=role,
        content=content,
        source=source,
        **metadata,
    )
    return session


def update_message(
    project: ProjectRecord,
    session_id: str,
    message_id: str,
    **changes: Any,
) -> dict[str, Any]:
    session = get_session(project, session_id)
    if session is None:
        raise FileNotFoundError(f"Unknown session: {session_id}")

    updated = False
    for message in session.setdefault("messages", []):
        if message.get("id") != message_id:
            continue
        message.update(changes)
        updated = True
        break

    if not updated:
        raise FileNotFoundError(f"Unknown message: {message_id}")

    session["updated_at"] = _now_iso()
    _write_session(project, session)
    return session


def rename_session(
    project: ProjectRecord,
    session_id: str,
    *,
    title: str,
) -> dict[str, Any]:
    session = get_session(project, session_id)
    if session is None:
        raise FileNotFoundError(f"Unknown session: {session_id}")

    next_title = title.strip()
    if not next_title:
        raise ValueError("Session title cannot be empty.")

    session["title"] = next_title
    session["updated_at"] = _now_iso()
    _write_session(project, session)
    return session


def delete_session(project: ProjectRecord, session_id: str) -> None:
    transcript_path = _transcript_path(project, session_id)
    summary_path = _summary_path(project, session_id)
    if not transcript_path.exists():
        raise FileNotFoundError(f"Unknown session: {session_id}")

    with _SESSION_IO_LOCK:
        transcript_path.unlink(missing_ok=True)
        summary_path.unlink(missing_ok=True)

    if not any(_transcripts_dir(project).glob("*.json")):
        ensure_default_session(project)


def get_provider_thread(
    project: ProjectRecord,
    session_id: str,
    provider_id: str,
    engine_id: str = "none",
) -> dict[str, Any] | None:
    session = get_session(project, session_id)
    if session is None:
        return None
    provider_threads = session.get("provider_threads") or {}
    storage_key = provider_thread_storage_key(provider_id, engine_id)
    thread = provider_threads.get(storage_key)
    if not isinstance(thread, dict) and engine_id == "none":
        thread = provider_threads.get(provider_id)
    if not isinstance(thread, dict):
        return None
    return thread


def upsert_provider_thread(
    project: ProjectRecord,
    session_id: str,
    provider_id: str,
    engine_id: str = "none",
    **changes: Any,
) -> dict[str, Any]:
    session = get_session(project, session_id)
    if session is None:
        raise FileNotFoundError(f"Unknown session: {session_id}")

    provider_threads = session.setdefault("provider_threads", {})
    storage_key = provider_thread_storage_key(provider_id, engine_id)
    existing = provider_threads.get(storage_key)
    if not isinstance(existing, dict) and engine_id == "none":
        existing = provider_threads.get(provider_id)
    if not isinstance(existing, dict):
        existing = {
            "provider_id": provider_id,
            "engine_id": engine_id or "none",
            "created_at": _now_iso(),
        }

    existing.update(changes)
    existing["provider_id"] = provider_id
    existing["engine_id"] = engine_id or str(existing.get("engine_id") or "none")
    existing["updated_at"] = _now_iso()
    provider_threads[storage_key] = existing

    session["updated_at"] = _now_iso()
    _write_session(project, session)
    return existing
