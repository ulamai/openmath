from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from openmath.memory.sessions import create_session

from .layout import (
    WORKSPACE_DIRECTORIES,
    render_metrics_toml,
    render_program_md,
    render_project_toml,
)
from .project import ProjectRecord, is_openmath_project, load_project, slugify, workspace_path


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def initialize_project(
    root: Path,
    *,
    name: str | None = None,
    objective: str | None = None,
    entry_docs: list[str] | None = None,
    lean_project: str | None = None,
    overwrite: bool = False,
) -> ProjectRecord:
    root = root.resolve()
    workspace = workspace_path(root)

    if is_openmath_project(root) and not overwrite:
        raise FileExistsError(f"OpenMath workspace already exists at {root}")

    root.mkdir(parents=True, exist_ok=True)
    for relative_dir in WORKSPACE_DIRECTORIES:
        (workspace / relative_dir).mkdir(parents=True, exist_ok=True)

    project_name = name or root.name
    project_objective = objective or "Define the first research objective for this project."
    docs = entry_docs or (["README.md"] if (root / "README.md").exists() else [])
    lean_root = lean_project or "./LeanProject"
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()

    _write_text(
        workspace / "project.toml",
        render_project_toml(project_name, project_objective, docs, lean_root),
        overwrite=True,
    )
    _write_text(
        workspace / "program.md",
        render_program_md(project_name, project_objective),
        overwrite=overwrite,
    )
    _write_text(
        workspace / "metrics.toml",
        render_metrics_toml(),
        overwrite=overwrite,
    )
    _write_text(
        workspace / "graph" / "nodes.jsonl",
        json.dumps(
            {
                "id": f"objective:{slugify(project_name)}",
                "kind": "objective",
                "label": project_objective,
                "status": "accepted",
                "source": "workspace.init",
                "updated_at": timestamp,
            }
        )
        + "\n",
        overwrite=overwrite,
    )
    _write_text(workspace / "graph" / "edges.jsonl", "", overwrite=overwrite)
    _write_text(
        workspace / "experiments" / "results.tsv",
        "run_id\tmetric\tvalue\tdecision\n",
        overwrite=overwrite,
    )
    _write_json(
        workspace / "backends" / "health.json",
        {
            "generated_at": timestamp,
            "native": {"status": "unknown"},
            "ulam": {"status": "unknown"},
            "aristotle": {"status": "unknown"},
        },
        overwrite=overwrite,
    )

    run_id = f"{timestamp.replace(':', '').replace('-', '').lower()}-init"
    run_dir = workspace / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "id": run_id,
            "type": "init",
            "backend": "native",
            "status": "finished",
            "started_at": timestamp,
            "finished_at": timestamp,
            "summary": "Initialized OpenMath workspace scaffold.",
            "affected_files": [
                ".openmath/project.toml",
                ".openmath/program.md",
                ".openmath/metrics.toml",
            ],
        },
        overwrite=overwrite,
    )
    _write_text(
        run_dir / "events.jsonl",
        json.dumps(
            {
                "timestamp": timestamp,
                "event": "run.finished",
                "message": "Workspace bootstrap completed.",
            }
        )
        + "\n",
        overwrite=overwrite,
    )
    _write_json(
        run_dir / "summary.json",
        {
            "headline": "OpenMath workspace initialized",
            "objective": project_objective,
            "next_steps": [
                "Run `python3 -m openmath doctor`.",
                "Run `python3 -m openmath web`.",
                "Add Lean and source files, then wire them into the workspace.",
            ],
        },
        overwrite=overwrite,
    )
    _write_text(run_dir / "stdout.log", "", overwrite=overwrite)
    _write_text(run_dir / "stderr.log", "", overwrite=overwrite)
    (run_dir / "diffs").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)

    project = load_project(root)
    if overwrite or not any((project.workspace / "sessions" / "transcripts").glob("*.json")):
        create_session(
            project,
            title="Research Lead",
            origin="workspace.init",
            pinned=True,
        )
    return project
