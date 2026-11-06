import ctypes
import unittest
from unittest.mock import patch
from types import SimpleNamespace

try:
    import game_input
except ModuleNotFoundError:
    game_input = None


class GameInputTests(unittest.TestCase):
    def test_f8_emergency_stop_checks_current_key_state(self):
        check = getattr(game_input, 'emergency_stop_pressed', None)
        self.assertIsNotNone(check, 'Emergency stop must work outside tool focus')
        for value, expected in ((0, False), (0x8000, True)):
            native = SimpleNamespace(GetAsyncKeyState=lambda key: value if key == 0x77 else 0)
            with patch.object(game_input, '_user32', native):
                self.assertEqual(check(), expected)

    def test_space_uses_held_scancode_input(self):
        events = []

        def send(count, pointer, size):
            event = ctypes.cast(pointer, ctypes.POINTER(game_input.INPUT)).contents
            events.append((event.ki.wScan, event.ki.dwFlags))
            return 1

        with patch.object(game_input, '_send_input', side_effect=send), \
             patch.object(game_input.time, 'sleep'):
            press = getattr(game_input, 'press_space', None)
            self.assertIsNotNone(press, 'Jump needs scan-code input like Ready')
            press()
        self.assertEqual(events, [(0x39, 0x8), (0x39, 0xA)])

    def test_focus_restores_fortnite_window(self):
        actions = []

        def enum(callback, data):
            for hwnd in (10, 11, 12, 20):
                if not callback(hwnd, data):
                    break
            return 1

        def title(hwnd, buffer, size):
            buffer.value = {10: 'Another app', 11: 'Fortnite_AutoQueue_v3',
                            12: 'Fortnite Auto-Queue | Bildschirmmodus',
                            20: 'Fortnite  '}[hwnd]
            return len(buffer.value)

        native = SimpleNamespace(
            EnumWindows=enum, IsWindowVisible=lambda hwnd: True,
            GetWindowTextW=title, IsIconic=lambda hwnd: True,
            ShowWindow=lambda hwnd, flag: actions.append(('restore', hwnd, flag)),
            SetForegroundWindow=lambda hwnd: actions.append(('focus', hwnd)),
        )
        with patch.object(game_input, '_user32', native), \
             patch.object(game_input, 'game_has_focus', return_value=True):
            focus = getattr(game_input, 'focus_game', None)
            self.assertIsNotNone(focus, 'Start must be able to focus Fortnite')
            self.assertTrue(focus())
        self.assertEqual(actions, [('restore', 20, 9), ('focus', 20)])

    def test_folder_and_tool_are_not_treated_as_focused_game(self):
        for title in ('Fortnite_AutoQueue_v3', 'Fortnite Auto-Queue | Bildschirmmodus', 'Fortnite  '):
            with self.subTest(title=title):
                def read_title(hwnd, buffer, size):
                    buffer.value = title
                    return len(title)
                native = SimpleNamespace(GetForegroundWindow=lambda: 20,
                                         GetWindowTextW=read_title)
                with patch.object(game_input, '_user32', native):
                    self.assertEqual(game_input.game_has_focus(), title == 'Fortnite  ')

    def test_p_uses_scancode_with_hold_and_release(self):
        self.assertIsNotNone(game_input, 'Missing game keyboard backend')
        events = []

        def send(count, pointer, size):
            event = ctypes.cast(pointer, ctypes.POINTER(game_input.INPUT)).contents
            events.append((event.type, event.ki.wVk, event.ki.wScan, event.ki.dwFlags, size))
            return 1

        with patch.object(game_input, '_send_input', side_effect=send), \
             patch.object(game_input.time, 'sleep') as hold:
            game_input.press_p()

        self.assertEqual([e[:4] for e in events], [(1, 0, 0x19, 0x8), (1, 0, 0x19, 0xA)])
        self.assertEqual(events[0][4], 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        self.assertGreaterEqual(hold.call_args.args[0], 0.15)

    def test_blocked_input_reports_error(self):
        self.assertIsNotNone(game_input, 'Missing game keyboard backend')
        with patch.object(game_input, '_send_input', return_value=0):
            with self.assertRaisesRegex(OSError, 'Windows'):
                game_input.press_p()

    def test_interrupted_hold_releases_key(self):
        self.assertIsNotNone(game_input, 'Missing game keyboard backend')
        flags = []

        def send(count, pointer, size):
            flags.append(ctypes.cast(pointer, ctypes.POINTER(game_input.INPUT)).contents.ki.dwFlags)
            return 1

        with patch.object(game_input, '_send_input', side_effect=send), \
             patch.object(game_input.time, 'sleep', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                game_input.press_p()
        self.assertEqual(flags, [0x8, 0xA])
