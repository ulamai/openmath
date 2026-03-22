from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "providers": {
        "ollama": {
            "base_url": "http://127.0.0.1:11434",
        },
    },
    "engines": {
        "aristotle": {
            "api_key": "",
        },
    },
}


def _settings_path(search_root: Path) -> Path:
    return search_root.resolve() / ".openmath" / "settings.json"


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _merge_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_copy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(search_root: Path) -> dict[str, Any]:
    path = _settings_path(search_root)
    settings = _deep_copy(DEFAULT_SETTINGS)
    if not path.exists():
        return settings
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    if not isinstance(stored, dict):
        return settings
    return _merge_dicts(settings, stored)


def save_settings(search_root: Path, updates: dict[str, Any]) -> dict[str, Any]:
    settings = _merge_dicts(load_settings(search_root), updates)
    path = _settings_path(search_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return settings


def serialize_settings_for_ui(settings: dict[str, Any]) -> dict[str, Any]:
    ollama = settings.get("providers", {}).get("ollama", {})
    aristotle = settings.get("engines", {}).get("aristotle", {})
    api_key = str(aristotle.get("api_key") or "")
    return {
        "providers": {
            "ollama": {
                "base_url": str(ollama.get("base_url") or DEFAULT_SETTINGS["providers"]["ollama"]["base_url"]),
            },
        },
        "engines": {
            "aristotle": {
                "has_api_key": bool(api_key.strip()),
                "api_key_preview": (
                    f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) >= 8 else ("saved" if api_key else "")
                ),
            },
        },
    }
