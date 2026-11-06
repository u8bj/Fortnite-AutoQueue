"""UI orchestration regressions; no real game input or screenshots."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import autoqueue
import settings

class AppTests(unittest.TestCase):
    def app(self):
        app = autoqueue.App.__new__(autoqueue.App)
        app.root = Mock()
        app.config = settings.default_config()
        app.config_warning = ''
        app.manual_mode = SimpleNamespace(get=lambda: True)
        app.runtime = SimpleNamespace(busy=False, start=Mock(return_value=True), stop=Mock())
        app.capture_pending = False
        return app

    def test_start_minimizes_and_focuses_before_runtime(self):
        app = self.app()
        actions = []
        app.root.iconify.side_effect = lambda: actions.append('minimize')
        app.runtime.start.side_effect = lambda **kwargs: actions.append('start') or True
        with patch.object(autoqueue.game_input, 'focus_game', side_effect=lambda: actions.append('focus')):
            app.start()
        self.assertEqual(actions, ['minimize', 'focus', 'start'])

    def test_unchecked_mode_allows_midmatch_monitoring_but_no_lobby_permission(self):
        app = self.app()
        app.manual_mode = SimpleNamespace(get=lambda: False)
        with patch.object(autoqueue.game_input, 'focus_game'):
            app.start()
        app.runtime.start.assert_called_once_with(mode_confirmed=False)

    def test_no_second_worker_while_previous_is_running(self):
        app = self.app()
        app.runtime.busy = True
        app.start()
        app.runtime.start.assert_not_called()
