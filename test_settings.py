import json
from pathlib import Path
import tempfile
import unittest

import settings


class SettingsTests(unittest.TestCase):
    def test_unknown_timeout_cannot_crash_runtime_constructor(self):
        cfg = settings.default_config()
        cfg['timeouts']['TYPO'] = 30
        with self.assertRaises(ValueError):
            settings.validate_config(cfg)

    def test_unsafe_old_crops_are_disabled_but_ready_is_preserved(self):
        cfg = settings.default_config()
        self.assertTrue(cfg['templates']['lobby']['enabled'])
        self.assertTrue(cfg['templates']['play']['enabled'])
        for name in ('jump', 'skip', 'replay'):
            self.assertFalse(cfg['templates'][name]['enabled'])

    def test_invalid_roi_and_single_frame_confirmation_rejected(self):
        for key, value in [('roi', [.9, 0, .5, 1]), ('confirmations', 1), ('threshold', 1.1)]:
            cfg = settings.default_config()
            cfg['templates']['play'][key] = value
            with self.assertRaises(ValueError):
                settings.validate_config(cfg)

    def test_configuration_roundtrip_and_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            cfg = settings.default_config()
            cfg['debug'] = True
            settings.save_config(path, cfg)
            loaded, warning = settings.load_config(path)
            self.assertTrue(loaded['debug'])
            self.assertFalse(warning)
            path.write_text('{broken', encoding='utf-8')
            loaded, warning = settings.load_config(path)
            self.assertTrue(warning)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')
            self.assertFalse(loaded['debug'])

    def test_outside_template_path_is_rejected(self):
        cfg = settings.default_config()
        cfg['templates']['play']['file'] = '../private.png'
        with self.assertRaises(ValueError):
            settings.validate_config(cfg)
