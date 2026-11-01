"""Start with Windows through the per-user Run registry key."""

import winreg

from .. import APP_ID

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_enabled(value=APP_ID):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value)
        return True
    except OSError:
        return False


def set_enabled(enabled, command=None, value=APP_ID):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, value, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, value)
            except FileNotFoundError:
                pass
