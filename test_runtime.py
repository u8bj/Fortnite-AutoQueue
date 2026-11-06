from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

import runtime
import settings
from vision import Detection


class InputTests(unittest.TestCase):
    def test_return_click_targets_lobby_button_and_replay_is_not_an_action(self):
        mouse = SimpleNamespace(moveTo=Mock(), mouseDown=Mock(), mouseUp=Mock(), FAILSAFE=True)
        event = threading.Event()
        controller = runtime.InputController(event, backend=SimpleNamespace(game_has_focus=lambda: True), mouse=mouse)
        cues = {'return_lobby': Detection('return_lobby', .99, (1572, 476), True, 3),
                'replay': Detection('replay', .99, (1572, 560), True, 3)}
        with patch.object(event, 'wait', return_value=False):
            self.assertTrue(controller.execute('return_lobby', cues))
        self.assertEqual(mouse.moveTo.call_args.args, (1572, 476))
        with self.assertRaises(ValueError):
            controller.execute('replay', cues)
        mouse.mouseDown.assert_called_once()

    def test_stop_during_mouse_hold_always_releases_button(self):
        event = threading.Event()
        mouse = SimpleNamespace(moveTo=Mock(), mouseDown=Mock(), mouseUp=Mock(), FAILSAFE=True)
        controller = runtime.InputController(event, backend=SimpleNamespace(game_has_focus=lambda: True), mouse=mouse)
        with patch.object(event, 'wait', side_effect=[False, True]):
            self.assertTrue(controller.execute('skip', {'skip': Detection('skip', .99, (100, 100), True, 3)}))
        mouse.mouseUp.assert_called_once()
        self.assertTrue(mouse.FAILSAFE)

    def test_no_keyboard_input_when_unfocused_or_stopped(self):
        for focused, stopped in ((False, False), (True, True)):
            backend = SimpleNamespace(game_has_focus=lambda: focused, press_p=Mock(), press_space=Mock())
            event = threading.Event()
            if stopped:
                event.set()
            controller = runtime.InputController(event, backend=backend)
            self.assertFalse(controller.execute('ready', {}))
            backend.press_p.assert_not_called()

    def test_focus_lost_during_move_prevents_mouse_down(self):
        backend = SimpleNamespace(game_has_focus=Mock(side_effect=[True, False]))
        mouse = SimpleNamespace(moveTo=Mock(), mouseDown=Mock(), mouseUp=Mock(), FAILSAFE=True)
        controller = runtime.InputController(threading.Event(), backend=backend, mouse=mouse)
        cue = Detection('skip', .99, (100, 200), True, 3)
        self.assertFalse(controller.execute('skip', {'skip': cue}))
        mouse.mouseDown.assert_not_called()

    def test_unconfirmed_button_never_clicked(self):
        backend = SimpleNamespace(game_has_focus=lambda: True)
        mouse = SimpleNamespace(moveTo=Mock())
        controller = runtime.InputController(threading.Event(), backend=backend, mouse=mouse)
        cue = Detection('return_lobby', .8, (100, 200), False, 1)
        self.assertFalse(controller.execute('return_lobby', {'return_lobby': cue}))
        mouse.moveTo.assert_not_called()


class RuntimeTests(unittest.TestCase):
    def test_confirmed_final_screen_is_team_end_only_without_live_veto(self):
        for blocker in (None, 'spectating', 'teammate_alive', 'jump', 'in_match'):
            with self.subTest(blocker=blocker), tempfile.TemporaryDirectory() as folder:
                config = settings.default_config()
                config['team_end_from_results'] = True
                app = runtime.QueueRuntime(Path(folder), config, lambda value: None,
                                           backend=SimpleNamespace(game_has_focus=lambda: True))
                try:
                    cues = {'placement', 'match_summary', 'return_lobby'}
                    if blocker:
                        cues.add(blocker)
                    app.detector = SimpleNamespace(detect=lambda frame: {
                        name: Detection(name, .99, (50, 50), True, 3) for name in cues})
                    app.inputs.execute = Mock(return_value=True)
                    app.engine.reset(0)
                    frame = np.zeros((100, 100, 3), np.uint8)
                    for now in range(3):
                        app.process_frame(frame, now)
                    if blocker:
                        app.inputs.execute.assert_not_called()
                    else:
                        self.assertEqual(app.inputs.execute.call_args.args[0], 'return_lobby')
                        app.inputs.execute.assert_called_once()
                finally:
                    app.close()

    def test_state_timeout_does_not_stop_the_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None)
            calls = []

            def process(frame, now):
                calls.append(now)
                if len(calls) == 1:
                    app.engine.fail('Timeout while finding current screen', now)
                else:
                    app.stop_event.set()

            try:
                with patch.object(runtime, 'screenshot_bgr', return_value=np.zeros((20, 30, 3), np.uint8)), \
                     patch.object(app, 'process_frame', side_effect=process), \
                     patch.object(app.stop_event, 'wait', return_value=False):
                    app._worker()
                self.assertEqual(len(calls), 2)
            finally:
                app.close()

    def test_stop_before_dispatch_does_not_consume_unsent_ready_or_space(self):
        for cues, action in ((('lobby', 'play'), 'ready'), (('jump',), 'jump')):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None,
                                           backend=SimpleNamespace(game_has_focus=lambda: True))
                try:
                    app.mode_confirmed = True
                    app.engine.reset(0)
                    app.detector = SimpleNamespace(detect=lambda frame: {
                        name: Detection(name, .99, (20, 30), True, 3) for name in cues})

                    def cancel_before_dispatch(*args):
                        app.stop_event.set()
                        return False

                    app.inputs.execute = Mock(side_effect=cancel_before_dispatch)
                    frame = np.zeros((20, 30, 3), np.uint8)
                    app.process_frame(frame, 0)
                    app.stop_event.clear()
                    app.engine.resume(1)
                    app.inputs.execute = Mock(return_value=True)
                    app.process_frame(frame, 1)
                    app.process_frame(frame, 2)
                    self.assertEqual(app.last_executed_action, action)
                    app.inputs.execute.assert_called_once()
                finally:
                    app.close()

    def test_real_input_success_does_not_wait_for_falling_or_glider(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = []
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None,
                backend=SimpleNamespace(game_has_focus=lambda: True, press_space=lambda: actions.append('space')))
            app.engine.reset(0)
            app.detector = SimpleNamespace(detect=lambda frame: {'jump': Detection('jump', .99, (100, 100), True, 2)})
            with patch.object(runtime.pyautogui, 'failSafeCheck'):
                app.process_frame(np.zeros((200, 300, 3), np.uint8), 0)
            app.detector = SimpleNamespace(detect=lambda frame: {})
            app.process_frame(np.zeros((200, 300, 3), np.uint8), 30)
            self.assertEqual(actions, ['space'])
            self.assertEqual(app.engine.state.value, 'IN_MATCH')
            self.assertEqual(app.engine.error, '')
            app.close()

    def test_hotkey_watcher_stops_without_needing_a_screenshot(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None,
                                       backend=SimpleNamespace(emergency_stop_pressed=lambda: True))
            app._watch_stop()
            self.assertTrue(app.stop_event.is_set())
            app.close()

    def test_cancelled_input_waits_for_resync_instead_of_stopping(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None,
                                       backend=SimpleNamespace(game_has_focus=lambda: True))
            app.mode_confirmed = True
            app.engine.reset(0)
            app.detector = SimpleNamespace(detect=lambda frame: {
                name: Detection(name, .99, (20, 30), True, 3) for name in ('lobby', 'play')})
            app.inputs.execute = Mock(return_value=False)
            snapshot = app.process_frame(np.zeros((20, 30, 3), np.uint8), 1)
            self.assertEqual(app.engine.state.value, 'DETECTING')
            self.assertEqual(app.engine.rounds, 0)
            self.assertTrue(app.engine.error)
            self.assertEqual(snapshot['last_action'], '')
            self.assertFalse(app.stop_event.is_set())
            app.close()

    def test_missing_lobby_templates_still_allow_midmatch_monitoring(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), events.append)
            with patch.object(runtime.threading, 'Thread') as thread:
                self.assertTrue(app.start(mode_confirmed=False))
                self.assertEqual(thread.call_count, 2)
            self.assertTrue(any(e['type'] == 'warning' and 'lobby' in e['text'] for e in events))
            app.thread = None
            app.hotkey_thread = None
            app.close()

    def test_one_screenshot_failure_retries_and_keeps_stop_available(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), events.append)
            frames = []

            def process(frame, now):
                frames.append(frame)
                app.stop_event.set()  # Stand-in for an explicit manual stop after recovery.

            with patch.object(runtime, 'screenshot_bgr', side_effect=[OSError('capture temporarily unavailable'), np.zeros((20, 30, 3), np.uint8)]), \
                 patch.object(app, 'process_frame', side_effect=process), \
                 patch.object(app.stop_event, 'wait', return_value=False):
                app._worker()
            self.assertEqual(len(frames), 1)
            self.assertTrue(any(e['type'] == 'warning' for e in events))
            app.close()

    def test_first_possible_alive_hit_vetoes_confirmed_result_button(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None,
                backend=SimpleNamespace(game_has_focus=lambda: True))
            app.engine.reset(0)
            app.engine.step({'team_eliminated', 'placement'}, 0)
            app.detector = SimpleNamespace(detect=lambda frame: {
                'teammate_alive': Detection('teammate_alive', .99, (10, 10), False, 1),
                'skip': Detection('skip', .99, (100, 100), True, 3)})
            app.inputs.execute = Mock(return_value=True)
            app.process_frame(np.zeros((200, 300, 3), np.uint8), 1)
            app.inputs.execute.assert_not_called()
            self.assertEqual(app.engine.state.value, 'SPECTATING')
            app.close()

    def test_worker_uses_proven_p_backend_and_reports_failed_input(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            cfg = settings.default_config()
            backend = SimpleNamespace(game_has_focus=lambda: True, press_p=Mock(), press_space=Mock())
            app = runtime.QueueRuntime(Path(folder), cfg, events.append, backend=backend)
            app.mode_confirmed = True
            app.engine.reset(0)
            app.detector = SimpleNamespace(detect=lambda frame: {
                name: Detection(name, .99, (20, 30), True, 3) for name in ('lobby', 'play')}, reset=lambda: None)
            frame = np.zeros((200, 300, 3), np.uint8)
            app.process_frame(frame, 1)
            app.process_frame(frame, 2)
            backend.press_p.assert_called_once()
            self.assertEqual(app.engine.rounds, 0, 'Submission must not count as confirmed round')
            self.assertTrue(events)
            app.close()

    def test_fresh_start_not_allowed_while_old_thread_is_alive(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None)
            app.thread = SimpleNamespace(is_alive=lambda: True)
            self.assertFalse(app.start())
            app.thread = None
            app.close()

    def test_fresh_start_waits_for_old_hotkey_watcher(self):
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), settings.default_config(), lambda value: None)
            app.hotkey_thread = SimpleNamespace(is_alive=lambda: True)
            with patch.object(runtime.threading, 'Thread'):
                self.assertFalse(app.start())
            app.hotkey_thread = None
            app.close()

    def test_mode_requires_manual_confirmation_or_all_four_visual_cues(self):
        cfg = settings.default_config()
        with tempfile.TemporaryDirectory() as folder:
            app = runtime.QueueRuntime(Path(folder), cfg, lambda value: None)
            self.assertFalse(app.mode_ok(set()))
            app.mode_confirmed = True
            self.assertTrue(app.mode_ok(set()))
            app.config['mode_check'] = 'templates'
            self.assertFalse(app.mode_ok({'mode_zero_build', 'mode_squads', 'mode_unranked'}))
            self.assertTrue(app.mode_ok({'mode_zero_build', 'mode_squads', 'mode_unranked', 'mode_fill'}))
            app.close()
