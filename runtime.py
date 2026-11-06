"""Screenshot/engine/input integration. Worker events never touch Tk widgets."""
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import time

import cv2
import numpy as np
import pyautogui

import game_input
from queue_engine import Engine, State
from vision import TemplateDetector


ACTION_LABELS = {'ready': 'Pressed P once', 'jump': 'Pressed Space once',
                 'skip': 'Clicked Skip once', 'return_lobby': 'Clicked Return to Lobby once'}
MODE_CUES = {'mode_zero_build', 'mode_squads', 'mode_unranked', 'mode_fill'}


def screenshot_bgr():
    return cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)


class InputController:
    def __init__(self, stop_event, backend=game_input, mouse=pyautogui):
        self.stop_event = stop_event
        self.backend = backend
        self.mouse = mouse

    def allowed(self):
        return not self.stop_event.is_set() and self.backend.game_has_focus()

    def execute(self, action, detections):
        if not self.allowed():
            return False
        if action in ('ready', 'jump'):
            pyautogui.failSafeCheck()
            if not self.allowed():
                return False
            (self.backend.press_p if action == 'ready' else self.backend.press_space)()
            return True
        if action not in ('skip', 'return_lobby'):
            raise ValueError(f'Unknown action: {action}')
        target = detections.get(action)
        if not target or not target.confirmed or target.position is None:
            return False
        self.mouse.moveTo(*target.position, duration=.15)
        if self.stop_event.wait(.15) or not self.allowed():
            return False
        self.mouse.mouseDown(button='left')
        try:
            self.stop_event.wait(.2)
        finally:
            failsafe = self.mouse.FAILSAFE
            try:
                self.mouse.FAILSAFE = False
                self.mouse.mouseUp(button='left')
            finally:
                self.mouse.FAILSAFE = failsafe
        return True


class QueueRuntime:
    def __init__(self, base_dir, config, on_event, backend=game_input):
        self.base_dir = Path(base_dir)
        self.config = config
        self.on_event = on_event
        self.backend = backend
        self.stop_event = threading.Event()
        self.thread = None
        self.hotkey_thread = None
        self.mode_confirmed = False
        self.detector = TemplateDetector(self.base_dir, config)
        self.missing_templates = self.detector.missing()
        self.engine = Engine(config.get('timeouts'))
        self.inputs = InputController(self.stop_event, backend=backend)
        self.logs_dir = self.base_dir / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(f'autoqueue.{id(self)}')
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.handler = RotatingFileHandler(self.logs_dir / 'autoqueue.log', maxBytes=1_000_000,
                                          backupCount=3, encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s', datefmt='%H:%M:%S'))
        self.logger.addHandler(self.handler)
        self._last_state = None
        self._last_snapshot = None
        self._last_debug = 0.0
        self.last_frame = None
        self.last_detections = {}
        self.last_executed_action = ''
        self._last_warning = ''
        self._last_warning_at = -float('inf')
        self._last_error_debug = -float('inf')

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive() and not self.stop_event.is_set())

    @property
    def busy(self):
        return bool((self.thread and self.thread.is_alive()) or
                    (self.hotkey_thread and self.hotkey_thread.is_alive()))

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)
        self.on_event({'type': 'log', 'text': f'[{datetime.now():%H:%M:%S}] {message}'})

    def mode_ok(self, visible):
        return MODE_CUES <= visible if self.config['mode_check'] == 'templates' else self.mode_confirmed

    def start(self, mode_confirmed=False):
        if self.busy:
            return False
        if self.missing_templates:
            self.warn('Missing or invalid templates: ' + ', '.join(self.missing_templates) + '. Monitoring remains available.', time.monotonic())
        self.mode_confirmed = mode_confirmed
        self.stop_event.clear()
        self.detector.reset()
        self.engine.resume(time.monotonic())
        self._last_state = None
        self._last_snapshot = None
        self.thread = threading.Thread(target=self._worker, name='AutoQueue', daemon=True)
        self.thread.start()
        self.hotkey_thread = threading.Thread(target=self._watch_stop, name='AutoQueue-F8', daemon=True)
        self.hotkey_thread.start()
        return True

    def stop(self, reason='Stopped manually'):
        self.stop_event.set()
        self.log(reason)
        self.on_event({'type': 'active', 'active': False})

    def close(self):
        self.stop_event.set()
        if self.thread and hasattr(self.thread, 'join') and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        if self.hotkey_thread and self.hotkey_thread is not threading.current_thread():
            self.hotkey_thread.join(timeout=.3)
        if not self.busy:
            self.handler.close()
            self.logger.removeHandler(self.handler)

    def _watch_stop(self):
        while not self.stop_event.wait(.03):
            try:
                if self.backend.emergency_stop_pressed():
                    self.stop('Emergency stop F8')
                    break
            except Exception as exc:
                self.engine.fail(f'Emergency stop unavailable: {exc}', time.monotonic())
                self.stop('Safety stop: hotkey check failed')
                self.on_event({'type': 'error', 'text': self.engine.error})
                break

    def _worker(self):
        self.on_event({'type': 'active', 'active': True})
        self.log('Auto-Queue started; F8 = emergency stop')
        try:
            while not self.stop_event.is_set():
                started = time.monotonic()
                try:
                    frame = screenshot_bgr()
                    self.process_frame(frame, time.monotonic())
                    if self.engine.state == State.ERROR:
                        self.warn(self.engine.error, time.monotonic(), frame)
                except pyautogui.FailSafeException:
                    self.stop('Emergency stop: mouse in screen corner')
                    break
                except Exception as exc:
                    now = time.monotonic()
                    self.engine.fail(str(exc), now)
                    self.warn(f'Temporary error: {exc}. Continuing to monitor.', now, self.last_frame)
                    # Retry screenshots/detection, never blindly repeat an uncertain input.
                    if self.stop_event.wait(1):
                        break
                self.stop_event.wait(max(.02, self.config['poll_interval'] - (time.monotonic() - started)))
        finally:
            self.on_event({'type': 'active', 'active': False})

    def warn(self, message, now, frame=None):
        if message != self._last_warning or now - self._last_warning_at >= 30:
            self.log(message, logging.WARNING)
            self.on_event({'type': 'warning', 'text': message})
            self._last_warning = message
            self._last_warning_at = now
        if frame is not None and now - self._last_error_debug >= 30:
            try:
                self.save_debug(frame, message, force=True)
            except (OSError, cv2.error):
                self.logger.warning('Could not save debug image', exc_info=True)
            self._last_error_debug = now

    def process_frame(self, frame, now):
        self.last_frame = frame
        focused = self.backend.game_has_focus()
        if focused:
            detections = self.detector.detect(frame)
        else:
            self.detector.reset()
            detections = {}
        self.last_detections = detections
        visible = {name for name, detection in detections.items() if detection.confirmed}
        if 'ready_button' in visible or {'lobby', 'lobby_navigation'} <= visible:
            visible.add('play')
        # A possible living teammate is a conservative veto immediately. We never
        # wait for its confirmation while an already-confirmed result could click.
        alive = detections.get('teammate_alive')
        if alive and alive.position is not None and alive.score >= self.config['templates'].get('teammate_alive', {}).get('threshold', .9):
            visible.add('teammate_alive')
        # User identified eliminated.png as the final team-results screen.
        # Require separate stable result markers; observing/live context vetoes.
        if self.config.get('team_end_from_results', False):
            blockers = {'spectating', 'own_dead', 'teammate_alive', 'jump', 'in_match',
                        'falling', 'glider', 'lobby', 'play', 'matchmaking', 'loading'}
            summary = {'placement', 'match_summary'} <= visible and bool(visible & {'return_lobby', 'replay'})
            xp = {'placement', 'skip'} <= visible
            if (summary or xp) and not visible & blockers:
                visible.add('team_eliminated')
        actions = self.engine.step(visible, now, focused, self.mode_ok(visible))
        for action in actions:
            if action == 'jump':
                self.log('Battle Bus: jump prompt confirmed')
            if not self.inputs.execute(action, detections):
                # False guarantees no event was sent, including an F8 race.
                self.engine.action_cancelled(action, now)
                if self.stop_event.is_set():
                    break
                self.warn('Input not sent; waiting for focus and fresh visual confirmation.', now)
                break
            self.last_executed_action = action
            self.engine.action_succeeded(action, now)
            self.log(ACTION_LABELS[action])
        state = self.engine.state.value
        if state != self._last_state:
            if state == 'IN_MATCH' and self._last_state == 'JUMPING':
                self.log('Jump input completed – monitoring only')
            elif state == 'IN_MATCH' and self._last_state == 'SPECTATING':
                self.log('Return to active match detected – monitoring only')
            elif state == 'SPECTATING':
                self.log('Death/spectating detected; result actions require team elimination evidence')
            self.log(f'State: {state}')
            self._last_state = state
            if self.config.get('debug'):
                self.save_debug(frame, f'State {state}')
        snapshot = {'type': 'status', 'state': state, 'rounds': self.engine.rounds,
                    'last_action': ACTION_LABELS.get(self.last_executed_action, self.last_executed_action),
                    'error': self.engine.error, 'focused': focused, 'mode_ok': self.mode_ok(visible),
                    'visible': sorted(visible), 'scores': {n: round(d.score, 3) for n, d in detections.items()}}
        # Confidence details remain available in logs without flooding Tk at idle.
        if snapshot != self._last_snapshot:
            self.on_event(snapshot)
            self._last_snapshot = snapshot
        if self.config.get('debug') and now - self._last_debug >= 15:
            self.logger.debug('Recognition %s', snapshot['scores'])
            self.save_debug(frame, 'Check recognition')
            self._last_debug = now
        return snapshot

    def save_debug(self, frame, reason, force=False):
        if not force and not self.config.get('debug'):
            return None
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        path = self.logs_dir / f'debug-{stamp}.png'
        ok, encoded = cv2.imencode('.png', frame)
        if not ok:
            raise OSError('Could not encode debug screenshot')
        encoded.tofile(path)
        path.with_suffix('.json').write_text(json.dumps({
            'reason': reason, 'state': self.engine.state.value,
            'scores': {n: {'score': d.score, 'confirmed': d.confirmed, 'streak': d.streak}
                       for n, d in self.last_detections.items()}}, ensure_ascii=False, indent=2), encoding='utf-8')
        limit = self.config.get('debug_limit', 30)
        old = sorted(self.logs_dir.glob('debug-*.png'))[:-limit]
        for item in old:
            item.unlink(missing_ok=True)
            item.with_suffix('.json').unlink(missing_ok=True)
        return path
