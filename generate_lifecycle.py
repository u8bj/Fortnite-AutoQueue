"""Generate artificial lifecycle fixtures. NOT actual Fortnite screenshots."""
from pathlib import Path
import json
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / 'lifecycle'
NAMES = ['lobby', 'play', 'matchmaking', 'loading', 'jump', 'falling', 'own_dead',
         'spectating', 'teammate_alive', 'team_eliminated', 'placement', 'continue',
         'skip', 'match_summary', 'return_lobby']
SCENES = {'lobby': ['lobby', 'play'], 'search': ['matchmaking'], 'loading': ['loading'],
          'bus': ['jump'], 'jumped': ['falling'],
          'spectating': ['own_dead', 'spectating', 'teammate_alive'],
          'false_results_alive': ['match_summary', 'placement', 'return_lobby', 'teammate_alive'],
          'false_personal_summary': ['own_dead', 'match_summary', 'placement', 'return_lobby'],
          'team_end': ['team_eliminated', 'placement', 'continue'],
          'xp': ['skip'], 'summary': ['match_summary', 'return_lobby']}


def generate():
    OUT.mkdir(exist_ok=True)
    config = {'templates': {}}
    for index, name in enumerate(NAMES):
        rng = np.random.default_rng(500 + index)
        crop = rng.integers(20, 110, (36, 140, 3), dtype=np.uint8)
        cv2.putText(crop, name, (4, 24), cv2.FONT_HERSHEY_SIMPLEX, .4, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.imwrite(str(OUT / f'cue-{name}.png'), crop)
        x, y = 15 + (index % 4) * 155, 45 + (index // 4) * 65
        config['templates'][name] = dict(file=f'tests/fixtures/lifecycle/cue-{name}.png', enabled=True,
            roi=[x / 640, y / 360, 140 / 640, 36 / 360], reference_size=[640, 360],
            scales=[1], threshold=.98, confirmations=2, grayscale=False)
    for scene, cues in SCENES.items():
        frame = np.full((360, 640, 3), (18, 22, 27), np.uint8)
        cv2.putText(frame, 'SYNTHETIC TEST - NOT FORTNITE', (12, 22), cv2.FONT_HERSHEY_SIMPLEX, .5, (170, 170, 170), 1)
        for name in cues:
            index = NAMES.index(name)
            x, y = 15 + (index % 4) * 155, 45 + (index // 4) * 65
            frame[y:y+36, x:x+140] = cv2.imread(str(OUT / f'cue-{name}.png'))
        cv2.imwrite(str(OUT / f'{scene}.png'), frame)
    (OUT / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    # The optional legacy composite contains private game crops. Public builds
    # generate the fully synthetic fixtures above without requiring those crops.
    if not all((ROOT / 'templates' / f'{name}.png').is_file() for name in ('lobby', 'play')):
        return
    frame = np.full((1080, 1920, 3), (18, 22, 27), np.uint8)
    cv2.putText(frame, 'COMPOSITE TEST / ORIGINAL CROPS - NOT A LIVE SCREENSHOT', (500, 50), cv2.FONT_HERSHEY_SIMPLEX, .6, (180, 180, 180), 1)
    for name, x, y in [('lobby', 83, 592), ('play', 80, 862)]:
        crop = cv2.imread(str(ROOT / 'templates' / f'{name}.png'))
        h, w = crop.shape[:2]
        frame[y:y+h, x:x+w] = crop
    cv2.imwrite(str(OUT / 'legacy_lobby_composite.png'), frame)


if __name__ == '__main__':
    generate()
