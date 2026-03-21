from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "codex_cli": {
        "id": "codex_cli",
        "label": "Codex",
        "command": "codex",
        "transport": "cli",
        "connect_command": ["ulam", "auth", "codex"],
        "connect_hint": "Run `ulam auth codex` to connect Codex the same way UlamAI does.",
        "models": [
            {"id": "gpt-5.4", "label": "gpt-5.4"},
            {"id": "gpt-5.4-mini", "label": "GPT-5.4-Mini"},
            {"id": "gpt-5.3-codex", "label": "gpt-5.3-codex"},
        ],
        "efforts": ["low", "medium", "high", "xhigh"],
        "default_model": "gpt-5.4",
        "default_effort": "medium",
        "native_effort": True,
        "native_continuation": True,
        "session_strategy": "capture_thread_id",
        "capabilities": ["chat", "project tools", "code agent"],
        "status_probe": "codex_auth_file",
    },
    "claude_cli": {
        "id": "claude_cli",
        "label": "Claude Code",
        "command": "claude",
        "transport": "cli",
        "connect_command": ["ulam", "auth", "claude"],
        "connect_hint": "Run `ulam auth claude` to connect Claude Code the same way UlamAI does.",
        "models": [
            {"id": "sonnet", "label": "Claude Sonnet (latest)"},
            {"id": "opus", "label": "Claude Opus (latest)"},
            {"id": "haiku", "label": "Claude Haiku (latest)"},
        ],
        "efforts": ["low", "medium", "high", "max"],
        "default_model": "sonnet",
        "default_effort": "medium",
        "native_effort": True,
        "native_continuation": True,
        "session_strategy": "assigned_session_id",
        "capabilities": ["chat", "project tools", "code agent"],
        "status_probe": "claude_auth_status",
    },
    "gemini_cli": {
        "id": "gemini_cli",
        "label": "Gemini CLI",
        "command": "gemini",
        "transport": "cli",
        "connect_command": ["ulam", "auth", "gemini"],
        "connect_hint": "Run `ulam auth gemini` to connect Gemini the same way UlamAI does.",
        "models": [
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
        ],
        "efforts": ["low", "medium", "high"],
        "default_model": "gemini-2.5-pro",
        "default_effort": "medium",
        "native_effort": False,
        "native_continuation": False,
        "session_strategy": "transcript_replay",
        "capabilities": ["chat", "project tools", "code agent"],
        "status_probe": "gemini_auth_heuristic",
    },
}


def _command_exists(command: str) -> str | None:
    return shutil.which(command)


def _codex_cache_path() -> Path:
    return Path.home() / ".codex" / "models_cache.json"


def _load_codex_models_from_cache() -> dict[str, Any] | None:
    cache_path = _codex_cache_path()
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        return None

    visible_models = [
        item
        for item in raw_models
        if isinstance(item, dict)
        and item.get("slug")
        and item.get("visibility") == "list"
    ]
    visible_models.sort(
        key=lambda item: (
            int(item.get("priority", 10_000)),
            str(item.get("display_name") or item.get("slug")),
        ),
    )

    selected = visible_models[:3]
    if not selected:
        return None

    models = [
        {
            "id": str(item["slug"]),
            "label": str(item.get("display_name") or item["slug"]),
        }
        for item in selected
    ]
    efforts = [
        str(level["effort"])
        for level in selected[0].get("supported_reasoning_levels", [])
        if isinstance(level, dict) and level.get("effort")
    ]

    return {
        "models": models,
        "efforts": efforts or ["low", "medium", "high", "xhigh"],
        "default_model": models[0]["id"],
        "default_effort": str(selected[0].get("default_reasoning_level") or "medium"),
    }


def _provider_catalog() -> dict[str, dict[str, Any]]:
    catalog = copy.deepcopy(PROVIDER_CATALOG)
    codex_overrides = _load_codex_models_from_cache()
    if codex_overrides:
        catalog["codex_cli"].update(codex_overrides)
    return catalog


def _detect_codex_auth() -> tuple[bool, str | None]:
    auth_path = Path.home() / ".codex" / "auth.json"
    if auth_path.exists():
        return True, str(auth_path)
    return False, None


def _detect_claude_auth() -> tuple[bool, str | None]:
    executable = _command_exists("claude")
    if not executable:
        return False, None
    try:
        completed = subprocess.run(
            [executable, "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False, None

    payload = completed.stdout.strip()
    if payload:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return False, None
        if parsed.get("loggedIn") is True:
            return True, parsed.get("authMethod") or "login"
    return False, None


def _detect_gemini_auth() -> tuple[bool, str | None]:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return True, "environment"
    config_candidates = [
        Path.home() / ".config" / "gemini",
        Path.home() / ".gemini",
    ]
    for candidate in config_candidates:
        if candidate.exists():
            return True, str(candidate)
    return False, None


def _probe_status(provider_id: str) -> tuple[str, bool, str | None]:
    catalog_entry = _provider_catalog()[provider_id]
    executable = _command_exists(str(catalog_entry["command"]))
    if not executable:
        return "unavailable", False, None

    probe = str(catalog_entry["status_probe"])
    if probe == "codex_auth_file":
        connected, detail = _detect_codex_auth()
    elif probe == "claude_auth_status":
        connected, detail = _detect_claude_auth()
    elif probe == "gemini_auth_heuristic":
        connected, detail = _detect_gemini_auth()
    else:
        connected, detail = False, None

    return ("ready" if connected else "disconnected"), connected, executable if detail is None else f"{executable} ({detail})"


def get_provider(provider_id: str) -> dict[str, Any] | None:
    provider = _provider_catalog().get(provider_id)
    if provider is None:
        return None
    return dict(provider)


def list_chat_providers() -> list[dict[str, Any]]:
    catalog = _provider_catalog()
    providers: list[dict[str, Any]] = []
    for provider_id, catalog_entry in catalog.items():
        status, connected, executable = _probe_status(provider_id)
        providers.append(
            {
                **catalog_entry,
                "status": status,
                "connected": connected,
                "available": status != "unavailable",
                "executable": executable,
            }
        )
    return providers


def validate_model(provider_id: str, model: str) -> bool:
    provider = _provider_catalog().get(provider_id)
    if provider is None:
        return False
    return any(item["id"] == model for item in provider["models"])


def validate_effort(provider_id: str, effort: str) -> bool:
    provider = _provider_catalog().get(provider_id)
    if provider is None:
        return False
    return effort in provider["efforts"]
