"""Removal of "Remote Laptop" 1.x, the former name of DanceRMD.

Settings are imported separately (config.migrate_legacy_data), so paired phones keep working.
"""

import logging
import shutil
import time
import winreg

from .. import paths
from ..services import elevation, installer
from ..win32 import autostart
from . import instance

log = logging.getLogger(__name__)
NAME = "Remote Laptop"
INSTALL_DIR = installer.LOCAL_PROGRAMS / NAME
START_MENU_LINK = installer.START_MENU / f"{NAME}.lnk"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RemoteLaptop"
RUN_VALUE = "RemoteLaptop"
TASK_NAME = f"{NAME} (Admin)"
MUTEX_NAME = "Local\\RemoteLaptop.Desktop"


def _has_uninstall_key():
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY).Close()
        return True
    except OSError:
        return False


def is_installed():
    return INSTALL_DIR.exists() or _has_uninstall_key()


def is_running():
    return instance.other_running(MUTEX_NAME)


def stop(port):
    return instance.stop_running(port, MUTEX_NAME)


def remove(port):
    """Uninstall the old version. Returns True if it was set to start with Windows."""
    stop(port)
    had_autostart = autostart.is_enabled(RUN_VALUE)
    autostart.set_enabled(False, value=RUN_VALUE)
    for link in (START_MENU_LINK, installer.desktop_dir() / f"{NAME}.lnk"):
        link.unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass
    if elevation.task_exists(TASK_NAME):
        try:
            elevation.remove_task(TASK_NAME)  # created elevated, so deleting it shows a UAC prompt
        except Exception as exc:
            log.warning("Couldn't remove the old admin task: %s", exc)
    for _ in range(10):  # the old .exe may stay locked for a moment after it exits
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
        if not INSTALL_DIR.exists():
            break
        time.sleep(0.5)
    if paths.CONFIG_PATH.exists():  # settings already imported
        shutil.rmtree(paths.LEGACY_DATA_DIR, ignore_errors=True)
    log.info("Removed %s (autostart was %s)", NAME, "on" if had_autostart else "off")
    return had_autostart
