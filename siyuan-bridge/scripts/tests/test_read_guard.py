import os
import tempfile
import unittest

from scripts.guards.read_guard import ReadGuard
from scripts.core.errors import ConflictError, GuardError


class ReadGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.tmp.name, "guard.json")
        self.guard = ReadGuard(self.cache, ttl_seconds=1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reject_without_read(self):
        with self.assertRaises(GuardError):
            self.guard.ensure_write_allowed("doc-1", "20260227", "update", allow_unsafe=False)

    def test_allow_after_read(self):
        self.guard.register_read("doc-1", "20260227", "test")
        self.guard.ensure_write_allowed("doc-1", "20260227", "update", allow_unsafe=False)

    def test_conflict(self):
        self.guard.register_read("doc-1", "20260227", "test")
        with self.assertRaises(ConflictError):
            self.guard.ensure_write_allowed("doc-1", "20260228", "update", allow_unsafe=False)

    def test_allow_unsafe_bypass(self):
        self.guard.ensure_write_allowed("doc-1", "20260228", "update", allow_unsafe=True)


if __name__ == "__main__":
    unittest.main()
