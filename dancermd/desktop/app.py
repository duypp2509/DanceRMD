"""The desktop app: dashboard window, tray icon and the server running in the background."""

import ctypes
import logging
import sys
import threading
import time
import winreg

import pystray
import webview

from .. import APP_ID, APP_NAME, VERSION, branding, config, i18n, paths
from ..i18n import t
from ..server import Hooks, ServerThread, make_app
from ..server.network import access_url, lan_addresses, lan_url
from ..server.state import STATE
from ..services import elevation, installer
from ..win32 import autostart, clipboard
from . import dialogs, lifecycle

log = logging.getLogger(__name__)
SM_CXSMICON = 49
NOTIFY_COOLDOWN = 300  # seconds; phones reconnect each time their screen wakes up
WINDOW_BACKGROUND = {"dark": "#110c09", "light": "#f7f3ef"}


def windows_uses_dark_theme():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


class DesktopApp:
    def __init__(self, start_hidden, port=None):
        self.cfg = config.load()
        self.port = port or self.cfg.get("port", config.DEFAULT_PORT)
        hooks = Hooks(
            on_event=self.on_event, show=self.show, quit=self.quit,
            install=self.install_from_window if paths.frozen() else None,
            set_admin_mode=self.set_admin_mode, set_autostart=self.set_autostart,
            autostart_enabled=self.autostart_enabled, language_changed=self.on_language_changed,
        )
        self.app = make_app(self.cfg, self.port, mode="desktop", hooks=hooks,
                            installed=installer.is_installed() if paths.frozen() else None)
        self.state = self.app[STATE]
        self.server = ServerThread(self.app, "0.0.0.0", self.port)
        # Show the window on the first run (the QR code is needed), and after a restart that asked for it
        show_once = self.cfg.pop("show_on_start", False)
        if show_once:
            config.save(self.cfg)
        self.start_hidden = start_hidden and self.cfg.get("paired") and not show_once
        self.window = None
        self.tray = None
        self.quitting = False
        self.tray_hint_shown = False
        self.last_notified = {}  # ip -> time of the last "phone connected" notification

    def run(self):
        try:
            self.server.start()
        except OSError as exc:
            log.error("Couldn't open port %s: %s", self.port, exc)
            dialogs.message(t("dialog.port_in_use", port=self.port, error=exc), error=True)
            return
        log.info("%s %s (desktop) listening on port %s", APP_NAME, VERSION, self.port)

        theme = "dark" if windows_uses_dark_theme() else "light"
        self.window = webview.create_window(
            APP_NAME, f"http://127.0.0.1:{self.port}/dashboard", width=1020, height=760, min_size=(720, 560),
            hidden=bool(self.start_hidden), background_color=WINDOW_BACKGROUND[theme])
        self.window.events.closing += self.on_closing

        tray_size = ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON) or 16
        self.tray = pystray.Icon(APP_ID, branding.render(tray_size), APP_NAME, menu=self._menu())
        threading.Thread(target=self.tray.run, name="tray", daemon=True).start()

        # The packaged .exe uses its embedded icon; from source, point to a generated .ico
        webview.start(icon=None if paths.frozen() else str(branding.window_icon_path()))
        self.tray.stop()
        self.server.stop()

    # ----- window -----
    def on_closing(self):
        """Closing the window only hides it: the server must keep running for the phone."""
        if self.quitting:
            return True
        threading.Thread(target=self.window.hide, daemon=True).start()
        if not self.tray_hint_shown:
            self.tray_hint_shown = True
            self.tray.notify(t("notify.still_running"), APP_NAME)
        return False

    def show(self):
        if self.window:
            self.window.show()
            self.window.restore()

    def quit(self):
        self.quitting = True
        if self.window:
            self.window.destroy()

    def install_from_window(self):
        """The dashboard's "Install" button: copy the files, then switch over to the installed copy."""
        installer.install(sys.executable, VERSION)
        lifecycle.after_install(self.port)
        lifecycle.relaunch_later(f'start "" "{installer.INSTALLED_EXE}"')
        threading.Timer(0.5, self.quit).start()

    # ----- tray -----
    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(t("tray.open"), lambda: self.show(), default=True),
            pystray.MenuItem(t("tray.copy_link"), lambda: self.copy_link()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.quit"), lambda: self.quit()),
        )

    def on_language_changed(self, setting):
        i18n.set_language(setting)
        if self.tray:
            self.tray.menu = self._menu()
            self.tray.update_menu()

    def copy_link(self):
        tunnel = self.state.tunnel.state()
        if tunnel["url"]:
            url, message = access_url(tunnel["url"], self.cfg["token"]), "notify.link_copied_remote"
        else:
            url, message = lan_url(lan_addresses()[0]["ip"], self.port, self.cfg["token"]), "notify.link_copied_lan"
        clipboard.set_text(url)
        self.tray.notify(t(message), APP_NAME)

    def on_event(self, kind, info):
        count = len(self.state.sessions)
        self.tray.title = t("tray.connected", count=count) if count else APP_NAME
        now = time.monotonic()
        if kind == "connect" and now - self.last_notified.get(info["ip"], -1e9) > NOTIFY_COOLDOWN:
            self.last_notified[info["ip"]] = now
            device = t(f"device.{info['device']}")
            self.tray.notify(t("notify.phone_connected", device=device, ip=info["ip"]),
                             t("notify.phone_connected.title"))

    # ----- admin mode and autostart -----
    def autostart_enabled(self):
        if self.cfg.get("run_as_admin"):
            return bool(self.cfg.get("autostart"))
        return autostart.is_enabled()

    def set_autostart(self, enabled):
        if self.cfg.get("run_as_admin"):
            # The Run key can't start an elevated app: use the admin task's logon trigger instead
            elevation.install_task(*lifecycle.launch_spec(), at_logon=enabled)
        else:
            autostart.set_enabled(enabled, lifecycle.autostart_command())
        self.cfg["autostart"] = enabled
        config.save(self.cfg)

    def set_admin_mode(self, enabled):
        """On: create the admin task (one UAC prompt) and restart through it. Off: delete the task and
        restart unelevated. Either way the app exits and starts again about two seconds later."""
        autostart_on = self.autostart_enabled()
        if enabled:
            elevation.install_task(*lifecycle.launch_spec(), at_logon=autostart_on)  # UAC prompt here
            autostart.set_enabled(False)
            relaunch = f'schtasks /run /tn "{elevation.TASK_NAME}"'
        else:
            elevation.remove_task()
            if autostart_on:
                autostart.set_enabled(True, lifecycle.autostart_command())
            # Explorer starts programs unelevated, even when asked by an elevated process
            relaunch = f'explorer.exe "{sys.executable}"' if paths.frozen() else lifecycle.autostart_command()
        self.cfg.update(run_as_admin=enabled, autostart=autostart_on, show_on_start=True)
        config.save(self.cfg)
        log.info("Admin mode %s, restarting", "on" if enabled else "off")
        lifecycle.relaunch_later(relaunch)
        threading.Timer(0.5, self.quit).start()
