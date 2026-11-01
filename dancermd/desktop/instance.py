"""A single running copy of the desktop app, and requests to that copy."""

import time
import urllib.request
import zlib

from .. import APP_ID, paths
from ..win32.instance import NamedMutex, mutex_exists

# Each data directory is a separate instance, so a test copy (DANCERMD_HOME) never clashes with the real one
MUTEX_NAME = f"Local\\{APP_ID}.Desktop" + (
    f".{zlib.crc32(str(paths.DATA_DIR).encode()):08x}" if paths.is_isolated() else "")
_mutex = NamedMutex(MUTEX_NAME)


def acquire():
    return _mutex.acquire()


def release():
    _mutex.release()


def other_running(mutex_name=MUTEX_NAME):
    return mutex_exists(mutex_name)


def post_local(port, path, timeout=3):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=timeout).close()


def stop_running(port, mutex_name=MUTEX_NAME):
    """Ask the running copy to exit (needed before replacing its files). Returns True once it is gone."""
    if not other_running(mutex_name):
        return True
    try:
        post_local(port, "/api/quit")
    except OSError:
        pass
    for _ in range(50):
        if not other_running(mutex_name):
            time.sleep(0.8)  # give the PyInstaller bootloader time to release the .exe
            return True
        time.sleep(0.2)
    return False
