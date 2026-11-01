"""HTTP + WebSocket server: serves the phone client, streams the screen and executes input.

Routes are defined in server.app; the wire protocol is documented in docs/protocol.md.
"""

from .app import ServerThread, make_app
from .state import Hooks

__all__ = ["Hooks", "ServerThread", "make_app"]
