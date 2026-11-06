"""Preserved Windows scan-code shortcuts, exact game focus and emergency stop."""
import ctypes
from ctypes import wintypes
import time


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD),
                ('wParamH', wintypes.WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', wintypes.DWORD), ('data', INPUTUNION)]


_user32 = ctypes.WinDLL('user32', use_last_error=True)
_send_input = _user32.SendInput
_send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_send_input.restype = wintypes.UINT
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = (_enum_callback, wintypes.LPARAM)
_user32.IsWindowVisible.argtypes = (wintypes.HWND,)
_user32.IsIconic.argtypes = (wintypes.HWND,)
_user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
_user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_user32.GetAsyncKeyState.restype = wintypes.SHORT


def emergency_stop_pressed():
    return bool(_user32.GetAsyncKeyState(0x77) & 0x8000)  # F8


def is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def game_has_focus():
    title = ctypes.create_unicode_buffer(512)
    _user32.GetWindowTextW(_user32.GetForegroundWindow(), title, len(title))
    return title.value.strip().casefold() == 'fortnite'


def focus_game():
    windows = []

    @_enum_callback
    def find(hwnd, data):
        title = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, title, len(title))
        if _user32.IsWindowVisible(hwnd) and title.value.strip().casefold() == 'fortnite':
            windows.append(hwnd)
            return False
        return True

    _user32.EnumWindows(find, 0)
    if not windows:
        return False
    hwnd = windows[0]
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    _user32.SetForegroundWindow(hwnd)
    return game_has_focus()


def press_p():
    _press_scancode(0x19, 'P')


def press_space():
    _press_scancode(0x39, 'Space')


def _press_scancode(scan, label):
    down = INPUT(type=1, ki=KEYBDINPUT(wScan=scan, dwFlags=0x0008))
    up = INPUT(type=1, ki=KEYBDINPUT(wScan=scan, dwFlags=0x0008 | 0x0002))
    if _send_input(1, ctypes.byref(down), ctypes.sizeof(INPUT)) != 1:
        raise OSError(f'Windows blocked {label}. Check the privileges of the game and tool.')
    try:
        time.sleep(0.2)
    finally:
        if _send_input(1, ctypes.byref(up), ctypes.sizeof(INPUT)) != 1:
            raise OSError(f'Windows could not release {label}. Please press and release the key manually.')
