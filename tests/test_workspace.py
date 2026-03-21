from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openmath.coordinator.runs import list_runs
from openmath.memory.graph import load_graph
from openmath.memory.sessions import list_sessions
from openmath.workspace.project import delete_project, discover_projects, load_project, rename_project, resolve_project
from openmath.workspace.scaffold import initialize_project


class WorkspaceTests(unittest.TestCase):
    def test_initialize_project_creates_workspace_and_init_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(
                root,
                name="Demo Project",
                objective="Bootstrap a mathematical workspace.",
            )

            self.assertTrue((root / ".openmath" / "project.toml").exists())
            self.assertEqual(project.id, "demo-project")

            loaded = load_project(root)
            graph = load_graph(loaded)
            runs = list_runs(loaded)
            sessions = list_sessions(loaded)

            self.assertEqual(graph["counts"]["nodes"], 1)
            self.assertEqual(len(runs), 1)
            self.assertEqual(len(sessions), 1)

    def test_project_ids_follow_folder_names_for_duplicate_display_names(self) -> None:
        with TemporaryDirectory() as tmp:
            root_one = Path(tmp) / "frontier"
            root_two = Path(tmp) / "frontier-2"
            initialize_project(root_one, name="Frontier", objective="One")
            initialize_project(root_two, name="Frontier", objective="Two")

            projects = discover_projects(Path(tmp))
            ids = {project.id for project in projects}
            resolved_one = resolve_project(Path(tmp), "frontier")
            resolved_two = resolve_project(Path(tmp), "frontier-2")

            self.assertIn("frontier", ids)
            self.assertIn("frontier-2", ids)
            self.assertIsNotNone(resolved_one)
            self.assertIsNotNone(resolved_two)
            self.assertEqual(resolved_one.root, root_one.resolve())
            self.assertEqual(resolved_two.root, root_two.resolve())

    def test_rename_project_updates_display_name_without_changing_folder_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(root, name="Demo Project", objective="Bootstrap a mathematical workspace.")

            renamed = rename_project(project, name="Renamed Project")

            self.assertEqual(renamed.name, "Renamed Project")
            self.assertEqual(renamed.id, "demo-project")

    def test_delete_project_removes_workspace_but_keeps_root_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            project = initialize_project(root, name="Demo Project", objective="Bootstrap a mathematical workspace.")

            delete_project(project)

            self.assertTrue(root.exists())
            self.assertFalse((root / ".openmath").exists())


if __name__ == "__main__":
    unittest.main()
