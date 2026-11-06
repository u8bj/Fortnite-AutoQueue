"""JSON-lines adapter around the unchanged Python queue engine. No Tkinter needed."""
import copy
import json
from pathlib import Path
import sys
import threading
import time

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import game_input
from instance_lock import InstanceLock
from runtime import QueueRuntime, screenshot_bgr
from settings import CUES, load_config, save_config, validate_config
from vision import TemplateDetector


class DesktopBridge:
    def __init__(self, base, emit, backend=game_input, runtime_factory=QueueRuntime):
        self.base = Path(base)
        self.emit = emit
        self.backend = backend
        self.factory = runtime_factory
        self.config, self.warning = load_config(self.base / 'config.json')
        self.runtime = self.factory(self.base, self.config, self.emit_runtime)

    def emit_runtime(self, event):
        if event.get('type') == 'status' and hasattr(self, 'runtime'):
            event = {**event, 'detections': [
                {'id': name, 'title': CUES[name][0], 'score': cue.score,
                 'confirmed': cue.confirmed, 'streak': cue.streak}
                for name, cue in self.runtime.last_detections.items()]}
        self.emit(event)

    def snapshot(self):
        missing = set(self.runtime.missing_templates)
        return {'ok': True, 'version': '0.2.0-preview', 'admin': self.backend.is_admin(),
                'config_warning': self.warning, 'missing_templates': sorted(missing),
                'poll_interval': self.config['poll_interval'], 'debug': self.config['debug'],
                'team_end_from_results': self.config.get('team_end_from_results', False),
                'running': self.runtime.busy, 'state': self.runtime.engine.state.value,
                'rounds': self.runtime.engine.rounds,
                'templates': [{'id': name, 'title': CUES[name][0], 'enabled': entry['enabled'],
                               'available': (self.base / entry['file']).is_file() and name not in missing}
                              for name, entry in self.config['templates'].items()]}

    def command(self, name, payload):
        if not isinstance(payload, dict):
            raise ValueError('Command payload must be an object.')
        if name == 'snapshot':
            return self.snapshot()
        if name == 'start':
            if payload.get('mode_confirmed') is not True:
                raise ValueError('Confirm the Fortnite mode before starting.')
            if self.warning:
                raise ValueError(self.warning)
            if not self.backend.is_admin():
                raise ValueError('For game automation, relaunch your terminal as administrator and run npm start. The design preview works without elevation.')
            if self.runtime.busy:
                raise ValueError('The engine is already running or still stopping.')
            if not self.backend.focus_game():
                raise ValueError('Fortnite was not found or could not be focused. Open Fortnite first.')
            if not self.runtime.start(mode_confirmed=True):
                raise ValueError('The engine could not start. Wait for the previous operation to finish.')
            return {'ok': True}
        if name == 'stop':
            self.runtime.stop()
            return {'ok': True}
        if name in ('set_debug', 'set_options'):
            if self.runtime.busy:
                raise ValueError('Stop the engine before changing settings.')
            draft = copy.deepcopy(self.config)
            if name == 'set_debug':
                if not isinstance(payload.get('enabled'), bool):
                    raise ValueError('Debug mode must be a boolean.')
                draft['debug'] = payload['enabled']
            else:
                for key in ('poll_interval', 'team_end_from_results'):
                    if key in payload:
                        draft[key] = payload[key]
            validate_config(draft)
            save_config(self.base / 'config.json', draft)
            self.config, self.warning = draft, ''
            # These options are read each tick; preserve the state machine and
            # its consumed input flags when changing them while stopped.
            self.runtime.config = draft
            return self.snapshot()
        if name == 'test':
            if self.runtime.busy:
                raise ValueError('Stop the engine before running a read-only recognition test.')
            self.emit({'type': 'log', 'text': 'Read-only test in 5 seconds. Switch to the game screen. No inputs will be sent.'})
            time.sleep(5)
            detector = TemplateDetector(self.base, self.config)
            for _ in range(max(entry['confirmations'] for entry in self.config['templates'].values())):
                detections = detector.detect(screenshot_bgr())
                time.sleep(.1)
            result = {'type': 'recognition', 'missing_templates': detector.missing(),
                      'detections': [{'id': name, 'title': CUES[name][0], 'score': cue.score,
                                      'confirmed': cue.confirmed, 'streak': cue.streak}
                                     for name, cue in detections.items()]}
            self.emit(result)
            return {'ok': True}
        raise ValueError('Unknown desktop command.')

    def close(self):
        self.runtime.close()


def main():
    output_lock = threading.Lock()
    def emit(value):
        with output_lock:
            print(json.dumps(value, ensure_ascii=True), flush=True)
    lock = InstanceLock(BASE)
    if not lock.acquire():
        emit({'type': 'boot_error', 'text': 'Another Auto-Queue window is already open. Close it, then reconnect.'})
        return 1
    bridge = None
    try:
        bridge = DesktopBridge(BASE, emit)
        emit({'type': 'ready', **bridge.snapshot()})
        for line in sys.stdin:
            request = {}
            try:
                if len(line) > 16384:
                    raise ValueError('Desktop request is too large.')
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Desktop request must be an object.')
                if request.get('command') == 'shutdown':
                    break
                result = bridge.command(request.get('command'), request.get('payload', {}))
                emit({'type': 'response', 'id': request.get('id'), 'result': result})
            except Exception as exc:
                emit({'type': 'response', 'id': request.get('id') if isinstance(request, dict) else None,
                      'error': str(exc)})
    except Exception as exc:
        emit({'type': 'boot_error', 'text': str(exc)})
        return 1
    finally:
        if bridge:
            bridge.close()
        lock.release()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
