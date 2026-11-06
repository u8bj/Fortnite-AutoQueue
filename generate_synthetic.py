"""Rebuild artificial detector test images; these are not Fortnite screenshots."""
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).parent
rng = np.random.default_rng(731)
template = rng.integers(0, 256, (24, 48, 3), dtype=np.uint8)
cv2.rectangle(template, (1, 1), (46, 22), (30, 220, 240), 2)
cv2.putText(template, 'TEST', (4, 17), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
cv2.imwrite(str(ROOT / 'synthetic_cue.png'), template)
cv2.imwrite(str(ROOT / 'constant_invalid.png'), np.full((24, 48, 3), 90, np.uint8))

def scene(name, width, height, x=None, y=None, tw=48, th=24):
    frame = np.full((height, width, 3), (21, 28, 34), np.uint8)
    cv2.putText(frame, 'SYNTHETIC TEST - NOT FORTNITE', (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .4, (160, 160, 160), 1)
    if x is not None:
        cue = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA if tw < 48 else cv2.INTER_LINEAR)
        frame[y:y + th, x:x + tw] = cue
    cv2.imwrite(str(ROOT / name), frame)

scene('synthetic_hit_640.png', 640, 360, 400, 240)
scene('synthetic_outside_roi.png', 640, 360, 100, 120)
scene('synthetic_miss.png', 640, 360)
scene('synthetic_downscale_320.png', 320, 180, 200, 120, 24, 12)
scene('synthetic_upscale_1280.png', 1280, 720, 800, 480, 96, 48)
scene('synthetic_nonuniform_960.png', 960, 360, 600, 240, 72, 24)
scene('synthetic_tolerance.png', 640, 360, 400, 240, 53, 26)
