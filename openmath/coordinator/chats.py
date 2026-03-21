from __future__ import annotations

from openmath.backends.detection import detect_backends
from openmath.coordinator.runs import list_runs
from openmath.memory.graph import load_graph
from openmath.workspace.project import ProjectRecord


def draft_bootstrap_reply(project: ProjectRecord, prompt: str) -> str:
    graph = load_graph(project)
    runs = list_runs(project)
    backends = detect_backends(project.root)
    native_status = backends["native"]["status"]
    ulam_status = backends["ulam"]["status"]
    aristotle_status = backends["aristotle"]["status"]
    lower_prompt = prompt.lower()

    suggestions: list[str] = []
    if "project" in lower_prompt or "folder" in lower_prompt:
        suggestions.append(
            "Initialize sibling folders with `python3 -m openmath init path/to/project`, "
            "then serve their parent directory to browse them from one picker."
        )
    if "lean" in lower_prompt or "prove" in lower_prompt:
        suggestions.append(
            "Wire a Lean project into `.openmath/project.toml`, then expose declaration and "
            "diagnostic runs through the native backend."
        )
    if "chat" in lower_prompt or "thread" in lower_prompt:
        suggestions.append(
            "Use separate chats for strategy, proving, source reading, and review so the project "
            "history stays segmented instead of collapsing into one transcript."
        )
    if not suggestions:
        suggestions.append(
            "The next useful slice is connecting these chats to real agent actions and run creation, "
            "so conversations can launch inspectable work instead of staying passive notes."
        )

    return (
        "Message saved to session memory.\n\n"
        f"Workspace snapshot: {graph['counts']['nodes']} graph nodes, {len(runs)} runs, "
        f"native backend {native_status}, Ulam {ulam_status}, Aristotle {aristotle_status}.\n\n"
        "Recommended next steps:\n"
        + "\n".join(f"- {item}" for item in suggestions)
    )
