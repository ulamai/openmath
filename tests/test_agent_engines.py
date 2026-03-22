from pathlib import Path
import unittest
from unittest.mock import patch

from openmath.agents.engines import get_chat_engine, list_chat_engines


class AgentEngineTests(unittest.TestCase):
    def test_list_chat_engines_exposes_expected_defaults(self) -> None:
        backend_state = {
            "native": {
                "id": "native",
                "label": "Native Lean backend",
                "status": "ready",
                "installed": True,
                "command": "lean/lake",
                "executable": "/usr/bin/lean",
                "version": "4.19.0",
                "notes": [],
            },
            "ulam": {
                "id": "ulam",
                "label": "UlamAI adapter",
                "status": "ready",
                "installed": True,
                "command": "ulam",
                "executable": "/usr/bin/ulam",
                "version": "0.1.0",
                "notes": [],
            },
            "aristotle": {
                "id": "aristotle",
                "label": "Aristotle adapter",
                "status": "missing",
                "installed": False,
                "command": "aristotle",
                "executable": None,
                "version": None,
                "notes": ["`aristotle` is not installed."],
            },
        }

        with patch("openmath.agents.engines.detect_backends", return_value=backend_state):
            engines = list_chat_engines(Path.cwd())

        self.assertEqual([engine["id"] for engine in engines], ["none", "ulam", "aristotle", "lean4_skills"])
        self.assertTrue(engines[0]["available"])
        self.assertEqual(engines[1]["connect_target_label"], "Connect to")
        self.assertFalse(engines[2]["available"])
        self.assertEqual(engines[3]["status"], "ready")

    def test_get_chat_engine_returns_matching_engine(self) -> None:
        with patch(
            "openmath.agents.engines.list_chat_engines",
            return_value=[{"id": "none"}, {"id": "ulam"}],
        ):
            self.assertEqual(get_chat_engine(Path.cwd(), "ulam"), {"id": "ulam"})
            self.assertIsNone(get_chat_engine(Path.cwd(), "missing"))

    def test_aristotle_engine_becomes_ready_when_api_key_is_present(self) -> None:
        backend_state = {
            "native": {"id": "native", "status": "missing", "installed": False, "command": "lean/lake", "executable": None, "version": None, "notes": []},
            "ulam": {"id": "ulam", "status": "missing", "installed": False, "command": "ulam", "executable": None, "version": None, "notes": []},
            "aristotle": {"id": "aristotle", "status": "missing", "installed": False, "command": "aristotle", "executable": None, "version": None, "notes": ["`aristotle` is not installed."]},
        }

        with patch("openmath.agents.engines.detect_backends", return_value=backend_state):
            aristotle = get_chat_engine(
                Path.cwd(),
                "aristotle",
                settings={"engines": {"aristotle": {"api_key": "sk-test-1234"}}},
            )

        self.assertIsNotNone(aristotle)
        assert aristotle is not None
        self.assertTrue(aristotle["available"])
        self.assertEqual(aristotle["status"], "ready")


if __name__ == "__main__":
    unittest.main()
