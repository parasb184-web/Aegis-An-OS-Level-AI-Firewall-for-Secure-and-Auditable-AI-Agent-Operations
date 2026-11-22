"""Unit tests for the Aegis sliding-window risk scoring engine (risk.py)."""

import os
import sys
import time
import unittest

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import risk


class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        risk.history.clear()

    def tearDown(self):
        risk.history.clear()

    def test_baseline_score(self):
        """Unrecorded process should yield score of 0 with empty reason."""
        points, why = risk.score(9999)
        self.assertEqual(points, 0)
        self.assertEqual(why, "")
        self.assertFalse(risk.is_warning(points))
        self.assertFalse(risk.is_risky(points))

    def test_file_limit_threshold(self):
        """Opens at or below FILE_LIMIT (15) incur 0 points; 16th file incurs 40 points."""
        pid = 1001
        for i in range(risk.FILE_LIMIT):
            risk.record(pid, f"/demo/dir/file{i}.txt")
        points, _ = risk.score(pid)
        self.assertEqual(points, 0)

        # 16th file exceeds limit
        risk.record(pid, "/demo/dir/file_extra.txt")
        points, why = risk.score(pid)
        self.assertEqual(points, 40)
        self.assertIn("16 files", why)
        self.assertTrue(risk.is_risky(points))

    def test_folder_limit_threshold(self):
        """Accessing 5 distinct folders triggers +30 points."""
        pid = 1002
        for i in range(5):
            risk.record(pid, f"/demo/folder_{i}/file.txt")
        points, why = risk.score(pid)
        self.assertEqual(points, 30)
        self.assertIn("5 folders", why)
        self.assertTrue(risk.is_warning(points))
        self.assertFalse(risk.is_risky(points))

    def test_combined_limit_threshold(self):
        """Exceeding both file limit and folder limit results in 70 points."""
        pid = 1003
        for i in range(20):
            folder_idx = i % 5  # Spans 5 distinct folders
            risk.record(pid, f"/demo/folder_{folder_idx}/file_{i}.txt")
        points, why = risk.score(pid)
        self.assertEqual(points, 70)
        self.assertIn("20 files", why)
        self.assertIn("5 folders", why)
        self.assertTrue(risk.is_risky(points))

    def test_window_expiration(self):
        """Events older than WINDOW are trimmed away."""
        pid = 1004
        old_time = time.time() - (risk.WINDOW + 5.0)
        # Inject old events
        risk.history[pid] = [(old_time, f"/demo/folder/file_{i}.txt") for i in range(20)]
        risk.trim(time.time())
        self.assertNotIn(pid, risk.history)
        points, _ = risk.score(pid)
        self.assertEqual(points, 0)

    def test_forget_root(self):
        """forget() cleans up all tracked state for a given root PID."""
        pid = 1005
        risk.record(pid, "/demo/test.txt")
        self.assertIn(pid, risk.history)
        risk.forget(pid)
        self.assertNotIn(pid, risk.history)


if __name__ == "__main__":
    unittest.main()
