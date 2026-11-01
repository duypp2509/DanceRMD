"""Named mutexes, used to keep a single running copy of the desktop app."""

import ctypes
from ctypes import wintypes

from .api import kernel32

kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.OpenMutexW.restype = wintypes.HANDLE
SYNCHRONIZE = 0x00100000
ERROR_ACCESS_DENIED, ERROR_ALREADY_EXISTS = 5, 183


def mutex_exists(name):
    handle = kernel32.OpenMutexW(SYNCHRONIZE, False, name)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    # Access denied: the mutex exists but belongs to an elevated process
    return ctypes.get_last_error() == ERROR_ACCESS_DENIED


class NamedMutex:
    """Held for the lifetime of the process; ``acquire`` fails when another process owns the name."""

    def __init__(self, name):
        self.name = name
        self._handle = None

    def acquire(self):
        self._handle = kernel32.CreateMutexW(None, False, self.name)
        # NULL with access denied also means an elevated copy owns it
        return bool(self._handle) and ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    def release(self):
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None
