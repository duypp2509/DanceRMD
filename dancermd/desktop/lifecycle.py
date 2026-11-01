"""Install, update, uninstall and relaunch flows of the desktop app."""

import logging
import subprocess
import sys
from pathlib import Path

from .. import VERSION, config, paths
from ..i18n import t
from ..services import elevation, installer
from ..win32 import autostart
from ..win32.api import CREATE_NO_WINDOW
from . import dialogs, instance, legacy

log = logging.getLogger(__name__)


def launch_spec(exe=None):
    """(program, arguments) that start the app minimized to the tray, for autostart and the admin task."""
    if paths.frozen():
        return str(exe or sys.executable), "--minimized"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    entry = paths.PACKAGE_DIR / "__main__.py"
    return str(pythonw if pythonw.exists() else sys.executable), f'"{entry}" --minimized'


def autostart_command(exe=None):
    program, args = launch_spec(exe)
    return f'"{program}" {args}'


def relaunch_later(command, delay_seconds=2):
    """Run a command once this process has exited and released the single-instance lock."""
    subprocess.Popen(f"cmd /c ping 127.0.0.1 -n {delay_seconds + 1} >nul & {command}",
                     creationflags=CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)


def after_install(port):
    """Steps shared by every install path: replace the old "Remote Laptop" and repoint the admin task."""
    cfg = config.load()
    if legacy.is_installed() and not paths.is_isolated() and legacy.remove(port):
        # The old version started with Windows: keep that behaviour for the new one
        autostart.set_enabled(True, autostart_command(installer.INSTALLED_EXE))
        cfg["autostart"] = True
        config.save(cfg)
    if cfg.get("run_as_admin") and elevation.task_exists():
        try:
            elevation.install_task(*launch_spec(installer.INSTALLED_EXE), at_logon=bool(cfg.get("autostart")))
        except Exception as exc:
            log.warning("Couldn't update the admin task: %s", exc)


def install_and_launch(port):
    if not instance.stop_running(port) or not legacy.stop(port):
        dialogs.message(t("dialog.stop_failed"), error=True)
        return
    installer.install(sys.executable, VERSION)
    after_install(port)
    subprocess.Popen([str(installer.INSTALLED_EXE)])


def offer_install(port):
    """When a downloaded .exe is opened outside the install folder, offer to install it.
    Returns True if control was handed over to the installed copy."""
    if not paths.frozen() or installer.running_installed_copy():
        return False
    if installer.is_installed() and installer.same_build(sys.executable):
        subprocess.Popen([str(installer.INSTALLED_EXE)])  # same build: just open the installed copy
        return True
    cfg = config.load()
    if cfg.get("install_declined") and not installer.is_installed():
        return False
    if installer.is_installed():
        question = t("dialog.update")
    else:
        question = t("dialog.install")
        if legacy.is_installed():
            question += "\n\n" + t("dialog.install_legacy")
    if not dialogs.ask(question):
        cfg["install_declined"] = True
        config.save(cfg)
        return False
    install_and_launch(port)
    return True


def run_uninstall(port):
    if not dialogs.ask(t("dialog.uninstall")):
        return
    instance.stop_running(port)
    remove_data = dialogs.ask(t("dialog.remove_data"))
    try:
        elevation.remove_task()  # may show a UAC prompt
    except Exception as exc:
        log.warning("Couldn't remove the admin task: %s", exc)
    logging.shutdown()  # release the log file before deleting the data folder
    installer.uninstall(remove_data, paths.DATA_DIR)
    dialogs.message(t("dialog.uninstalled"))
