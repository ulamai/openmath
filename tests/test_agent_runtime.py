import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from openmath.agents.runtime import (
    _build_command,
    _build_run_id,
    _parse_codex,
    launch_agent_run,
    list_agent_runs,
    request_agent_stop,
)
from openmath.memory.sessions import get_session, list_sessions
from openmath.workspace.project import load_project
from openmath.workspace.scaffold import initialize_project


class _ImmediateThread:
    def __init__(self, *, target=None, kwargs=None, daemon=None):
        self._target = target
        self._kwargs = kwargs or {}
        self.daemon = daemon

    def start(self) -> None:
        if self._target is not None:
            self._target(**self._kwargs)


class _DeferredThread:
    def __init__(self, *, target=None, kwargs=None, daemon=None):
        self._target = target
        self._kwargs = kwargs or {}
        self.daemon = daemon

    def start(self) -> None:
        return None


class AgentRuntimeTests(unittest.TestCase):
    def test_build_run_id_is_collision_safe(self) -> None:
        first = _build_run_id("codex_cli")
        second = _build_run_id("codex_cli")
        self.assertNotEqual(first, second)

    def test_codex_command_passes_reasoning_effort(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            command = _build_command(
                {"id": "codex_cli"},
                project=project,
                prompt="Plan the next proof step.",
                model="gpt-5-codex",
                effort="high",
                run_directory=project.workspace / "runs" / "stub-run",
                continuation_mode="native_init",
                provider_session_id=None,
            )

            self.assertIn("-c", command)
            self.assertIn('model_reasoning_effort="high"', command)

    def test_codex_resume_command_uses_native_session(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            command = _build_command(
                {"id": "codex_cli"},
                project=project,
                prompt="Continue the conversation.",
                model="gpt-5-codex",
                effort="medium",
                run_directory=project.workspace / "runs" / "stub-run",
                continuation_mode="native_resume",
                provider_session_id="thread-123",
            )

            self.assertEqual(command[:3], ["codex", "exec", "resume"])
            self.assertEqual(command[-2:], ["thread-123", "Continue the conversation."])

    def test_claude_commands_use_session_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            new_command = _build_command(
                {"id": "claude_cli"},
                project=project,
                prompt="Start a thread.",
                model="sonnet",
                effort="medium",
                run_directory=project.workspace / "runs" / "stub-run",
                continuation_mode="native_init",
                provider_session_id="11111111-1111-1111-1111-111111111111",
            )
            resumed_command = _build_command(
                {"id": "claude_cli"},
                project=project,
                prompt="Continue that thread.",
                model="sonnet",
                effort="medium",
                run_directory=project.workspace / "runs" / "stub-run",
                continuation_mode="native_resume",
                provider_session_id="11111111-1111-1111-1111-111111111111",
            )

            self.assertIn("--session-id", new_command)
            self.assertIn("-r", resumed_command)

    def test_codex_parser_unwraps_json_errors(self) -> None:
        with TemporaryDirectory() as tmp:
            run_directory = Path(tmp)
            error_payload = json.dumps(
                {
                    "type": "error",
                    "status": 400,
                    "error": {
                        "type": "invalid_request_error",
                        "message": "The 'gpt-5-mini' model is not supported when using Codex with a ChatGPT account.",
                    },
                }
            )
            ok, result = _parse_codex(
                run_directory,
                "\n".join(
                    [
                        '{"type":"thread.started","thread_id":"019d1122-0f5b-7a70-963a-a380cf9a564e"}',
                        '{"type":"turn.started"}',
                        json.dumps({"type": "error", "message": error_payload}),
                        json.dumps({"type": "turn.failed", "error": {"message": error_payload}}),
                    ]
                ),
                "",
            )

            self.assertFalse(ok)
            self.assertEqual(
                result,
                "The 'gpt-5-mini' model is not supported when using Codex with a ChatGPT account.",
            )

    def test_launch_agent_run_stores_provider_thread_and_resumes_next_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            project = load_project(root)
            session_id = list_sessions(project)[0]["id"]
            provider = {
                "id": "codex_cli",
                "label": "Codex",
                "status": "ready",
                "connect_hint": "Run auth.",
                "native_continuation": True,
                "session_strategy": "capture_thread_id",
            }

            with (
                patch("openmath.agents.runtime.list_chat_providers", return_value=[provider]),
                patch("openmath.agents.runtime.validate_model", return_value=True),
                patch("openmath.agents.runtime.validate_effort", return_value=True),
                patch("openmath.agents.runtime.threading.Thread", _ImmediateThread),
                patch(
                    "openmath.agents.runtime._run_process",
                    side_effect=[
                        (True, "First answer.", "", "", 0, "thread-123"),
                        (True, "Second answer.", "", "", 0, "thread-123"),
                    ],
                ),
            ):
                launch_agent_run(
                    project,
                    session_id=session_id,
                    provider_id="codex_cli",
                    model="gpt-5-codex",
                    effort="medium",
                    prompt="How should we attack this proof?",
                )
                first_runs = list_agent_runs(project)
                self.assertEqual(first_runs[0]["continuation_mode"], "native_init")
                self.assertEqual(first_runs[0]["provider_session_id"], "thread-123")

                launch_agent_run(
                    project,
                    session_id=session_id,
                    provider_id="codex_cli",
                    model="gpt-5-codex",
                    effort="medium",
                    prompt="Continue from the previous answer.",
                )

            session = get_session(project, session_id)
            self.assertIsNotNone(session)
            assert session is not None
            self.assertEqual(session["provider_threads"]["codex_cli"]["native_session_id"], "thread-123")
            self.assertEqual(session["provider_threads"]["codex_cli"]["active_run_id"], None)
            self.assertEqual(session["messages"][-2]["role"], "user")
            self.assertEqual(session["messages"][-1]["role"], "assistant")
            self.assertEqual(session["messages"][-1]["status"], "finished")
            self.assertEqual(session["messages"][-1]["content"], "Second answer.")

            runs = list_agent_runs(project)
            self.assertEqual(len(runs), 2)
            self.assertTrue(all(run["status"] == "finished" for run in runs))
            self.assertIn("native_init", {run["continuation_mode"] for run in runs})
            self.assertIn("native_resume", {run["continuation_mode"] for run in runs})
            self.assertTrue(all(run["backend"] == "codex_cli" for run in runs))

    def test_autoresearch_run_ignores_done_marker_and_runs_to_loop_cap(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            project = load_project(root)
            session_id = list_sessions(project)[0]["id"]
            provider = {
                "id": "gemini_cli",
                "label": "Gemini CLI",
                "status": "ready",
                "connect_hint": "Run auth.",
                "native_continuation": False,
                "session_strategy": "transcript_replay",
            }

            with (
                patch("openmath.agents.runtime.list_chat_providers", return_value=[provider]),
                patch("openmath.agents.runtime.validate_model", return_value=True),
                patch("openmath.agents.runtime.validate_effort", return_value=True),
                patch("openmath.agents.runtime.threading.Thread", _ImmediateThread),
                patch(
                    "openmath.agents.runtime._run_process",
                    side_effect=[
                        (True, "Investigated the first angle.", "", "", 0, None),
                        (True, "DONE: The second pass closed the loop.", "", "", 0, None),
                        (True, "Third pass verified and extended the result.", "", "", 0, None),
                    ],
                ),
            ):
                launch_agent_run(
                    project,
                    session_id=session_id,
                    provider_id="gemini_cli",
                    model="gemini-2.5-pro",
                    effort="medium",
                    prompt="Drive this research thread forward.",
                    run_mode="autoresearch",
                    max_iterations=3,
                    max_minutes=120,
                )

            session = get_session(project, session_id)
            self.assertIsNotNone(session)
            assert session is not None
            assistant_messages = [message for message in session["messages"] if message["role"] == "assistant"]
            self.assertEqual(len(assistant_messages), 3)
            self.assertEqual(assistant_messages[0]["loop_iteration"], 1)
            self.assertEqual(assistant_messages[1]["loop_iteration"], 2)
            self.assertEqual(assistant_messages[2]["loop_iteration"], 3)
            self.assertEqual(assistant_messages[1]["content"], "DONE: The second pass closed the loop.")
            self.assertEqual(
                assistant_messages[2]["content"],
                "Third pass verified and extended the result.",
            )

            runs = list_agent_runs(project)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["status"], "finished")
            self.assertEqual(runs[0]["run_mode"], "autoresearch")
            self.assertEqual(runs[0]["iteration_count"], 3)
            self.assertEqual(runs[0]["max_iterations"], 3)
            self.assertEqual(runs[0]["max_minutes"], 120)

    def test_request_agent_stop_marks_run_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            project = load_project(root)
            session_id = list_sessions(project)[0]["id"]
            provider = {
                "id": "codex_cli",
                "label": "Codex",
                "status": "ready",
                "connect_hint": "Run auth.",
                "native_continuation": True,
                "session_strategy": "capture_thread_id",
            }

            with (
                patch("openmath.agents.runtime.list_chat_providers", return_value=[provider]),
                patch("openmath.agents.runtime.validate_model", return_value=True),
                patch("openmath.agents.runtime.validate_effort", return_value=True),
                patch("openmath.agents.runtime.threading.Thread", _DeferredThread),
            ):
                launched = launch_agent_run(
                    project,
                    session_id=session_id,
                    provider_id="codex_cli",
                    model="gpt-5-codex",
                    effort="medium",
                    prompt="Keep working.",
                    run_mode="autoresearch",
                    max_iterations=12,
                    max_minutes=240,
                )

                updated = request_agent_stop(project, launched["run"]["id"])

            self.assertTrue(updated["stop_requested"])
            self.assertIn("Stop requested", updated["summary"])


if __name__ == "__main__":
    unittest.main()
