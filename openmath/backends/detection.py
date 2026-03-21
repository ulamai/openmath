from __future__ import annotations

from datetime import UTC, datetime
import platform
from pathlib import Path
import shutil
import subprocess


def _probe_version(command: str, args: list[str]) -> tuple[bool, str | None, str | None]:
    executable = shutil.which(command)
    if not executable:
        return False, None, None

    try:
        completed = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return True, executable, None

    output = completed.stdout.strip() or completed.stderr.strip()
    version = output.splitlines()[0] if output else None
    return True, executable, version


def _tool_status(command: str, args: list[str]) -> dict[str, object]:
    installed, executable, version = _probe_version(command, args)
    return {
        "command": command,
        "installed": installed,
        "executable": executable,
        "version": version,
    }


def detect_backends(_project_root: Path | None = None) -> dict[str, dict[str, object]]:
    lean = _tool_status("lean", ["--version"])
    lake = _tool_status("lake", ["--version"])
    ulam = _tool_status("ulam", ["--help"])
    aristotle = _tool_status("aristotle", ["--help"])

    native_notes: list[str] = []
    if not lean["installed"]:
        native_notes.append("`lean` is not available in PATH.")
    if not lake["installed"]:
        native_notes.append("`lake` is not available in PATH.")

    native_installed = bool(lean["installed"] and lake["installed"])
    native_status = "ready" if native_installed else "partial" if any(
        [lean["installed"], lake["installed"]]
    ) else "missing"

    def backend_card(
        backend_id: str,
        label: str,
        tool: dict[str, object],
        *,
        capabilities: list[str],
        notes: list[str] | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        tool_notes = notes or []
        if not tool["installed"] and not tool_notes:
            tool_notes = [f"`{tool['command']}` is not installed."]
        return {
            "id": backend_id,
            "label": label,
            "status": status or ("ready" if tool["installed"] else "missing"),
            "installed": tool["installed"],
            "command": tool["command"],
            "executable": tool["executable"],
            "version": tool["version"],
            "capabilities": capabilities,
            "notes": tool_notes,
        }

    return {
        "native": {
            "id": "native",
            "label": "Native Lean backend",
            "status": native_status,
            "installed": native_installed,
            "command": "lean/lake",
            "executable": lean["executable"] or lake["executable"],
            "version": lean["version"] or lake["version"],
            "capabilities": [
                "lean diagnostics",
                "lake build integration",
                "declaration discovery",
                "deterministic repairs",
            ],
            "notes": native_notes,
            "components": {
                "lean": lean,
                "lake": lake,
            },
        },
        "ulam": backend_card(
            "ulam",
            "UlamAI adapter",
            ulam,
            capabilities=[
                "formalization",
                "advanced proving",
                "artifact import",
            ],
            notes=[
                "Optional backend. Install separately and route selected jobs through it."
            ]
            if not ulam["installed"]
            else [],
        ),
        "aristotle": backend_card(
            "aristotle",
            "Aristotle adapter",
            aristotle,
            capabilities=[
                "sorry filling",
                "remote proof jobs",
                "artifact import",
            ],
            notes=[
                "Optional backend. Install separately and expose it in the Web UI terminal."
            ]
            if not aristotle["installed"]
            else [],
        ),
    }


def build_doctor_report(project_root: Path | None = None) -> dict[str, object]:
    python = _tool_status("python3", ["--version"])
    node = _tool_status("node", ["--version"])
    npm = _tool_status("npm", ["--version"])
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "project_root": str(project_root.resolve()) if project_root else None,
        "platform": platform.platform(),
        "runtime": {
            "python": python,
            "node": node,
            "npm": npm,
        },
        "backends": detect_backends(project_root),
    }
