from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openmath.api.http.server import _project_creation_root, _project_search_root, _unique_project_path
from openmath.workspace.scaffold import initialize_project


class HttpServerTests(unittest.TestCase):
    def test_project_creation_root_uses_parent_for_project_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing-project"
            initialize_project(root, name="Existing Project", objective="Investigate a lemma.")

            creation_root = _project_creation_root(root)
            search_root = _project_search_root(root)

            self.assertEqual(creation_root, Path(tmp).resolve())
            self.assertEqual(search_root, Path(tmp).resolve())

    def test_unique_project_path_uses_slug_and_suffixes_existing_folders(self) -> None:
        with TemporaryDirectory() as tmp:
            search_root = Path(tmp)
            (search_root / "hadamard-matrix").mkdir()

            first = _unique_project_path(search_root, "Hadamard Matrix")
            first.mkdir()
            second = _unique_project_path(search_root, "Hadamard Matrix")

            self.assertEqual(first.name, "hadamard-matrix-2")
            self.assertEqual(second.name, "hadamard-matrix-3")


if __name__ == "__main__":
    unittest.main()
