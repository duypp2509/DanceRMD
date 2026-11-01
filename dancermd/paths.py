"""Filesystem locations: bundled resources and the per-user data directory."""

import os
import sys
from pathlib import Path

from . import APP_ID

PACKAGE_DIR = Path(__file__).resolve().parent
# PyInstaller unpacks bundled files under sys._MEIPASS, keeping the package layout.
BUNDLE_DIR = Path(sys._MEIPASS) / "dancermd" if hasattr(sys, "_MEIPASS") else PACKAGE_DIR
WEB_DIR = BUNDLE_DIR / "web"
RESOURCES_DIR = BUNDLE_DIR / "resources"
ICON_SOURCE = RESOURCES_DIR / "icon.jpg"
FIREWALL_SCRIPT = RESOURCES_DIR / "firewall.ps1"

# Overrides the data directory, e.g. to run a test instance next to the installed app.
HOME_ENV = "DANCERMD_HOME"
_APPDATA = Path(os.environ.get("APPDATA") or Path.home())
DATA_DIR = Path(os.environ.get(HOME_ENV) or _APPDATA / APP_ID)
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH = DATA_DIR / "dancermd.log"
CACHE_DIR = DATA_DIR / "cache"
BIN_DIR = DATA_DIR / "bin"

# Version 1.x shipped as "Remote Laptop" and kept its data here.
LEGACY_DATA_DIR = _APPDATA / "RemoteLaptop"


def is_isolated():
    """True when running against a custom data directory (tests, side-by-side instances)."""
    return HOME_ENV in os.environ


def frozen():
    return getattr(sys, "frozen", False)
