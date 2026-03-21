from __future__ import annotations

from openmath.workspace.project import ProjectRecord


def serialize_project(project: ProjectRecord) -> dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "root": str(project.root),
        "workspace": str(project.workspace),
        "objective": project.objective,
        "entry_docs": project.entry_docs,
        "lean_project": project.lean_project,
    }


def serialize_project_list(projects: list[ProjectRecord]) -> dict[str, object]:
    return {
        "count": len(projects),
        "projects": [serialize_project(project) for project in projects],
    }
