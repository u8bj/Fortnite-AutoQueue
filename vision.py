"""Pure offline image evidence: no screenshots, window access, or input injection."""
from dataclasses import dataclass
from pathlib import Path
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class Detection:
    name: str
    score: float
    position: tuple | None
    confirmed: bool
    streak: int


class TemplateDetector:
    """Cache templates for one configuration and match externally supplied BGR frames.

    Positions are screen-space centers. A below-threshold candidate still reports
    its best score/position, but cannot confirm. Recreate after template edits.
    Resized caches are replaced on resolution changes, bounding memory growth.
    """

    def __init__(self, base_dir: Path, config: dict):
        self._specs = {name: dict(spec) for name, spec in config.get('templates', {}).items()
                       if spec.get('enabled', True)}
        self._images = {}
        self._streaks = {name: 0 for name in self._specs}
        self._resized = {}
        self._screen_size = None
        for name, spec in self._specs.items():
            path = Path(base_dir) / spec.get('file', '')
            image = None
            if path.is_file():
                try:
                    # imdecode supports Windows paths containing non-ASCII names.
                    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is not None and spec.get('grayscale', False):
                        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                except (OSError, ValueError, cv2.error):
                    image = None
            self._images[name] = image if self._textured(image) else None

    @staticmethod
    def _textured(image):
        if image is None or image.size == 0 or min(image.shape[:2]) < 2:
            return False
        # A solid color can differ between channels yet has no spatial evidence.
        return bool(np.max(np.var(image.astype(np.float32), axis=(0, 1))) > 1e-6)

    def missing(self) -> list[str]:
        """Enabled cues with unreadable or spatially constant source templates."""
        return [name for name, image in self._images.items() if image is None]

    def reset(self):
        for name in self._streaks:
            self._streaks[name] = 0

    def _variants(self, name, width, height):
        if name in self._resized:
            return self._resized[name]
        spec, image = self._specs[name], self._images[name]
        variants = []
        if image is not None:
            try:
                rw, rh = spec.get('reference_size', [width, height])
                scales = spec.get('scales', [.95, 1.0, 1.05])
                seen = set()
                for scale in scales[:9]:
                    scale = float(scale)
                    if not math.isfinite(scale) or scale <= 0 or rw <= 0 or rh <= 0:
                        continue
                    tw = round(image.shape[1] * width / rw * scale)
                    th = round(image.shape[0] * height / rh * scale)
                    if (tw, th) in seen or tw < 2 or th < 2 or tw > width or th > height:
                        continue
                    seen.add((tw, th))
                    interpolation = cv2.INTER_AREA if tw < image.shape[1] or th < image.shape[0] else cv2.INTER_LINEAR
                    resized = cv2.resize(image, (tw, th), interpolation=interpolation)
                    if self._textured(resized):
                        variants.append(resized)
            except (TypeError, ValueError, OverflowError, cv2.error):
                variants = []
        self._resized[name] = variants
        return variants

    def detect(self, frame_bgr: np.ndarray) -> dict[str, Detection]:
        valid = (isinstance(frame_bgr, np.ndarray) and frame_bgr.ndim == 3
                 and frame_bgr.shape[2] == 3 and frame_bgr.dtype == np.uint8
                 and frame_bgr.shape[0] > 0 and frame_bgr.shape[1] > 0)
        if not valid:
            self.reset()
            return {name: Detection(name, 0.0, None, False, 0) for name in self._specs}
        height, width = frame_bgr.shape[:2]
        if self._screen_size != (width, height):
            self.reset()
            self._resized.clear()
            self._screen_size = (width, height)
        results = {}
        gray = None
        for name, spec in self._specs.items():
            score, position = 0.0, None
            try:
                x, y, w, h = map(float, spec.get('roi', [0, 0, 1, 1]))
                if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
                    raise ValueError('invalid ROI')
                x0, y0 = max(0, min(width, math.floor(x * width))), max(0, min(height, math.floor(y * height)))
                x1, y1 = max(0, min(width, math.ceil((x + w) * width))), max(0, min(height, math.ceil((y + h) * height)))
                source = frame_bgr
                if spec.get('grayscale', False):
                    if gray is None:
                        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                    source = gray
                roi = source[y0:y1, x0:x1]
                best = -float('inf')
                for template in self._variants(name, width, height):
                    th, tw = template.shape[:2]
                    if roi.shape[0] < th or roi.shape[1] < tw:
                        continue
                    correlation = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                    _, candidate, _, location = cv2.minMaxLoc(correlation)
                    if math.isfinite(candidate) and candidate > best:
                        best = candidate
                        score = max(-1.0, min(1.0, float(candidate)))
                        position = (x0 + location[0] + tw // 2, y0 + location[1] + th // 2)
                hit = position is not None and score >= float(spec.get('threshold', .85))
                confirmations = max(1, int(spec.get('confirmations', 2)))
            except (TypeError, ValueError, OverflowError, cv2.error):
                score, position, hit, confirmations = 0.0, None, False, 1
            self._streaks[name] = self._streaks[name] + 1 if hit else 0
            streak = self._streaks[name]
            results[name] = Detection(name, score, position, hit and streak >= confirmations, streak)
        return results
