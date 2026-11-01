"""Headless server for development and servers without a desktop session.

    python -m dancermd --headless [--port 8765] [--new-token] [--no-browser]

Prints the connection links and a QR code in the console. The desktop app (python -m dancermd)
offers the same features with a window and a tray icon.
"""

import argparse
import asyncio
import logging
import sys
import webbrowser
from pathlib import Path

import qrcode
from aiohttp import web

from . import APP_NAME, VERSION, config
from .server import Hooks, make_app
from .server.network import lan_addresses, lan_url
from .win32 import autostart
from .win32.input import enable_dpi_awareness

log = logging.getLogger("dancermd")


def pythonw_path():
    exe = Path(sys.executable)
    return exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe


def autostart_command():
    entry = Path(__file__).resolve().parent / "__main__.py"
    return f'"{pythonw_path()}" "{entry}" --headless --no-browser'


def print_banner(cfg, port):
    addrs = lan_addresses()
    print("\n" + "=" * 64)
    print(f"  {APP_NAME} {VERSION} is running  (Ctrl+C to stop)")
    print("=" * 64)
    for addr in addrs:
        print(f"  {addr['kind']:<10} {lan_url(addr['ip'], port, cfg['token'])}")
    print(f"\n  Access code: {cfg['token']}")
    print(f"  Dashboard:   http://localhost:{port}/dashboard\n")
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(lan_url(addrs[0]["ip"], port, cfg["token"]))
        qr.print_ascii(out=sys.stdout, invert=True)
    except (UnicodeEncodeError, AttributeError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(prog="dancermd --headless", description=f"{APP_NAME} headless server")
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all interfaces)")
    parser.add_argument("--port", type=int, help=f"port (default: {config.DEFAULT_PORT})")
    parser.add_argument("--new-token", action="store_true", help="generate a new access code (phones must scan again)")
    parser.add_argument("--no-browser", action="store_true", help="don't open the dashboard on first run")
    args = parser.parse_args()

    config.setup_logging(console=True)  # without a console (pythonw) this logs to a file
    enable_dpi_awareness()

    cfg = config.load(rotate_token=args.new_token)
    port = args.port or cfg.get("port", config.DEFAULT_PORT)
    dashboard_url = f"http://localhost:{port}/dashboard"
    hooks = Hooks(
        show=lambda: webbrowser.open(dashboard_url),
        set_autostart=lambda enabled: autostart.set_enabled(enabled, autostart_command()),
        autostart_enabled=autostart.is_enabled,
    )
    app = make_app(cfg, port, mode="cli", hooks=hooks)

    async def on_startup(_app):
        if sys.stdout is not None:
            print_banner(cfg, port)
        if not cfg.get("paired") and not args.no_browser:
            asyncio.get_running_loop().call_later(1, webbrowser.open, dashboard_url)

    app.on_startup.append(on_startup)
    try:
        web.run_app(app, host=args.host, port=port, print=None, access_log=None)
    except OSError as exc:
        log.error("Couldn't open port %s (%s). Is another copy running? Try --port.", port, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
