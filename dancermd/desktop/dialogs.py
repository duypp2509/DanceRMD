"""Native message boxes, usable before any window exists."""

import ctypes

from .. import APP_NAME

MB_YESNO, MB_ICONERROR, MB_ICONQUESTION, MB_ICONINFORMATION = 0x4, 0x10, 0x20, 0x40
IDYES = 6


def message(text, error=False):
    ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, MB_ICONERROR if error else MB_ICONINFORMATION)


def ask(text):
    return ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, MB_YESNO | MB_ICONQUESTION) == IDYES
