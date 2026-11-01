"""Access control: token brute-force protection and the local-only dashboard guard."""

import functools
import time
from urllib.parse import urlsplit

from aiohttp import web

LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
LOOPBACK = ("127.0.0.1", "::1")


class AuthGuard:
    """Blocks an address for ``window`` seconds after ``max_fail`` wrong tokens."""

    def __init__(self, max_fail=5, window=60, clock=time.monotonic):
        self.max_fail, self.window, self.clock = max_fail, window, clock
        self.fails = {}

    def blocked(self, ip):
        now = self.clock()
        self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < self.window]
        return len(self.fails[ip]) >= self.max_fail

    def fail(self, ip):
        self.fails.setdefault(ip, []).append(self.clock())

    def success(self, ip):
        self.fails.pop(ip, None)


def same_origin(request):
    origin = request.headers.get("Origin")
    return not origin or urlsplit(origin).netloc == request.host


def is_local(request):
    """Whether the request comes from a browser on this PC.

    The Host header is checked too, so a malicious website can't reach the dashboard through DNS
    rebinding. Requests relayed by Cloudflare Tunnel also come from 127.0.0.1, but carry a
    *.trycloudflare.com Host and CF-* headers, so they are rejected.
    """
    host = request.host if request.host.endswith("]") else request.host.rsplit(":", 1)[0]
    via_tunnel = "CF-Connecting-IP" in request.headers or "CF-Ray" in request.headers
    return request.remote in LOOPBACK and host in LOCAL_HOSTS and not via_tunnel


def local_only(handler):
    """Restrict a handler to this PC. POST requests must also be same-origin JSON, which a foreign
    page can't send without a CORS preflight (CSRF protection)."""
    @functools.wraps(handler)
    async def wrapper(request):
        if not is_local(request):
            raise web.HTTPForbidden(text="The dashboard is only available on this PC.")
        if request.method == "POST" and (request.content_type != "application/json" or not same_origin(request)):
            raise web.HTTPForbidden(text="Invalid request")
        return await handler(request)
    return wrapper
