"""Per-user installation (no administrator rights needed).

Installs to %LOCALAPPDATA%\\Programs\\DanceRMD, adds Start menu and desktop shortcuts (so Windows
search finds the app) and registers an entry in Settings > Apps for uninstalling.
"""

import os
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

from .. import APP_ID, APP_NAME
from ..errors import UserError
from ..win32 import autostart
from ..win32.api import CREATE_NO_WINDOW
from ..win32.process import powershell

LOCAL_PROGRAMS = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Programs"
START_MENU = Path(os.environ.get("APPDATA") or Path.home()) / r"Microsoft\Windows\Start Menu\Programs"
INSTALL_DIR = LOCAL_PROGRAMS / APP_NAME
INSTALLED_EXE = INSTALL_DIR / f"{APP_ID}.exe"
START_MENU_LINK = START_MENU / f"{APP_NAME}.lnk"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
SHORTCUT_DESCRIPTION = "Control this PC from your phone"


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def desktop_dir():
    # OneDrive may have relocated the Desktop folder, so ask Windows instead of guessing
    return Path(powershell("[Environment]::GetFolderPath('Desktop')"))


def is_installed():
    return INSTALLED_EXE.exists()


def running_installed_copy():
    return getattr(sys, "frozen", False) and Path(sys.executable).resolve() == INSTALLED_EXE.resolve()


def same_build(exe):
    """Whether the installed copy is this exact build (then there is nothing to update)."""
    try:
        a, b = Path(exe).stat(), INSTALLED_EXE.stat()
    except OSError:
        return False
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def _copy_when_unlocked(source, target, timeout=10):
    """A copy that just exited may keep the file locked for a few seconds (bootloader process,
    antivirus scan), so retry for a while."""
    end = time.monotonic() + timeout
    while True:
        try:
            shutil.copy2(source, target)
            return
        except PermissionError:
            if time.monotonic() > end:
                raise UserError("install.locked", "{path} is locked. Quit {app} and try again.",
                                path=str(target), app=APP_NAME) from None
            time.sleep(0.4)


def create_shortcuts(links, target, description=SHORTCUT_DESCRIPTION):
    script = ["$shell = New-Object -ComObject WScript.Shell"]
    for link in links:
        script += [f"$l = $shell.CreateShortcut({_ps_quote(link)})",
                   f"$l.TargetPath = {_ps_quote(target)}",
                   f"$l.WorkingDirectory = {_ps_quote(Path(target).parent)}",
                   f"$l.IconLocation = {_ps_quote(f'{target},0')}",
                   f"$l.Description = {_ps_quote(description)}",
                   "$l.Save()"]
    powershell("; ".join(script))


def install(source_exe, version, desktop_shortcut=True):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    if Path(source_exe).resolve() != INSTALLED_EXE.resolve():
        _copy_when_unlocked(source_exe, INSTALLED_EXE)
    links = [START_MENU_LINK] + ([desktop_dir() / f"{APP_NAME}.lnk"] if desktop_shortcut else [])
    create_shortcuts(links, INSTALLED_EXE)

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for name, value in (("DisplayName", APP_NAME), ("DisplayVersion", version), ("Publisher", APP_NAME),
                            ("DisplayIcon", f"{INSTALLED_EXE},0"), ("InstallLocation", str(INSTALL_DIR)),
                            ("UninstallString", f'"{INSTALLED_EXE}" --uninstall')):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name, value in (("NoModify", 1), ("NoRepair", 1),
                            ("EstimatedSize", INSTALLED_EXE.stat().st_size // 1024)):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)

    if autostart.is_enabled():  # keep "start with Windows" pointing at the installed copy
        autostart.set_enabled(True, f'"{INSTALLED_EXE}" --minimized')


def remove_later(path, delay_seconds=4):
    """Delete a folder once this process has exited (a running .exe can't delete itself)."""
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n {delay_seconds + 1} >nul & rmdir /s /q "{path}"',
                     creationflags=CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)


def uninstall(remove_data, data_dir):
    autostart.set_enabled(False)
    for link in (START_MENU_LINK, desktop_dir() / f"{APP_NAME}.lnk"):
        link.unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass
    if remove_data:
        shutil.rmtree(data_dir, ignore_errors=True)
    remove_later(INSTALL_DIR)
