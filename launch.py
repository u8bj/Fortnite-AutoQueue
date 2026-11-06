"""Launcher: install only missing dependencies, request user-approved elevation."""
import ctypes
import importlib
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent


def ensure_dependencies():
    try:
        for module in ('cv2', 'numpy', 'PIL', 'pyautogui'):
            importlib.import_module(module)
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(BASE / 'requirements.txt')], check=True)


def is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def elevate():
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                   ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
    shell.ShellExecuteW.restype = ctypes.c_void_p
    arguments = subprocess.list2cmdline([str(BASE / 'autoqueue.py')])
    return shell.ShellExecuteW(None, 'runas', sys.executable, arguments, str(BASE), 1) or 0


def main():
    try:
        ensure_dependencies()
        if not is_admin():
            print('Fortnite and this tool need matching privileges. Please approve the Windows elevation prompt.')
            result = elevate()
            if result <= 32:
                print('Administrator launch cancelled or failed. The tool was not started.')
                return 1
            return 0
        return subprocess.run([sys.executable, str(BASE / 'autoqueue.py')], cwd=str(BASE)).returncode
    except Exception as exc:
        print(f'Launch failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
