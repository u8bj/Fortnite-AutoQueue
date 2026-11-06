"""Real user screenshots found in Documents; all tests run without game input."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2

from queue_engine import Engine, State
from runtime import QueueRuntime
from settings import load_config
from vision import TemplateDetector

BASE = Path(__file__).resolve().parent
CAPTURES = BASE / 'tests' / 'captures'


class UserScreenshotTests(unittest.TestCase):
    def test_real_spectating_then_rebooted_scene_returns_to_match_without_input(self):
        with tempfile.TemporaryDirectory() as folder:
            app = QueueRuntime(Path(folder), self.config, lambda value: None,
                               backend=SimpleNamespace(game_has_focus=lambda: True))
            try:
                app.detector = TemplateDetector(BASE, self.config)
                app.engine.reset(0)
                actions = []
                app.inputs.execute = lambda action, found: actions.append(action) or True
                spectator = cv2.imread(str(CAPTURES / 'user-spectating.png'))
                rebooted = cv2.imread(str(CAPTURES / 'user-rebooted.png'))
                for now in range(5):
                    app.process_frame(spectator, now)
                self.assertEqual(app.engine.state, State.SPECTATING)
                for now in range(5, 10):
                    app.process_frame(rebooted, now)
                self.assertEqual(app.engine.state, State.IN_MATCH)
                for now in range(10, 15):
                    app.process_frame(spectator, now)
                self.assertEqual(app.engine.state, State.SPECTATING)
                self.assertEqual(actions, [])
            finally:
                app.close()

    def test_lobby_p_is_independent_of_changing_start_button_label(self):
        frame = cv2.imread(str(CAPTURES / 'user-lobby.png'))
        # Altered real screenshot: remove old SPIELEN label, representing a
        # changed button. Not claimed to be an independent BEREIT screenshot.
        frame[870:955, 90:430] = 0
        with tempfile.TemporaryDirectory() as folder:
            actions = []
            app = QueueRuntime(Path(folder), self.config, lambda value: None,
                               backend=SimpleNamespace(game_has_focus=lambda: True,
                                                       press_p=lambda: actions.append('p')))
            try:
                app.detector = TemplateDetector(BASE, self.config)
                app.engine.reset(0)
                app.mode_confirmed = True
                with patch('runtime.pyautogui.failSafeCheck'):
                    for now in range(5):
                        app.process_frame(frame, now)
                self.assertEqual(actions, ['p'])
            finally:
                app.close()

    def test_match_hud_before_bus_does_not_suppress_first_space(self):
        config = {**self.config, 'templates': {n: dict(s) for n, s in self.config['templates'].items()}}
        config['templates']['falling']['enabled'] = False
        with tempfile.TemporaryDirectory() as folder:
            actions = []
            app = QueueRuntime(Path(folder), config, lambda value: None,
                               backend=SimpleNamespace(game_has_focus=lambda: True,
                                                       press_space=lambda: actions.append('space')))
            try:
                app.detector = TemplateDetector(BASE, config)
                app.engine.reset(0)
                # Use only this real scene's HUD as a pre-bus HUD stand-in.
                # This is not claimed to be a captured waiting-island scene.
                hud = cv2.imread(str(CAPTURES / 'falling-observed.png'))
                bus = cv2.imread(str(CAPTURES / 'user-bus.png'))
                with patch('runtime.pyautogui.failSafeCheck'):
                    for now in range(3):
                        app.process_frame(hud, now)
                    self.assertEqual(app.engine.state, State.IN_MATCH)
                    self.assertEqual(actions, [])
                    for now in range(3, 8):
                        app.process_frame(bus, now)
                self.assertEqual(actions, ['space'])
            finally:
                app.close()

    def test_user_labelled_eliminated_screenshot_clicks_replay_once(self):
        cases = [('user-summary.png', 'return_lobby'), ('replay-20261103-050441.png', 'return_lobby'), ('user-xp.png', 'skip')]
        for filename, expected in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                frame = cv2.imread(str(CAPTURES / filename))
                app = QueueRuntime(Path(folder), self.config, lambda value: None,
                                   backend=SimpleNamespace(game_has_focus=lambda: True))
                try:
                    app.detector = TemplateDetector(BASE, self.config)
                    actions = []
                    app.inputs.execute = lambda action, detections: actions.append(action) or True
                    app.engine.reset(0)
                    for now in range(5):
                        app.process_frame(frame, now)
                    self.assertEqual(actions, [expected])
                finally:
                    app.close()

    def test_restart_midmatch_uses_hud_without_needing_falling_text(self):
        config = self.config.copy()
        config['templates'] = {name: dict(spec) for name, spec in self.config['templates'].items()}
        config['templates']['falling']['enabled'] = False
        detector = TemplateDetector(BASE, config)
        frame = cv2.imread(str(CAPTURES / 'falling-observed.png'))
        for _ in range(3):
            found = detector.detect(frame)
        self.assertIn('in_match', found)
        self.assertTrue(found['in_match'].confirmed)
        cues = {name for name, value in found.items() if value.confirmed}
        engine = Engine()
        self.assertEqual(engine.step(cues, 0), [])
        self.assertEqual(engine.state, State.IN_MATCH)
        self.assertEqual(engine.step(cues, 30), [])

    def test_game_hud_not_detected_in_lobby_or_bus(self):
        for filename in ('user-lobby.png', 'user-bus.png'):
            with self.subTest(filename=filename):
                found = self.detect(filename)
                self.assertIn('in_match', found)
                self.assertFalse(found['in_match'].confirmed)

    def test_observing_screen_enters_spectating_without_any_input(self):
        found = self.detect('user-spectating.png')
        self.assertIn('spectating', found)
        self.assertTrue(found['spectating'].confirmed)
        self.assertFalse(found['jump'].confirmed)
        cues = {name for name, detection in found.items() if detection.confirmed}
        self.assertNotIn('team_eliminated', cues)
        engine = Engine()
        self.assertEqual(engine.step({'jump'}, 0), ['jump'])
        engine.action_succeeded('jump', .2)
        self.assertEqual(engine.step(cues, 30), [])
        self.assertEqual(engine.state, State.SPECTATING)
        self.assertEqual(engine.step(cues | {'return_lobby'}, 31), [])
        self.assertEqual(engine.state, State.SPECTATING)

    def setUp(self):
        if not (BASE / 'config.json').is_file() or not CAPTURES.is_dir():
            self.skipTest('Private screenshot regressions require local captures and config.json; not distributed.')
        self.config, warning = load_config(BASE / 'config.json')
        self.assertFalse(warning)

    def detect(self, filename):
        detector = TemplateDetector(BASE, self.config)
        frame = cv2.imread(str(CAPTURES / filename))
        self.assertIsNotNone(frame)
        for _ in range(3):
            found = detector.detect(frame)
        return found

    def test_actual_prompt_and_buttons_have_correct_templates(self):
        for filename, cues in [('user-bus.png', ('jump',)),
                               ('user-xp.png', ('skip', 'placement')),
                               ('user-summary.png', ('return_lobby', 'placement', 'match_summary'))]:
            with self.subTest(filename=filename):
                found = self.detect(filename)
                for name in cues:
                    self.assertIn(name, found, f'{name} muss eingerichtet sein')
                    self.assertTrue(found[name].confirmed, f'{name}: score={found[name].score}')

    def test_bus_prompt_never_detected_in_other_real_screenshots(self):
        for filename in ('user-lobby.png', 'user-xp.png', 'user-summary.png', 'falling-observed.png'):
            with self.subTest(filename=filename):
                found = self.detect(filename)
                self.assertIn('jump', found)
                self.assertFalse(found['jump'].confirmed)

    def test_actual_bus_prompt_at_other_screen_sizes(self):
        original = cv2.imread(str(CAPTURES / 'user-bus.png'))
        for size in ((1920, 1080), (1650, 928)):
            with self.subTest(size=size):
                detector = TemplateDetector(BASE, self.config)
                frame = cv2.resize(original, size, interpolation=cv2.INTER_AREA)
                for _ in range(3):
                    found = detector.detect(frame)
                self.assertTrue(found['jump'].confirmed, f'jump at {size}: {found["jump"].score}')

    def test_actual_summary_alone_does_not_authorize_leaving_team(self):
        found = self.detect('user-summary.png')
        cues = {name for name, detection in found.items() if detection.confirmed}
        self.assertIn('return_lobby', cues)
        self.assertNotIn('team_eliminated', cues)
        engine = Engine()
        self.assertEqual(engine.step(cues, 0), [])
        self.assertNotEqual(engine.state, State.RETURNING_TO_LOBBY)

    def test_real_bus_to_real_falling_sends_exactly_one_space(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = []
            backend = SimpleNamespace(game_has_focus=lambda: True,
                                      press_space=lambda: actions.append('space'),
                                      press_p=lambda: actions.append('p'))
            runtime = QueueRuntime(Path(folder), self.config, lambda event: None, backend=backend)
            runtime.detector = TemplateDetector(BASE, self.config)
            runtime.engine.reset(0)
            try:
                with patch('runtime.pyautogui.failSafeCheck'):
                    bus = cv2.imread(str(CAPTURES / 'user-bus.png'))
                    falling = cv2.imread(str(CAPTURES / 'falling-observed.png'))
                    for now in range(6):
                        runtime.process_frame(bus, now)
                    self.assertEqual(actions, ['space'])
                    for now in range(6, 10):
                        runtime.process_frame(falling, now)
                self.assertEqual(actions, ['space'])
                self.assertEqual(runtime.engine.state, State.IN_MATCH)
            finally:
                runtime.close()
