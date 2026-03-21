from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from openmath.backends.detection import build_doctor_report, detect_backends
from openmath.coordinator.projects import collect_project_state
from openmath.coordinator.runs import list_runs
from openmath.memory.graph import load_graph
from openmath.workspace.project import load_project
from openmath.workspace.scaffold import initialize_project


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2))


def cmd_init(args: argparse.Namespace) -> int:
    project = initialize_project(
        Path(args.path),
        name=args.name,
        objective=args.objective,
        entry_docs=args.entry_doc or None,
        lean_project=args.lean_project,
        overwrite=args.force,
    )
    print(f"Initialized OpenMath project at {project.root}")
    print(f"Workspace: {project.workspace}")
    print("Next: python3 -m openmath doctor")
    print("Then: python3 -m openmath web")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = build_doctor_report(Path(args.path))
    if args.json:
        _print_json(report)
        return 0

    print("OpenMath doctor")
    print(f"Project root: {report['project_root']}")
    print(f"Platform: {report['platform']}")
    print("Runtime:")
    for name, status in report["runtime"].items():
        installed = "yes" if status["installed"] else "no"
        print(f"  {name:6} installed={installed:3} version={status['version'] or 'unknown'}")
    print("Backends:")
    for backend in report["backends"].values():
        installed = "yes" if backend["installed"] else "no"
        print(
            f"  {backend['id']:10} status={backend['status']:7} installed={installed:3} "
            f"version={backend['version'] or 'unknown'}"
        )
        for note in backend["notes"]:
            print(f"    note: {note}")
    return 0


def cmd_backend_detect(args: argparse.Namespace) -> int:
    backends = detect_backends(Path(args.path))
    if args.json:
        _print_json({"backends": list(backends.values())})
        return 0

    for backend in backends.values():
        print(f"{backend['label']}:")
        print(f"  status: {backend['status']}")
        print(f"  installed: {'yes' if backend['installed'] else 'no'}")
        print(f"  command: {backend['command']}")
        print(f"  executable: {backend['executable'] or 'not found'}")
        print(f"  version: {backend['version'] or 'unknown'}")
        if backend["notes"]:
            for note in backend["notes"]:
                print(f"  note: {note}")
    return 0


def cmd_graph_show(args: argparse.Namespace) -> int:
    project = load_project(Path(args.path))
    graph = load_graph(project)
    print(f"Project: {project.name}")
    print(f"Nodes: {graph['counts']['nodes']}")
    print(f"Edges: {graph['counts']['edges']}")
    print("Recent nodes:")
    for node in graph["nodes"][-10:]:
        print(
            f"  {node.get('id', '<missing>')} "
            f"[{node.get('kind', 'unknown')}] "
            f"{node.get('status', 'unknown')}"
        )
    return 0


def cmd_runs_list(args: argparse.Namespace) -> int:
    project = load_project(Path(args.path))
    runs = list_runs(project)
    if not runs:
        print("No runs found.")
        return 0
    for run in runs:
        print(
            f"{run['id']}  {run.get('type', 'unknown'):10}  "
            f"{run.get('status', 'unknown'):8}  {run.get('summary', '')}"
        )
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    project = load_project(Path(args.path))
    _print_json(collect_project_state(project))
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from openmath.api.http.server import serve

    serve(Path(args.path), host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openmath", description="OpenMath bootstrap CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create an OpenMath workspace.")
    init_parser.add_argument("path", nargs="?", default=".", help="Project root to initialize.")
    init_parser.add_argument("--name", help="Project name.")
    init_parser.add_argument(
        "--objective",
        help="Initial research objective.",
        default="Define the first research objective for this project.",
    )
    init_parser.add_argument(
        "--entry-doc",
        action="append",
        help="Entry document path. Repeat the flag to add multiple documents.",
    )
    init_parser.add_argument(
        "--lean-project",
        default="./LeanProject",
        help="Lean project root relative to the project.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing OpenMath bootstrap files.",
    )
    init_parser.set_defaults(func=cmd_init)

    doctor_parser = subparsers.add_parser("doctor", help="Inspect local runtime and backends.")
    doctor_parser.add_argument("path", nargs="?", default=".", help="Project or search root.")
    doctor_parser.add_argument("--json", action="store_true", help="Print JSON output.")
    doctor_parser.set_defaults(func=cmd_doctor)

    backend_parser = subparsers.add_parser("backend", help="Backend operations.")
    backend_subparsers = backend_parser.add_subparsers(dest="backend_command", required=True)
    backend_detect = backend_subparsers.add_parser(
        "detect", help="Detect installed OpenMath backends."
    )
    backend_detect.add_argument("path", nargs="?", default=".", help="Project or search root.")
    backend_detect.add_argument("--json", action="store_true", help="Print JSON output.")
    backend_detect.set_defaults(func=cmd_backend_detect)

    runs_parser = subparsers.add_parser("runs", help="Inspect run records.")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_subparsers.add_parser("list", help="List recorded runs.")
    runs_list.add_argument("path", nargs="?", default=".", help="Project root.")
    runs_list.set_defaults(func=cmd_runs_list)

    graph_parser = subparsers.add_parser("graph", help="Inspect the claim graph.")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", required=True)
    graph_show = graph_subparsers.add_parser("show", help="Show graph counts and recent nodes.")
    graph_show.add_argument("path", nargs="?", default=".", help="Project root.")
    graph_show.set_defaults(func=cmd_graph_show)

    state_parser = subparsers.add_parser("state", help="Dump current project state as JSON.")
    state_parser.add_argument("path", nargs="?", default=".", help="Project root.")
    state_parser.set_defaults(func=cmd_state)

    web_parser = subparsers.add_parser("web", help="Start the OpenMath local gateway and UI.")
    web_parser.add_argument("path", nargs="?", default=".", help="Project or search root.")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    web_parser.add_argument("--port", default=31789, type=int, help="Port to bind.")
    web_parser.set_defaults(func=cmd_web)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileExistsError as error:
        print(str(error), file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
