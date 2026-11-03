"""Command line of the desktop app.

    DanceRMD.exe [--minimized] [--port N] [--install] [--uninstall]

--minimized  start in the system tray only (used by autostart)
--install    install without asking (Start menu, desktop, Settings > Apps)
--uninstall  uninstall (called from Settings > Apps)
"""

import argparse
import ctypes
import logging
import sys

from .. import APP_ID, APP_NAME, VERSION, config, i18n, paths
from ..i18n import t
from ..services import elevation, installer
from ..win32.input import enable_dpi_awareness
from ..win32.security import is_elevated
from . import dialogs, instance, legacy, lifecycle
from .app import DesktopApp

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(prog=APP_ID, description=f"{APP_NAME} desktop app")
    parser.add_argument("--minimized", action="store_true", help="start in the system tray only")
    parser.add_argument("--port", type=int, help=f"port (default: {config.DEFAULT_PORT})")
    parser.add_argument("--install", action="store_true", help="install without asking")
    parser.add_argument("--uninstall", action="store_true", help="uninstall")
    args = parser.parse_args()

    config.setup_logging(console=False)
    enable_dpi_awareness()
    # Group taskbar buttons under this app (not python.exe when running from source)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.Desktop")
    cfg = config.load()
    i18n.set_language(cfg.get("language", config.DEFAULT_LANGUAGE))
    port = args.port or cfg.get("port", config.DEFAULT_PORT)
    try:
        if args.uninstall:
            lifecycle.run_uninstall(port)
            return
        if args.install:
            if not paths.frozen():
                parser.error("--install requires the packaged executable (see scripts/build.py)")
            installer.install(sys.executable, VERSION)
            lifecycle.after_install(port)
            return
        if lifecycle.offer_install(port):
            return
        if instance.other_running() or not instance.acquire():
            try:
                instance.post_local(port, "/api/show")  # bring the running copy's window to the front
            except OSError:
                dialogs.message(t("dialog.already_running"))
            return
        if not paths.is_isolated() and legacy.is_running():
            legacy.stop(port)  # "Remote Laptop" 1.x would hold the same port
        cfg = config.load()
        if cfg.get("run_as_admin") and not is_elevated():
            # Admin mode: start through the scheduled task to get elevated without a UAC prompt
            if not args.minimized:
                cfg["show_on_start"] = True
                config.save(cfg)
            instance.release()  # let the elevated copy take the lock
            if elevation.task_exists() and elevation.run_task():
                return
            log.warning("Admin task missing, running unelevated")
            instance.acquire()
        DesktopApp(args.minimized, args.port).run()
    except Exception:
        log.exception("Unexpected error")
        dialogs.message(t("dialog.crashed", log=paths.LOG_PATH), error=True)
