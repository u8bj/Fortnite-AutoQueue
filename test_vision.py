"""Offline detector mechanics. Artificial scenes do not establish game accuracy."""
from pathlib import Path
import importlib.util
import unittest
import tempfile
import cv2
import numpy as np

ROOT = Path(__file__).parent
FIXTURES = ROOT / 'tests' / 'fixtures'


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('vision'), 'vision detector is not implemented')
        from vision import TemplateDetector
        self.detector_class = TemplateDetector

    def detector(self, **overrides):
        cue = dict(file='tests/fixtures/synthetic_cue.png', enabled=True,
                   roi=[.5, .5, .5, .5], threshold=.95, confirmations=2,
                   reference_size=[640, 360], scales=[1.0])
        cue.update(overrides)
        return self.detector_class(ROOT, {'templates': {'cue': cue}})

    def frame(self, name='synthetic_hit_640.png'):
        image = cv2.imread(str(FIXTURES / name))
        self.assertIsNotNone(image)
        return image

    def test_hit_confirms_only_after_consecutive_frames_and_reset(self):
        detector = self.detector()
        first = detector.detect(self.frame())['cue']
        self.assertEqual((first.name, first.position, first.confirmed, first.streak),
                         ('cue', (424, 252), False, 1))
        self.assertGreater(first.score, .99)
        second = detector.detect(self.frame())['cue']
        self.assertTrue(second.confirmed)
        self.assertEqual(second.streak, 2)
        detector.detect(self.frame('synthetic_miss.png'))
        self.assertFalse(detector.detect(self.frame())['cue'].confirmed)
        detector.reset()
        self.assertEqual(detector.detect(self.frame())['cue'].streak, 1)

    def test_roi_excludes_identical_cue_outside_region(self):
        result = self.detector().detect(self.frame('synthetic_outside_roi.png'))['cue']
        self.assertFalse(result.confirmed)
        self.assertEqual(result.streak, 0)

    def test_resolution_scaling_in_both_axes(self):
        for filename, position in [('synthetic_downscale_320.png', (212, 126)),
                                   ('synthetic_upscale_1280.png', (848, 504)),
                                   ('synthetic_nonuniform_960.png', (636, 252))]:
            with self.subTest(filename=filename):
                result = self.detector(confirmations=1).detect(self.frame(filename))['cue']
                self.assertTrue(result.confirmed)
                self.assertEqual(result.position, position)

    def test_resolution_change_restarts_temporal_confirmation(self):
        detector = self.detector(confirmations=2)
        self.assertEqual(detector.detect(self.frame())['cue'].streak, 1)
        resized_first = detector.detect(self.frame('synthetic_upscale_1280.png'))['cue']
        self.assertEqual(resized_first.streak, 1)
        self.assertFalse(resized_first.confirmed)
        resized_second = detector.detect(self.frame('synthetic_upscale_1280.png'))['cue']
        self.assertEqual(resized_second.streak, 2)
        self.assertTrue(resized_second.confirmed)

    def test_tolerance_scales_and_best_below_threshold_score(self):
        frame = self.frame('synthetic_tolerance.png')
        result = self.detector(scales=[.9, 1, 1.1], confirmations=1).detect(frame)['cue']
        self.assertTrue(result.confirmed)
        self.assertEqual(result.position, (426, 253))
        miss = self.detector(scales=[1]).detect(frame)['cue']
        self.assertGreater(miss.score, 0)
        self.assertLess(miss.score, .95)
        self.assertFalse(miss.confirmed)

    def test_missing_and_constant_templates_never_confirm(self):
        for file in ['does_not_exist.png', 'tests/fixtures/constant_invalid.png']:
            with self.subTest(file=file):
                detector = self.detector(file=file, threshold=0, confirmations=1)
                self.assertEqual(detector.missing(), ['cue'])
                result = detector.detect(self.frame())['cue']
                self.assertEqual((result.score, result.position, result.confirmed, result.streak),
                                 (0, None, False, 0))

    def test_disabled_cues_are_omitted(self):
        detector = self.detector(enabled=False, file='does_not_exist.png')
        self.assertEqual(detector.missing(), [])
        self.assertEqual(detector.detect(self.frame()), {})

    def test_grayscale_and_invalid_frames_do_not_keep_confirmation(self):
        detector = self.detector(grayscale=True, confirmations=1)
        self.assertTrue(detector.detect(self.frame())['cue'].confirmed)
        for bad in [None, np.empty((0, 0, 3), np.uint8), np.zeros((10, 10), np.uint8)]:
            result = detector.detect(bad)['cue']
            self.assertEqual((result.position, result.confirmed, result.streak), (None, False, 0))

    def test_too_large_template_and_empty_roi_cannot_confirm(self):
        for overrides in [dict(roi=[0, 0, .01, .01]), dict(roi=[1, 1, .2, .2]),
                          dict(scales=[100]), dict(scales=[0, -1])]:
            with self.subTest(overrides=overrides):
                result = self.detector(confirmations=1, threshold=0, **overrides).detect(self.frame())['cue']
                self.assertEqual((result.score, result.position, result.confirmed), (0, None, False))

    def test_cached_template_remains_usable_without_disk_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'cue.png'
            path.write_bytes((FIXTURES / 'synthetic_cue.png').read_bytes())
            detector = self.detector_class(Path(temporary), {'templates': {'cue': dict(
                file='cue.png', roi=[.5, .5, .5, .5], confirmations=1,
                threshold=.95, reference_size=[640, 360], scales=[1])}})
            self.assertTrue(detector.detect(self.frame())['cue'].confirmed)
            path.unlink()
            self.assertTrue(detector.detect(self.frame())['cue'].confirmed)
            self.assertTrue(detector.detect(self.frame('synthetic_downscale_320.png'))['cue'].confirmed)
            self.assertTrue(detector.detect(self.frame())['cue'].confirmed)

    def test_multiple_scale_hits_increment_streak_once_per_frame(self):
        detector = self.detector(scales=[.99, 1, 1.01], confirmations=3)
        self.assertEqual(detector.detect(self.frame())['cue'].streak, 1)
        self.assertFalse(detector.detect(self.frame())['cue'].confirmed)
        self.assertTrue(detector.detect(self.frame())['cue'].confirmed)

    def test_default_tolerance_and_corrupt_template(self):
        detector = self.detector_class(ROOT, {'templates': {'cue': dict(
            file='tests/fixtures/synthetic_cue.png', confirmations=1,
            threshold=.95, reference_size=[640, 360], roi=[.5, .5, .5, .5])}})
        self.assertTrue(detector.detect(self.frame())['cue'].confirmed)
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / 'bad.png').write_bytes(b'not an image')
            detector = self.detector_class(Path(temporary), {'templates': {'bad': dict(file='bad.png')}})
            self.assertEqual(detector.missing(), ['bad'])
            self.assertFalse(detector.detect(self.frame())['bad'].confirmed)


if __name__ == '__main__':
    unittest.main()
