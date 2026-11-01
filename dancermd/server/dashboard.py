"""The local dashboard (/dashboard): QR codes, connected phones and settings.

It shows the access token, so every route is restricted to this PC (see auth.local_only).
"""

import asyncio
import functools
import logging
import socket

import qrcode
import qrcode.image.svg
from aiohttp import web

from .. import APP_NAME, VERSION, config, i18n, paths
from ..errors import UserError, error_payload
from ..media import encoders
from ..win32 import security
from ..win32.process import run_elevated_script
from .auth import local_only
from .network import access_url, lan_addresses, lan_url
from .session import clamp_int
from .state import STATE

log = logging.getLogger(__name__)
CLOSE_KICKED, CLOSE_TOKEN_CHANGED = 4002, 4003


@functools.lru_cache(maxsize=32)
def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return img.to_string(encoding="unicode")


def dashboard_state(state):
    cfg, port = state.config, state.port
    links = []
    for addr in lan_addresses():
        url = lan_url(addr["ip"], port, cfg["token"])
        links.append({**addr, "url": url, "qr": qr_svg(url)})
    tunnel = state.tunnel.state()
    if tunnel["url"]:
        tunnel["link"] = access_url(tunnel["url"], cfg["token"])
        tunnel["qr"] = qr_svg(tunnel["link"])
    return {
        "app": APP_NAME, "version": VERSION, "mode": state.mode, "port": port, "token": cfg["token"],
        "host": socket.gethostname(), "data_dir": str(paths.DATA_DIR), "links": links,
        "language": i18n.resolve(cfg.get("language", "auto")), "language_setting": cfg.get("language", "auto"),
        "devices": sorted((s.info() for s in state.sessions.values()), key=lambda d: d["since"]),
        "autostart": state.hooks.autostart_enabled(), "tunnel": tunnel, "tunnel_enabled": bool(cfg.get("tunnel")),
        "admin": {"available": state.hooks.set_admin_mode is not None, "enabled": bool(cfg.get("run_as_admin")),
                  "elevated": security.is_elevated()},
        "gpu": {"capture": state.capturer.backend_label, "encoder": encoders.h264_label()},
        "installed": state.installed,
    }


def _ok(request):
    return web.json_response(dashboard_state(request.app[STATE]))


def _failed(exc, status=400):
    return web.json_response({"ok": False, "error": error_payload(exc)}, status=status)


async def _call(hook, *args):
    """Run a blocking desktop hook off the event loop; returns an error response or None."""
    if hook is None:
        return _failed(UserError("feature.unavailable", "Not available in this build"))
    try:
        await asyncio.to_thread(hook, *args)
    except Exception as exc:
        log.warning("Dashboard action failed: %s", exc)
        return _failed(exc)
    return None


@local_only
async def page(request):
    return web.FileResponse(paths.WEB_DIR / "dashboard" / "index.html", headers={"Cache-Control": "no-store"})


@local_only
async def legacy_page(request):
    raise web.HTTPFound("/dashboard")


@local_only
async def get_state(request):
    return _ok(request)


@local_only
async def rotate_token(request):
    state = request.app[STATE]
    state.config["token"] = config.new_token()
    config.save(state.config)
    for sess in list(state.sessions.values()):  # the old token is void: disconnect every phone
        asyncio.ensure_future(sess.ws.close(code=CLOSE_TOKEN_CHANGED, message=b"token changed"))
    log.info("Access token rotated")
    return _ok(request)


@local_only
async def kick(request):
    data = await request.json()
    sess = request.app[STATE].sessions.get(clamp_int(data.get("id")))
    if sess:
        asyncio.ensure_future(sess.ws.close(code=CLOSE_KICKED, message=b"kicked"))
    return web.json_response({"ok": True})


@local_only
async def set_autostart(request):
    enabled = bool((await request.json()).get("enabled"))
    return await _call(request.app[STATE].hooks.set_autostart, enabled) or _ok(request)


@local_only
async def set_admin(request):
    """Toggle admin mode (desktop build). The app restarts itself in the new mode."""
    enabled = bool((await request.json()).get("enabled"))
    return await _call(request.app[STATE].hooks.set_admin_mode, enabled) or web.json_response({"ok": True})


@local_only
async def set_language(request):
    state = request.app[STATE]
    language = (await request.json()).get("language")
    if language not in ("auto", *i18n.SUPPORTED):
        return _failed(UserError("feature.unavailable", "Unsupported language"))
    state.config["language"] = language
    config.save(state.config)
    state.hooks.language_changed(language)
    return _ok(request)


@local_only
async def open_firewall(request):
    try:
        await asyncio.to_thread(run_elevated_script, paths.FIREWALL_SCRIPT, "-Port", str(request.app[STATE].port))
    except UserError as exc:
        return _failed(exc)
    return web.json_response({"ok": True})


@local_only
async def set_tunnel(request):
    state = request.app[STATE]
    enabled = bool((await request.json()).get("enabled"))
    state.config["tunnel"] = enabled  # remembered: the tunnel starts again with the app
    config.save(state.config)
    if enabled:
        state.tunnel.start()
    else:
        state.tunnel.stop()
    return _ok(request)


@local_only
async def show(request):
    hook = request.app[STATE].hooks.show
    if hook:
        hook()
    return web.json_response({"ok": True})


@local_only
async def install(request):
    return await _call(request.app[STATE].hooks.install) or web.json_response({"ok": True})


@local_only
async def quit_app(request):
    """A newer copy (install, update) asks this one to exit so it can replace the files."""
    asyncio.get_running_loop().call_later(0.2, request.app[STATE].hooks.quit)
    return web.json_response({"ok": True})


def add_routes(app):
    app.router.add_get("/dashboard", page)
    app.router.add_get("/pair", legacy_page)
    app.router.add_get("/api/state", get_state)
    for path, handler in (("token", rotate_token), ("kick", kick), ("autostart", set_autostart),
                          ("admin", set_admin), ("language", set_language), ("firewall", open_firewall),
                          ("tunnel", set_tunnel), ("show", show), ("install", install), ("quit", quit_app)):
        app.router.add_post(f"/api/{path}", handler)
