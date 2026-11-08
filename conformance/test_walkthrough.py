"""The walkthrough is executable evidence, not a documentation example."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WalkthroughTests(unittest.TestCase):
    def test_violation_is_detected_corrected_and_verified(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/acima_walkthrough.py"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("before: clean ordering application", result.stdout)
        self.assertIn("ACIMA-D001", result.stdout)
        self.assertIn("after: 0 findings", result.stdout)
        self.assertIn("violation detected, corrected, and verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
