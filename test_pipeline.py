"""Saved synthetic screenshots through real detector, engine and guarded inputs."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2

import runtime
import settings
from queue_engine import State

BASE = Path(__file__).resolve().parent
FIXTURES = BASE / 'tests' / 'fixtures' / 'lifecycle'


class PipelineTests(unittest.TestCase):
    def make_runtime(self, folder):
        cfg = settings.default_config()
        cfg['templates'] = json.loads((FIXTURES / 'config.json').read_text())['templates']
        actions = []
        backend = SimpleNamespace(game_has_focus=lambda: True, press_p=lambda: actions.append('ready'),
                                  press_space=lambda: actions.append('jump'))
        app = runtime.QueueRuntime(Path(folder), cfg, lambda value: None, backend=backend)
        from vision import TemplateDetector
        app.detector = TemplateDetector(BASE, cfg)
        mouse = SimpleNamespace(FAILSAFE=True, moveTo=lambda *args, **kwargs: None,
                                mouseDown=lambda **kwargs: actions.append('result_click'), mouseUp=lambda **kwargs: None)
        app.inputs.mouse = mouse
        app.mode_confirmed = True
        app.engine.reset(0)
        return app, actions

    def show(self, app, scene, now):
        frame = cv2.imread(str(FIXTURES / f'{scene}.png'))
        self.assertIsNotNone(frame)
        with patch.object(runtime.pyautogui, 'failSafeCheck'), patch.object(app.stop_event, 'wait', return_value=False):
            for index in range(3):
                app.process_frame(frame, now + index * .4)

    def test_saved_screenshots_full_loop_and_jump_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            app, actions = self.make_runtime(folder)
            self.show(app, 'lobby', 0)
            self.show(app, 'search', 2)
            self.show(app, 'loading', 4)
            self.show(app, 'bus', 6)
            self.show(app, 'bus', 8)
            self.assertEqual(actions, ['ready', 'jump'])
            self.show(app, 'jumped', 10)
            self.assertEqual(app.engine.state, State.IN_MATCH)
            self.show(app, 'spectating', 12)
            self.show(app, 'false_results_alive', 14)
            self.show(app, 'false_personal_summary', 16)
            self.assertEqual(actions, ['ready', 'jump'])
            self.show(app, 'team_end', 18)
            self.show(app, 'xp', 24)
            self.show(app, 'summary', 26)
            self.show(app, 'summary', 28)
            self.assertEqual(actions, ['ready', 'jump', 'result_click', 'result_click'])
            self.show(app, 'search', 30)
            self.assertEqual(app.engine.rounds, 1)
            self.show(app, 'lobby', 32)
            self.assertEqual(actions, ['ready', 'jump', 'result_click', 'result_click', 'ready'])
            self.show(app, 'search', 34)
            self.assertEqual(app.engine.rounds, 2)
            app.close()

    def test_original_ready_crops_still_trigger_preserved_p(self):
        if not (FIXTURES / 'legacy_lobby_composite.png').is_file():
            self.skipTest('Private legacy template composite is not distributed.')
        with tempfile.TemporaryDirectory() as folder:
            cfg = settings.default_config()
            actions = []
            backend = SimpleNamespace(game_has_focus=lambda: True, press_p=lambda: actions.append('p'))
            app = runtime.QueueRuntime(Path(folder), cfg, lambda value: None, backend=backend)
            from vision import TemplateDetector
            app.detector = TemplateDetector(BASE, cfg)
            app.mode_confirmed = True
            frame = cv2.imread(str(FIXTURES / 'legacy_lobby_composite.png'))
            with patch.object(runtime.pyautogui, 'failSafeCheck'):
                for now in range(4):
                    app.process_frame(frame, now)
            self.assertEqual(actions, ['p'])
            app.close()
