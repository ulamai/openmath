from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from openmath.agents.providers import get_provider, list_chat_providers, validate_effort, validate_model


class AgentProviderTests(unittest.TestCase):
    def test_codex_provider_uses_local_models_cache(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "models_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "slug": "gpt-5.4",
                                "display_name": "GPT-5.4",
                                "visibility": "list",
                                "priority": 1,
                                "default_reasoning_level": "high",
                                "supported_reasoning_levels": [
                                    {"effort": "low"},
                                    {"effort": "medium"},
                                    {"effort": "high"},
                                    {"effort": "xhigh"},
                                ],
                            },
                            {
                                "slug": "gpt-5.4-mini",
                                "display_name": "GPT-5.4 Mini",
                                "visibility": "list",
                                "priority": 2,
                            },
                            {
                                "slug": "gpt-5.3-codex",
                                "display_name": "GPT-5.3 Codex",
                                "visibility": "list",
                                "priority": 3,
                            },
                            {
                                "slug": "gpt-hidden",
                                "display_name": "Hidden",
                                "visibility": "hidden",
                                "priority": 0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch("openmath.agents.providers._codex_cache_path", return_value=cache_path):
                provider = get_provider("codex_cli")
                self.assertIsNotNone(provider)
                assert provider is not None
                self.assertEqual(
                    [model["id"] for model in provider["models"]],
                    ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"],
                )
                self.assertEqual(provider["default_model"], "gpt-5.4")
                self.assertEqual(provider["default_effort"], "high")
                self.assertTrue(validate_model("codex_cli", "gpt-5.4-mini"))
                self.assertTrue(validate_effort("codex_cli", "xhigh"))
                self.assertFalse(validate_model("codex_cli", "gpt-hidden"))

    def test_ollama_provider_uses_settings_base_url_and_detected_models(self) -> None:
        with patch(
            "openmath.agents.providers._load_ollama_models",
            return_value=[{"id": "qwen2.5-coder", "label": "qwen2.5-coder"}],
        ):
            provider = get_provider(
                "ollama",
                settings={"providers": {"ollama": {"base_url": "http://localhost:11434"}}},
            )
            providers = list_chat_providers(
                settings={"providers": {"ollama": {"base_url": "http://localhost:11434"}}}
            )

        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider["base_url"], "http://localhost:11434")
        self.assertEqual(provider["default_model"], "qwen2.5-coder")
        ollama = next(item for item in providers if item["id"] == "ollama")
        self.assertEqual(ollama["base_url"], "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
