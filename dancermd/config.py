"""User settings (config.json in the data directory) and logging setup.

Keys: token, paired, port, language ("auto" | "en" | "vi"), tunnel, autostart, run_as_admin,
install_declined, show_on_start.
"""

import json
import logging
import logging.handlers
import secrets
import shutil
import sys

from . import paths

log = logging.getLogger("dancermd")
DEFAULT_PORT = 8765


def new_token():
    return secrets.token_urlsafe(12)


def migrate_legacy_data():
    """Carry the settings of "Remote Laptop" 1.x over, so paired phones keep their access token."""
    legacy = paths.LEGACY_DATA_DIR / "config.json"
    if paths.CONFIG_PATH.exists() or paths.is_isolated() or not legacy.exists():
        return
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, paths.CONFIG_PATH)
    cloudflared = paths.LEGACY_DATA_DIR / "bin" / "cloudflared.exe"
    if cloudflared.exists():
        paths.BIN_DIR.mkdir(exist_ok=True)
        shutil.copy2(cloudflared, paths.BIN_DIR / cloudflared.name)
    log.info("Imported settings from %s", paths.LEGACY_DATA_DIR)


def load(rotate_token=False):
    migrate_legacy_data()
    cfg = {}
    if paths.CONFIG_PATH.exists():
        try:
            cfg = json.loads(paths.CONFIG_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            log.warning("Unreadable config, starting fresh: %s", paths.CONFIG_PATH)
            cfg = {}
    if rotate_token or not cfg.get("token"):
        cfg["token"] = new_token()
        cfg["paired"] = False
        save(cfg)
    return cfg


def save(cfg):
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")


def setup_logging(console):
    """Log to the console when there is one, otherwise (desktop app, pythonw) to a rotating file."""
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if console and sys.stderr is not None:
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                stream.reconfigure(encoding="utf-8", errors="replace")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    else:
        handler = logging.handlers.RotatingFileHandler(paths.LOG_PATH, maxBytes=512_000, backupCount=1,
                                                       encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
