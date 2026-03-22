from __future__ import annotations

from pathlib import Path
from typing import Any

from openmath.backends.detection import detect_backends


def _engine_card(
    *,
    engine_id: str,
    label: str,
    status: str,
    available: bool,
    connect_target_label: str,
    description: str,
    command: str | None = None,
    executable: str | None = None,
    version: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": engine_id,
        "label": label,
        "status": status,
        "available": available,
        "connect_target_label": connect_target_label,
        "description": description,
        "command": command,
        "executable": executable,
        "version": version,
        "notes": notes or [],
    }


def list_chat_engines(
    project_root: Path | None = None,
    *,
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    backends = detect_backends(project_root)
    native = backends["native"]
    ulam = backends["ulam"]
    aristotle = backends["aristotle"]
    aristotle_api_key = str(
        (settings or {}).get("engines", {}).get("aristotle", {}).get("api_key") or ""
    ).strip()
    aristotle_available = bool(aristotle["installed"]) or bool(aristotle_api_key)
    aristotle_notes = [str(note) for note in aristotle.get("notes", [])]
    if not aristotle_available and not aristotle_notes:
        aristotle_notes = ["Aristotle CLI is unavailable until you install it or add an API key in Settings."]
    if bool(aristotle_api_key):
        aristotle_notes = ["API key configured in Settings."]

    return [
        _engine_card(
            engine_id="none",
            label="None",
            status="ready",
            available=True,
            connect_target_label="Provider",
            description="Use the selected provider directly with no extra engine profile.",
        ),
        _engine_card(
            engine_id="ulam",
            label="UlamAI",
            status="ready" if bool(ulam["installed"]) else "unavailable",
            available=bool(ulam["installed"]),
            connect_target_label="Connect to",
            description="Apply a UlamAI-style formalization and proving workflow through the selected provider.",
            command=str(ulam["command"]),
            executable=(str(ulam["executable"]) if ulam.get("executable") else None),
            version=(str(ulam["version"]) if ulam.get("version") else None),
            notes=[str(note) for note in ulam.get("notes", [])],
        ),
        _engine_card(
            engine_id="aristotle",
            label="Aristotle",
            status="ready" if aristotle_available else "unavailable",
            available=aristotle_available,
            connect_target_label="Connect to",
            description="Apply an Aristotle-style autonomous proof workflow through the selected provider.",
            command=str(aristotle["command"]),
            executable=(str(aristotle["executable"]) if aristotle.get("executable") else None),
            version=(str(aristotle["version"]) if aristotle.get("version") else None),
            notes=aristotle_notes,
        ),
        _engine_card(
            engine_id="lean4_skills",
            label="lean4-skills",
            status="ready" if str(native["status"]) == "ready" else "unavailable",
            available=str(native["status"]) == "ready",
            connect_target_label="Provider",
            description="Bias the agent toward Lean 4 research, proof decomposition, and checkable tactics.",
            command=str(native["command"]),
            executable=(str(native["executable"]) if native.get("executable") else None),
            version=(str(native["version"]) if native.get("version") else None),
            notes=[str(note) for note in native.get("notes", [])],
        ),
    ]


def get_chat_engine(
    project_root: Path | None,
    engine_id: str,
    *,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    for engine in list_chat_engines(project_root, settings=settings):
        if engine["id"] == engine_id:
            return engine
    return None
