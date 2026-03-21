from __future__ import annotations

import json
from pathlib import Path

from openmath.workspace.project import ProjectRecord


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []

    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def load_graph(project: ProjectRecord) -> dict[str, object]:
    nodes = _load_jsonl(project.workspace / "graph" / "nodes.jsonl")
    edges = _load_jsonl(project.workspace / "graph" / "edges.jsonl")
    counts = {
        "nodes": len(nodes),
        "edges": len(edges),
        "accepted": sum(1 for node in nodes if node.get("status") == "accepted"),
        "speculative": sum(1 for node in nodes if node.get("status") == "speculative"),
        "broken": sum(1 for node in nodes if node.get("status") == "broken"),
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": counts,
    }
