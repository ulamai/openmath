from pathlib import Path
import unittest

from openmath.backends.detection import build_doctor_report, detect_backends


class BackendDetectionTests(unittest.TestCase):
    def test_detect_backends_exposes_expected_cards(self) -> None:
        backends = detect_backends(Path.cwd())
        self.assertIn("native", backends)
        self.assertIn("ulam", backends)
        self.assertIn("aristotle", backends)
        self.assertIn("status", backends["native"])

    def test_doctor_report_contains_runtime(self) -> None:
        report = build_doctor_report(Path.cwd())
        self.assertIn("runtime", report)
        self.assertIn("python", report["runtime"])


if __name__ == "__main__":
    unittest.main()
