"""Replay locally captured real screenshots, when available. No OS input."""
import json
from pathlib import Path
import unittest
import cv2
import numpy as np

from settings import load_config
from vision import TemplateDetector

BASE = Path(__file__).resolve().parent


class RealCaptureTests(unittest.TestCase):
    def test_real_bus_and_team_end_screens_are_available(self):
        expected = set()
        for path in (BASE / 'tests' / 'captures').glob('*.json'):
            cues = set(json.loads(path.read_text(encoding='utf-8')).get('expected', []))
            expected.update(cues)
            config, _ = load_config(BASE / 'config.json')
            if config.get('team_end_from_results') and {'placement', 'match_summary', 'replay'} <= cues:
                expected.add('team_eliminated')
        required = {'jump', 'team_eliminated', 'placement', 'skip', 'match_summary', 'replay'}
        if not required <= expected:
            self.skipTest('Echte Bus-/Team-/Ergebnis-Testbilder fehlen: ' + ', '.join(sorted(required - expected)))

    def test_supervised_capture_regressions(self):
        labels = sorted((BASE / 'tests' / 'captures').glob('*.json'))
        if not labels:
            self.skipTest('Keine echten beschrifteten Bus-/Ergebnis-Aufnahmen vorhanden; Live-Kalibrierung ausstehend.')
        config, warning = load_config(BASE / 'config.json')
        self.assertFalse(warning)
        for path in labels:
            with self.subTest(capture=path.name):
                metadata = json.loads(path.read_text(encoding='utf-8'))
                frame = cv2.imdecode(np.fromfile(path.with_suffix('.png'), dtype=np.uint8), cv2.IMREAD_COLOR)
                self.assertIsNotNone(frame)
                detector = TemplateDetector(BASE, config)
                count = max(spec['confirmations'] for spec in config['templates'].values())
                for _ in range(count):
                    found = detector.detect(frame)
                for name in metadata['expected']:
                    self.assertIn(name, found, 'Aufgenommene Vorlage nicht aktiviert')
                    self.assertTrue(found[name].confirmed, f'{name}: Confidence {found[name].score:.3f}')
