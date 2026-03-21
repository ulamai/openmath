from __future__ import annotations

import json
from pathlib import Path

from openmath.workspace.project import ProjectRecord


def list_runs(project: ProjectRecord) -> list[dict[str, object]]:
    runs_dir = project.workspace / "runs"
    if not runs_dir.exists():
        return []

    manifests: list[dict[str, object]] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("id", run_dir.name)
        manifest["path"] = str(run_dir)
        manifests.append(manifest)

    manifests.sort(key=lambda item: str(item.get("started_at", "")), reverse=True)
    return manifests
