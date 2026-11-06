"""OS-backed project lock; released by Windows even after a process crash."""
from pathlib import Path
import msvcrt


class InstanceLock:
    def __init__(self, base):
        self.path = Path(base) / '.autoqueue.lock'
        self.handle = None

    def acquire(self):
        try:
            handle = self.path.open('a+b')
            if handle.seek(0, 2) == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            self.handle = handle
            return True
        except OSError:
            if 'handle' in locals():
                handle.close()
            return False

    def release(self):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.handle.close()
                self.handle = None
