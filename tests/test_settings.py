from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openmath.settings import load_settings, save_settings, serialize_settings_for_ui


class SettingsTests(unittest.TestCase):
    def test_save_and_load_settings_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_settings(
                root,
                {
                    "providers": {"ollama": {"base_url": "http://localhost:11434"}},
                    "engines": {"aristotle": {"api_key": "sk-live-12345678"}},
                },
            )
            settings = load_settings(root)

            self.assertEqual(settings["providers"]["ollama"]["base_url"], "http://localhost:11434")
            self.assertEqual(settings["engines"]["aristotle"]["api_key"], "sk-live-12345678")

    def test_serialize_settings_masks_aristotle_key(self) -> None:
        payload = serialize_settings_for_ui(
            {
                "providers": {"ollama": {"base_url": "http://127.0.0.1:11434"}},
                "engines": {"aristotle": {"api_key": "sk-live-12345678"}},
            }
        )

        self.assertEqual(payload["providers"]["ollama"]["base_url"], "http://127.0.0.1:11434")
        self.assertTrue(payload["engines"]["aristotle"]["has_api_key"])
        self.assertEqual(payload["engines"]["aristotle"]["api_key_preview"], "sk-l...5678")


if __name__ == "__main__":
    unittest.main()
