from __future__ import annotations

from pathlib import Path

from openmath.agents.engines import list_chat_engines
from openmath.agents.providers import list_chat_providers
from openmath.agents.runtime import list_agent_runs
from openmath.api.schemas import serialize_project
from openmath.backends.detection import detect_backends
from openmath.coordinator.runs import list_runs
from openmath.memory.graph import load_graph
from openmath.memory.sessions import list_sessions
from openmath.workspace.project import ProjectRecord


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def collect_project_state(
    project: ProjectRecord,
    *,
    settings: dict[str, object] | None = None,
) -> dict[str, object]:
    graph = load_graph(project)
    runs = list_runs(project)
    active_agents = list_agent_runs(project, statuses={"queued", "running"}, limit=12)
    agent_stream = list_agent_runs(project, limit=18)
    agent_providers = list_chat_providers(settings)
    agent_engines = list_chat_engines(project.root, settings=settings)
    sessions = list_sessions(project)
    backends = detect_backends(project.root)
    approvals_pending = _count_files(project.workspace / "approvals")
    source_files = _count_files(project.workspace / "sources")
    exports = _count_files(project.workspace / "exports")

    solved_declarations = sum(
        1
        for node in graph["nodes"]
        if node.get("kind") == "lean-declaration" and node.get("status") == "accepted"
    )
    broken_declarations = sum(
        1
        for node in graph["nodes"]
        if node.get("kind") == "lean-declaration" and node.get("status") == "broken"
    )
    counterexamples = sum(
        1 for node in graph["nodes"] if node.get("kind") == "counterexample"
    )
    recent_runs = runs[:10]
    recent_nodes = list(reversed(graph["nodes"][-10:]))
    total_messages = sum(int(session.get("message_count") or 0) for session in sessions)

    return {
        "project": serialize_project(project),
        "summary": {
            "build_status": backends["native"]["status"],
            "runs": len(runs),
            "active_agents": len(active_agents),
            "sessions": len(sessions),
            "messages": total_messages,
            "graph_nodes": graph["counts"]["nodes"],
            "open_approvals": approvals_pending,
            "sources": source_files,
            "exports": exports,
            "solved_declarations": solved_declarations,
            "broken_declarations": broken_declarations,
            "counterexamples": counterexamples,
        },
        "workspace": {
            "project_file": str(project.project_file),
            "program": str(project.workspace / "program.md"),
            "metrics": str(project.workspace / "metrics.toml"),
        },
        "graph": graph,
        "agent_providers": agent_providers,
        "agent_engines": agent_engines,
        "active_agents": active_agents,
        "agent_stream": agent_stream,
        "sessions": sessions,
        "recent_runs": recent_runs,
        "recent_nodes": recent_nodes,
        "recent_conjectures": [
            node
            for node in recent_nodes
            if node.get("kind") in {"conjecture", "objective", "theorem"}
        ][:5],
        "recent_counterexamples": [
            node for node in recent_nodes if node.get("kind") == "counterexample"
        ][:5],
        "backends": list(backends.values()),
        "routes": {
            "chats": f"/projects/{project.id}/chats",
            "dashboard": f"/projects/{project.id}/dashboard",
            "graph": f"/projects/{project.id}/graph",
            "runs": f"/projects/{project.id}/runs",
            "backends": f"/projects/{project.id}/backends",
            "terminal": f"/projects/{project.id}/terminal",
        },
    }
