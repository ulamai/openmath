from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openmath.memory.sessions import (
    append_message,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    rename_session,
)
from openmath.workspace.project import load_project
from openmath.workspace.scaffold import initialize_project


class SessionTests(unittest.TestCase):
    def test_workspace_bootstrap_creates_default_thread(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Study a theorem.")
            project = load_project(root)

            sessions = list_sessions(project)

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["title"], "Research Lead")
            self.assertEqual(sessions[0]["message_count"], 0)

    def test_append_message_updates_transcript_and_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Study a theorem.")
            project = load_project(root)
            session_id = list_sessions(project)[0]["id"]

            append_message(project, session_id, role="user", content="Plan the next proving pass.")
            session = get_session(project, session_id)
            summaries = list_sessions(project)

            self.assertIsNotNone(session)
            self.assertEqual(session["messages"][-1]["role"], "user")
            self.assertIn("Plan the next proving pass.", session["messages"][-1]["content"])
            self.assertEqual(summaries[0]["message_count"], len(session["messages"]))

    def test_rename_session_updates_title(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Study a theorem.")
            project = load_project(root)
            session_id = list_sessions(project)[0]["id"]

            renamed = rename_session(project, session_id, title="Hadamard Search")

            self.assertEqual(renamed["title"], "Hadamard Search")
            self.assertEqual(list_sessions(project)[0]["title"], "Hadamard Search")

    def test_delete_session_recreates_default_when_last_thread_removed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Study a theorem.")
            project = load_project(root)
            original_id = list_sessions(project)[0]["id"]

            delete_session(project, original_id)

            sessions = list_sessions(project)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["title"], "Research Lead")

    def test_delete_session_removes_only_selected_thread(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Study a theorem.")
            project = load_project(root)
            first_id = list_sessions(project)[0]["id"]
            second = create_session(project, title="Aux Thread")

            delete_session(project, second["id"])

            sessions = list_sessions(project)
            self.assertEqual([session["id"] for session in sessions], [first_id])


if __name__ == "__main__":
    unittest.main()
