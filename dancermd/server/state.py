"""State shared by the request handlers, and the hooks the desktop shell plugs in."""

from collections.abc import Callable
from dataclasses import dataclass, field

from aiohttp import web

from ..media.capture import Capturer
from ..services.tunnel import Tunnel
from .auth import AuthGuard


def _noop(*_args):
    return None


@dataclass
class Hooks:
    """Callbacks into the host application. ``None`` means the feature is unavailable."""

    on_event: Callable[[str, dict], None] = _noop    # ("connect" | "disconnect", session info)
    show: Callable[[], None] | None = None           # bring the dashboard to the front
    quit: Callable[[], None] = _noop                 # another copy asks this one to exit
    install: Callable[[], None] | None = None        # packaged build installing itself
    set_admin_mode: Callable[[bool], None] | None = None
    set_autostart: Callable[[bool], None] | None = None
    autostart_enabled: Callable[[], bool] = lambda: False
    language_changed: Callable[[str], None] = _noop


@dataclass
class ServerState:
    config: dict
    port: int
    mode: str                     # "desktop" or "cli"
    hooks: Hooks
    capturer: Capturer
    tunnel: Tunnel
    installed: bool | None = None  # None when running from source (nothing to install)
    guard: AuthGuard = field(default_factory=AuthGuard)
    sessions: dict = field(default_factory=dict)


STATE = web.AppKey("dancermd_state", ServerState)
