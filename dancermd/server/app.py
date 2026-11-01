"""Application factory, routes and a background-thread runner."""

import asyncio
import threading

from aiohttp import web

from .. import branding, paths
from ..media import encoders
from ..media.capture import Capturer
from ..services.tunnel import Tunnel
from . import dashboard
from .state import STATE, Hooks, ServerState
from .websocket import ws_handler

CLIENT_DIR = paths.WEB_DIR / "client"


async def client_page(request):
    return web.FileResponse(CLIENT_DIR / "index.html")


async def icon(request):
    found = branding.web_icon(request.match_info["name"])
    if not found:
        raise web.HTTPNotFound()
    content_type, body = found
    return web.Response(body=body, content_type=content_type, headers={"Cache-Control": "max-age=86400"})


@web.middleware
async def no_cache(request, handler):
    """Revalidate the UI files on every load, so phones pick up updates right away."""
    resp = await handler(request)
    if not resp.prepared:
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


def _ignore_connection_resets(loop, context):
    """Windows' proactor event loop reports clients that disappear abruptly as errors; they are expected."""
    if isinstance(context.get("exception"), ConnectionResetError):
        return
    loop.default_exception_handler(context)


async def _on_startup(app):
    asyncio.get_running_loop().set_exception_handler(_ignore_connection_resets)
    state = app[STATE]
    if state.config.get("tunnel"):
        state.tunnel.start()
    # Probe the H.264 encoders now (about 0.3 s) rather than when the first phone connects
    state.capturer.pool.submit(encoders.pick_h264)


async def _on_cleanup(app):
    app[STATE].tunnel.stop()


def make_app(cfg, port, mode="cli", hooks=None, installed=None):
    """Build the aiohttp application. ``mode`` is "cli" (headless) or "desktop"."""
    app = web.Application(middlewares=[no_cache])
    app[STATE] = ServerState(config=cfg, port=port, mode=mode, hooks=hooks or Hooks(), capturer=Capturer(),
                             tunnel=Tunnel(port, paths.DATA_DIR), installed=installed)
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    app.router.add_get("/", client_page)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/icons/{name}", icon)
    dashboard.add_routes(app)
    app.router.add_static("/static/", paths.WEB_DIR)
    return app


class ServerThread:
    """Runs the server on a background event loop; the desktop app needs the main thread for its window."""

    def __init__(self, app, host, port):
        self.app, self.host, self.port = app, host, port
        self.loop = asyncio.new_event_loop()
        self._runner = None

    def start(self):
        """Start listening; raises OSError when the port is taken."""
        ready, errors = threading.Event(), []

        def run():
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self._start())
            except Exception as exc:
                errors.append(exc)
                ready.set()
                return
            ready.set()
            self.loop.run_forever()

        threading.Thread(target=run, name="server", daemon=True).start()
        ready.wait()
        if errors:
            raise errors[0]

    async def _start(self):
        self._runner = web.AppRunner(self.app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()

    def stop(self):
        if self._runner:
            try:
                asyncio.run_coroutine_threadsafe(self._runner.cleanup(), self.loop).result(timeout=5)
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)
