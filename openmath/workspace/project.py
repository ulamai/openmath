from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tomllib

from .layout import WORKSPACE_DIRNAME

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    root: Path
    workspace: Path
    objective: str
    entry_docs: list[str]
    lean_project: str
    config: dict[str, object]

    @property
    def project_file(self) -> Path:
        return self.workspace / "project.toml"


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "openmath-project"


def workspace_path(root: Path) -> Path:
    return root / WORKSPACE_DIRNAME


def project_file_path(root: Path) -> Path:
    return workspace_path(root) / "project.toml"


def is_openmath_project(root: Path) -> bool:
    return project_file_path(root).is_file()


def load_project(root: Path) -> ProjectRecord:
    root = root.resolve()
    project_file = project_file_path(root)
    if not project_file.is_file():
        raise FileNotFoundError(f"No OpenMath project found at {root}")

    config = tomllib.loads(project_file.read_text(encoding="utf-8"))
    project_block = config.get("project", {})
    name = str(project_block.get("name") or root.name)
    objective = str(project_block.get("objective") or "No objective defined yet.")
    entry_docs = [str(item) for item in project_block.get("entry_docs", [])]
    lean_project = str(project_block.get("lean_project") or "./LeanProject")
    return ProjectRecord(
        id=slugify(root.name),
        name=name,
        root=root,
        workspace=workspace_path(root),
        objective=objective,
        entry_docs=entry_docs,
        lean_project=lean_project,
        config=config,
    )


def discover_projects(search_root: Path, max_depth: int = 3) -> list[ProjectRecord]:
    root = search_root.resolve()
    projects: list[ProjectRecord] = []
    seen: set[Path] = set()

    for current, dirnames, _filenames in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)

        if is_openmath_project(current_path):
            resolved = current_path.resolve()
            if resolved not in seen:
                projects.append(load_project(resolved))
                seen.add(resolved)
            dirnames[:] = []
            continue

        if depth >= max_depth:
            dirnames[:] = []
            continue

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_DIRECTORIES and dirname != WORKSPACE_DIRNAME
        ]

    if is_openmath_project(root) and root not in seen:
        projects.insert(0, load_project(root))

    return sorted(projects, key=lambda project: (project.name.lower(), str(project.root)))


def resolve_project(search_root: Path, project_id: str) -> ProjectRecord | None:
    for project in discover_projects(search_root):
        if project.id == project_id:
            return project
    return None


def _quote_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def rename_project(project: ProjectRecord, *, name: str) -> ProjectRecord:
    next_name = name.strip()
    if not next_name:
        raise ValueError("Project name cannot be empty.")

    content = project.project_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_project_block = False
    project_header_index: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == "[project]":
                in_project_block = True
                project_header_index = index
                continue
            if in_project_block:
                break
        if in_project_block and re.match(r"^name\s*=", stripped):
            lines[index] = f'name = "{_quote_toml_string(next_name)}"'
            project.project_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return load_project(project.root)

    if project_header_index is None:
        raise ValueError("Project configuration is missing a [project] section.")

    lines.insert(project_header_index + 1, f'name = "{_quote_toml_string(next_name)}"')
    project.project_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_project(project.root)


def delete_project(project: ProjectRecord) -> None:
    workspace = project.workspace.resolve()
    if workspace.name != WORKSPACE_DIRNAME or workspace.parent != project.root.resolve():
        raise ValueError("Refusing to delete a non-standard workspace path.")
    shutil.rmtree(workspace, ignore_errors=False)
