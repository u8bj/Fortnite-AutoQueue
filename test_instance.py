from pathlib import Path
import tempfile
import unittest
from instance_lock import InstanceLock


class InstanceTests(unittest.TestCase):
    def test_only_one_process_handle_can_own_project_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = InstanceLock(Path(folder)), InstanceLock(Path(folder))
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()
