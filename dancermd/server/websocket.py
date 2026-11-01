"""The /ws endpoint: token handshake, then the message loop of one phone."""

import asyncio
import hmac
import json
import logging
import socket

from aiohttp import WSMsgType, web

from .. import VERSION, config
from ..errors import UserError, error_payload
from ..media import encoders
from ..win32 import system
from .auth import same_origin
from .network import client_ip, device_kind
from .session import Session
from .state import STATE

log = logging.getLogger(__name__)
AUTH_TIMEOUT = 10
CLOSE_BAD_HANDSHAKE, CLOSE_AUTH_FAILED = 4000, 4001


async def _authenticate(ws, state, ip):
    """Read the {"t": "auth", "token": ...} message. Returns True when the token is valid."""
    try:
        first = await ws.receive(timeout=AUTH_TIMEOUT)
        msg = json.loads(first.data) if first.type == WSMsgType.TEXT else {}
    except (asyncio.TimeoutError, ValueError):
        msg = {}
    if not isinstance(msg, dict) or msg.get("t") != "auth":
        await ws.close(code=CLOSE_BAD_HANDSHAKE)
        return False
    token = str(msg.get("token", ""))
    guard = state.guard
    if guard.blocked(ip):
        reason = UserError("auth.rate_limited", "Too many wrong attempts. Wait a minute and try again.")
    elif not hmac.compare_digest(token.encode(), state.config["token"].encode()):
        guard.fail(ip)
        reason = UserError("auth.invalid", "Wrong access code")
    else:
        guard.success(ip)
        return True
    log.warning("Rejected connection from %s: %s", ip, reason)
    if not ws.closed:
        await ws.send_str(json.dumps({"t": "auth_fail", "reason": reason.payload()}, ensure_ascii=False))
        await ws.close(code=CLOSE_AUTH_FAILED, message=b"auth")
    return False


def _emit(state, kind, sess):
    try:
        state.hooks.on_event(kind, sess.info())
    except Exception:
        log.exception("Event hook failed: %s", kind)


async def ws_handler(request):
    state = request.app[STATE]
    if not same_origin(request):
        raise web.HTTPForbidden(text="Invalid origin")
    ws = web.WebSocketResponse(heartbeat=20, compress=False, max_msg_size=1 << 20)
    await ws.prepare(request)
    ip = client_ip(request)
    if not await _authenticate(ws, state, ip):
        return ws
    if not state.config.get("paired"):
        state.config["paired"] = True
        config.save(state.config)

    hint = "uipi.hint_desktop" if state.hooks.set_admin_mode else "uipi.hint_cli"
    sess = Session(ws, state.capturer, ip, device_kind(request.headers.get("User-Agent", "")), hint)
    await sess.load_monitors()
    state.sessions[sess.id] = sess
    log.info("Phone connected: %s (%s)", ip, sess.device)
    _emit(state, "connect", sess)
    try:
        await sess.send(t="hello", host=socket.gethostname(), version=VERSION, monitors=sess.monitors,
                        monitor=sess.monitor, battery=system.battery(), qualities=list(encoders.QUALITY))
        for loop in (sess.stream_loop, sess.cursor_loop, sess.info_loop, sess.uipi_loop, sess.window_loop):
            sess.spawn(loop())
        async for frame in ws:
            if frame.type != WSMsgType.TEXT:
                continue
            try:
                await sess.handle(json.loads(frame.data))
            except ConnectionResetError:
                break
            except Exception as exc:
                log.warning("Command failed: %s", exc)
                await sess.send(t="toast", error=True, **error_payload(exc))
    finally:
        for task in list(sess.tasks):
            task.cancel()
        await sess.release_buttons()
        state.sessions.pop(sess.id, None)
        log.info("Phone disconnected: %s", ip)
        _emit(state, "disconnect", sess)
    return ws
