from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openmath.coordinator.projects import collect_project_state
from openmath.workspace.project import load_project
from openmath.workspace.scaffold import initialize_project


class ProjectStateTests(unittest.TestCase):
    def test_collect_project_state_reads_bootstrap_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            initialize_project(root, name="Demo Project", objective="Investigate a lemma.")
            project = load_project(root)

            state = collect_project_state(project)

            self.assertEqual(state["project"]["name"], "Demo Project")
            self.assertEqual(state["summary"]["graph_nodes"], 1)
            self.assertEqual(state["summary"]["sessions"], 1)
            self.assertEqual(state["summary"]["messages"], 0)
            self.assertEqual(state["summary"]["active_agents"], 0)
            self.assertEqual(len(state["recent_runs"]), 1)
            self.assertEqual(len(state["sessions"]), 1)
            self.assertEqual(len(state["agent_providers"]), 3)
            self.assertIn("agent_stream", state)
            self.assertEqual(state["agent_stream"], [])
            self.assertTrue(state["backends"])


if __name__ == "__main__":
    unittest.main()
