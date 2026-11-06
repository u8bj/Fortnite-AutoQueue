"""Desktop protocol regressions: mocked engine and capture; no game input."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from desktop.bridge import DesktopBridge


class DesktopBridgeTests(unittest.TestCase):
    def make_bridge(self, root, admin=True, focused=True):
        runtime = SimpleNamespace(busy=False, missing_templates=[], config={},
                                  start=Mock(return_value=True), stop=Mock(), close=Mock(),
                                  engine=SimpleNamespace(state=SimpleNamespace(value='DETECTING'), rounds=0),
                                  last_executed_action='')
        backend = SimpleNamespace(is_admin=lambda: admin, focus_game=Mock(return_value=focused))
        return DesktopBridge(Path(root), lambda event: None, backend=backend,
                             runtime_factory=lambda *args: runtime), runtime, backend

    def test_start_needs_explicit_mode_confirmation_before_focus_or_input(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, backend = self.make_bridge(root)
            with self.assertRaisesRegex(ValueError, 'mode'):
                bridge.command('start', {'mode_confirmed': False})
            runtime.start.assert_not_called()
            backend.focus_game.assert_not_called()

    def test_unelevated_preview_never_sends_start_input(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, _ = self.make_bridge(root, admin=False)
            with self.assertRaisesRegex(ValueError, 'administrator'):
                bridge.command('start', {'mode_confirmed': True})
            runtime.start.assert_not_called()

    def test_start_focuses_game_and_preserves_existing_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, backend = self.make_bridge(root)
            result = bridge.command('start', {'mode_confirmed': True})
            self.assertTrue(result['ok'])
            backend.focus_game.assert_called_once()
            runtime.start.assert_called_once_with(mode_confirmed=True)

    def test_missing_game_blocks_start(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, _ = self.make_bridge(root, focused=False)
            with self.assertRaisesRegex(ValueError, 'Fortnite'):
                bridge.command('start', {'mode_confirmed': True})
            runtime.start.assert_not_called()

    def test_stop_and_invalid_requests_cannot_dispatch_unexpected_input(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, _ = self.make_bridge(root)
            self.assertTrue(bridge.command('stop', {})['ok'])
            runtime.stop.assert_called_once()
            for command, payload in [('exec', {}), ('start', []), ('set_debug', {'enabled': 'yes'})]:
                with self.assertRaises(ValueError):
                    bridge.command(command, payload)
            runtime.start.assert_not_called()

    def test_settings_cannot_be_changed_while_runtime_is_busy(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, _ = self.make_bridge(root)
            runtime.busy = True
            with self.assertRaisesRegex(ValueError, 'Stop'):
                bridge.command('set_options', {'poll_interval': .5})

    def test_settings_preserve_runtime_session_and_consumed_inputs(self):
        with tempfile.TemporaryDirectory() as root:
            bridge, runtime, _ = self.make_bridge(root)
            runtime.engine.rounds = 7
            result = bridge.command('set_options', {'poll_interval': .5})
            runtime.close.assert_not_called()
            self.assertIs(bridge.runtime, runtime)
            self.assertEqual(result['rounds'], 7)
            self.assertEqual(bridge.runtime.config['poll_interval'], .5)
