"""Remote access through a Cloudflare quick tunnel: no shared Wi-Fi, no router configuration.

cloudflared's "quick tunnel" needs no account and returns a random https://*.trycloudflare.com
address (a new one on every start). The phone reaches Cloudflare over HTTPS, which also unlocks
H.264 decoding in the browser (WebCodecs requires a secure context).
"""

import logging
import re
import shutil
import subprocess
import threading
import urllib.request
from collections import deque
from pathlib import Path

from ..errors import UserError, error_payload
from ..win32.api import CREATE_NO_WINDOW
from ..win32.process import kill_with_this_process
from ..win32.security import has_valid_signature

log = logging.getLogger(__name__)
DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
READY_MARKER = "Registered tunnel connection"


class Tunnel:
    """States: off -> starting -> on, or error. ``message`` is a translatable {code, params} payload."""

    def __init__(self, port, data_dir):
        self.port = port
        self.bin_dir = Path(data_dir) / "bin"
        # An empty config file stops cloudflared from reading ~/.cloudflared/config.yml,
        # which would break a quick tunnel.
        self.config_file = Path(data_dir) / "cloudflared-empty.yml"
        self.status = "off"
        self.url = None
        self.message = None
        self._proc = None
        self._lock = threading.Lock()
        self._log = deque(maxlen=12)

    def state(self):
        return {"status": self.status, "url": self.url, "message": self.message}

    def _set_message(self, code, text, **params):
        self.message = {"code": code, "params": params, "message": text.format(**params)}

    def start(self):
        with self._lock:
            if self.status in ("starting", "on"):
                return
            self.status, self.url = "starting", None
            self._set_message("tunnel.starting", "Starting…")
        threading.Thread(target=self._run, name="tunnel", daemon=True).start()

    def stop(self):
        with self._lock:
            proc, self._proc = self._proc, None
            self.status, self.url, self.message = "off", None, None
        if proc and proc.poll() is None:
            proc.terminate()

    def _executable(self):
        local = self.bin_dir / "cloudflared.exe"
        if local.exists():
            return local
        found = shutil.which("cloudflared")
        if found:
            return Path(found)
        self._set_message("tunnel.downloading", "Downloading cloudflared (about 60 MB, first time only)…")
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        part = local.with_suffix(".part")
        urllib.request.urlretrieve(DOWNLOAD_URL, part)
        if not has_valid_signature(part):
            part.unlink(missing_ok=True)
            raise UserError("tunnel.bad_signature",
                            "The downloaded cloudflared has no valid digital signature and was deleted")
        part.replace(local)
        return local

    def _run(self):
        try:
            exe = self._executable()
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text("", "utf-8")
            self._set_message("tunnel.creating", "Creating the tunnel…")
            proc = subprocess.Popen(
                [str(exe), "tunnel", "--config", str(self.config_file), "--no-autoupdate",
                 "--url", f"http://127.0.0.1:{self.port}"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
            kill_with_this_process(proc)
        except Exception as exc:
            log.warning("Remote access failed to start: %s", exc)
            with self._lock:
                if self.status == "starting":
                    self.status, self.message = "error", error_payload(exc)
            return

        with self._lock:
            if self.status != "starting":  # turned off while starting
                proc.terminate()
                return
            self._proc = proc
        for line in proc.stderr:
            self._log.append(line.rstrip())
            if self.url is None and (match := URL_RE.search(line)):
                self.url = match.group(0)
            if READY_MARKER in line and self.url and self.status == "starting":
                self.status, self.message = "on", None
                log.info("Remote access is on: %s", self.url)
        # cloudflared exited
        with self._lock:
            if self._proc is proc:  # not stopped by us
                self._proc = None
                last = next((line for line in reversed(self._log) if "ERR" in line), self._log[-1] if self._log else "")
                self.status, self.url = "error", None
                self._set_message("tunnel.stopped", "cloudflared stopped. {detail}", detail=last[-160:])
                log.warning("cloudflared stopped: %s", last)
