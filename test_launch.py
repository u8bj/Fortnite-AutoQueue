import unittest
from unittest.mock import patch, Mock
import launch


class LauncherTests(unittest.TestCase):
    def test_nonadmin_requests_user_elevation(self):
        with patch.object(launch, 'ensure_dependencies'), patch.object(launch, 'is_admin', return_value=False), \
             patch.object(launch, 'elevate', return_value=42) as elevate, patch.object(launch.subprocess, 'run') as run:
            self.assertEqual(launch.main(), 0)
            elevate.assert_called_once()
            run.assert_not_called()

    def test_cancelled_elevation_does_not_start_unelevated_tool(self):
        with patch.object(launch, 'ensure_dependencies'), patch.object(launch, 'is_admin', return_value=False), \
             patch.object(launch, 'elevate', return_value=5), patch.object(launch.subprocess, 'run') as run:
            self.assertEqual(launch.main(), 1)
            run.assert_not_called()

    def test_elevated_launch_keeps_project_working_directory(self):
        with patch.object(launch, 'ensure_dependencies'), patch.object(launch, 'is_admin', return_value=True), \
             patch.object(launch.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(launch.main(), 0)
            self.assertEqual(run.call_args.kwargs['cwd'], str(launch.BASE))
            self.assertEqual(run.call_args.args[0][-1], str(launch.BASE / 'autoqueue.py'))
