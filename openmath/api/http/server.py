from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from openmath.api.schemas import serialize_project, serialize_project_list
from openmath.agents.providers import list_chat_providers
from openmath.agents.runtime import launch_agent_run, list_agent_runs, request_agent_stop
from openmath.backends.detection import build_doctor_report, detect_backends
from openmath.coordinator.chats import draft_bootstrap_reply
from openmath.coordinator.projects import collect_project_state
from openmath.coordinator.runs import list_runs
from openmath.memory.graph import load_graph
from openmath.memory.sessions import (
    append_message,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    rename_session,
)
from openmath.settings import load_settings, save_settings, serialize_settings_for_ui
from openmath.workspace.project import (
    delete_project,
    discover_projects,
    is_openmath_project,
    rename_project,
    resolve_project,
    slugify,
)
from openmath.workspace.scaffold import initialize_project

WEB_ROOT = Path(__file__).resolve().parents[3] / "apps" / "web"
LOGO_PATH = Path(__file__).resolve().parents[3] / "logo.png"


def _project_creation_root(search_root: Path) -> Path:
    root = search_root.resolve()
    return root.parent if is_openmath_project(root) else root


def _project_search_root(search_root: Path) -> Path:
    return _project_creation_root(search_root)


def _unique_project_path(search_root: Path, name: str) -> Path:
    base_root = _project_creation_root(search_root)
    stem = slugify(name)
    candidate = base_root / stem
    index = 2
    while candidate.exists():
        candidate = base_root / f"{stem}-{index}"
        index += 1
    return candidate


class OpenMathRequestHandler(BaseHTTPRequestHandler):
    search_root = Path.cwd()
    web_root = WEB_ROOT

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path.startswith("/api/"):
            self._handle_api_get(path)
            return

        self._serve_web_asset(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path == "/api/projects":
            self._handle_create_project()
            return

        path_parts = [part for part in path.split("/") if part]
        if (
            len(path_parts) == 5
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3:] == ["backends", "detect"]
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            self._json({"backends": list(detect_backends(project.root).values())})
            return

        if len(path_parts) == 4 and path_parts[:2] == ["api", "projects"] and path_parts[3] == "sessions":
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            payload = self._read_json()
            session = create_session(
                project,
                title=str(payload.get("title") or "New Chat"),
                origin="ui",
            )
            self._json({"session": session}, status=HTTPStatus.CREATED)
            return

        if (
            len(path_parts) == 6
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3] == "sessions"
            and path_parts[5] == "messages"
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            payload = self._read_json()
            content = str(payload.get("content") or "").strip()
            if not content:
                self._json({"error": "empty_message"}, status=HTTPStatus.BAD_REQUEST)
                return
            session_id = path_parts[4]
            try:
                append_message(project, session_id, role="user", content=content)
                session = append_message(
                    project,
                    session_id,
                    role="assistant",
                    content=draft_bootstrap_reply(project, content),
                    source="bootstrap-assistant",
                )
            except FileNotFoundError:
                self._json({"error": "session_not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError:
                self._json({"error": "empty_message"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json({"session": session})
            return

        if (
            len(path_parts) == 5
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3:] == ["agents", "runs"]
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            payload = self._read_json()
            try:
                launched = launch_agent_run(
                    project,
                    session_id=str(payload.get("session_id") or ""),
                    engine_id=str(payload.get("engine_id") or "none"),
                    provider_id=str(payload.get("provider_id") or ""),
                    model=str(payload.get("model") or ""),
                    effort=str(payload.get("effort") or "medium"),
                    prompt=str(payload.get("prompt") or ""),
                    run_mode=str(payload.get("run_mode") or "once"),
                    max_iterations=payload.get("max_iterations"),
                    max_minutes=payload.get("max_minutes"),
                    settings=self._settings(),
                )
            except (FileNotFoundError, ValueError) as error:
                self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json(launched, status=HTTPStatus.CREATED)
            return

        if (
            len(path_parts) == 7
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3] == "agents"
            and path_parts[4] == "runs"
            and path_parts[6] == "stop"
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            try:
                manifest = request_agent_stop(project, path_parts[5])
            except FileNotFoundError:
                self._json({"error": "run_not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._json({"run": manifest})
            return

        self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        if path == "/api/settings":
            payload = self._read_json()
            updates = {
                "providers": {
                    "ollama": {
                        "base_url": str(payload.get("ollama_base_url") or "").strip() or "http://127.0.0.1:11434",
                    },
                },
            }
            if "aristotle_api_key" in payload:
                updates.setdefault("engines", {}).setdefault("aristotle", {})["api_key"] = str(payload.get("aristotle_api_key") or "").strip()
            if payload.get("clear_aristotle_api_key") is True:
                updates.setdefault("engines", {}).setdefault("aristotle", {})["api_key"] = ""
            settings = save_settings(self.search_root, updates)
            self._json({"settings": serialize_settings_for_ui(settings)})
            return
        path_parts = [part for part in path.split("/") if part]
        if len(path_parts) == 3 and path_parts[:2] == ["api", "projects"]:
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            payload = self._read_json()
            try:
                updated = rename_project(project, name=str(payload.get("name") or ""))
            except ValueError as error:
                self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json({"project": serialize_project(updated)})
            return

        if (
            len(path_parts) == 5
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3] == "sessions"
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            payload = self._read_json()
            try:
                session = rename_session(
                    project,
                    path_parts[4],
                    title=str(payload.get("title") or ""),
                )
            except FileNotFoundError:
                self._json({"error": "session_not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as error:
                self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json({"session": session})
            return

        self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        path_parts = [part for part in path.split("/") if part]
        if len(path_parts) == 3 and path_parts[:2] == ["api", "projects"]:
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            try:
                delete_project(project)
            except ValueError as error:
                self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json({"ok": True})
            return

        if (
            len(path_parts) == 5
            and path_parts[:2] == ["api", "projects"]
            and path_parts[3] == "sessions"
        ):
            project = self._project_or_404(path_parts[2])
            if not project:
                return
            try:
                delete_session(project, path_parts[4])
            except FileNotFoundError:
                self._json({"error": "session_not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True})
            return

        self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_api_get(self, path: str) -> None:
        if path == "/api/projects":
            projects = discover_projects(_project_search_root(self.search_root))
            self._json(serialize_project_list(projects))
            return

        if path == "/api/settings":
            self._json({"settings": serialize_settings_for_ui(self._settings())})
            return

        if path == "/api/doctor":
            self._json(build_doctor_report(self.search_root))
            return

        path_parts = [part for part in path.split("/") if part]
        if len(path_parts) < 4 or path_parts[:2] != ["api", "projects"]:
            self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        project = self._project_or_404(path_parts[2])
        if not project:
            return

        route = path_parts[3]
        if route == "state":
            self._json(collect_project_state(project, settings=self._settings()))
            return
        if route == "runs":
            self._json({"runs": list_runs(project)})
            return
        if route == "graph":
            self._json(load_graph(project))
            return
        if route == "backends":
            self._json({"backends": list(detect_backends(project.root).values())})
            return
        if route == "agents":
            if len(path_parts) == 5 and path_parts[4] == "providers":
                self._json({"providers": list_chat_providers(self._settings())})
                return
            if len(path_parts) == 5 and path_parts[4] == "runs":
                self._json({"runs": list_agent_runs(project)})
                return
        if route == "sessions":
            if len(path_parts) == 4:
                self._json({"sessions": list_sessions(project)})
                return
            if len(path_parts) == 5:
                session = get_session(project, path_parts[4])
                if session is None:
                    self._json({"error": "session_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._json({"session": session})
                return

        self._json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_create_project(self) -> None:
        payload = self._read_json()
        name = str(payload.get("name") or "").strip()
        if not name:
            self._json({"error": "Project name is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        raw_path = str(payload.get("path") or "").strip()
        path = Path(raw_path) if raw_path else _unique_project_path(self.search_root, name)
        project = initialize_project(
            path,
            name=name,
            objective=str(payload.get("objective") or f"Define the first research objective for {name}."),
        )
        self._json(collect_project_state(project, settings=self._settings()), status=HTTPStatus.CREATED)

    def _project_or_404(self, project_id: str):
        project = resolve_project(_project_search_root(self.search_root), project_id)
        if project is None:
            self._json({"error": "project_not_found"}, status=HTTPStatus.NOT_FOUND)
        return project

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw)

    def _settings(self) -> dict[str, object]:
        return load_settings(self.search_root)

    def _serve_web_asset(self, raw_path: str) -> None:
        path = "/" if raw_path == "" else raw_path
        if path == "/":
            return self._serve_file(self.web_root / "index.html")
        if path == "/logo.png" and LOGO_PATH.is_file():
            return self._serve_file(LOGO_PATH)

        candidate = (self.web_root / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(self.web_root.resolve())
        except ValueError:
            self._json({"error": "invalid_path"}, status=HTTPStatus.BAD_REQUEST)
            return

        if candidate.is_file():
            self._serve_file(candidate)
            return

        self._serve_file(self.web_root / "index.html")

    def _serve_file(self, path: Path) -> None:
        content = path.read_bytes()
        mime_type, _encoding = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, payload: dict[str, object], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve(project_root: Path, host: str = "127.0.0.1", port: int = 31789) -> None:
    search_root = _project_search_root(project_root.resolve())
    handler = type(
        "ConfiguredOpenMathRequestHandler",
        (OpenMathRequestHandler,),
        {
            "search_root": search_root,
            "web_root": WEB_ROOT.resolve(),
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"OpenMath gateway listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OpenMath local gateway.")
    parser.add_argument("path", nargs="?", default=".", help="Project root or search root.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the gateway to.")
    parser.add_argument("--port", default=31789, type=int, help="Port to bind the gateway to.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    serve(Path(args.path), host=args.host, port=args.port)
    return 0
