"""Screen capture on a dedicated thread, shared by every connected phone."""

import logging
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

import mss
import numpy as np

try:
    import dxcam
except Exception:  # library missing or Windows too old: GDI only
    dxcam = None

log = logging.getLogger(__name__)
_MSS = getattr(mss, "MSS", None) or mss.mss  # mss >= 10 renamed the class
DXGI_RETRY_SECONDS = 5


class Capturer:
    """Grabs the latest frame of a monitor. DXGI only returns a frame when the screen changed; the GDI
    fallback compares checksums instead. Every method must run on ``self.pool``."""

    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capture")
        self._sct = None
        self._cams = {}    # (left, top, width, height) -> DXCamera | None (not capturable with DXGI)
        self._latest = {}  # monitor index -> (BGRA frame, version)
        self._crc = {}
        self._dxgi_retry_at = 0.0 if dxcam is not None else float("inf")
        self.backend = "dxgi" if dxcam is not None else "gdi"

    @property
    def backend_label(self):
        return "GPU (DXGI)" if self.backend == "dxgi" else "CPU (GDI)"

    def _mss(self):
        if self._sct is None:
            self._sct = _MSS()
        return self._sct

    def _reset(self):
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
        self._release_cams()
        self._latest.clear()
        self._crc.clear()

    def _release_cams(self):
        for cam in self._cams.values():
            if cam is not None:
                try:
                    cam.release()
                except Exception:
                    pass
        self._cams.clear()

    def monitors(self):
        """Re-read the monitor layout (a display may have been plugged in or removed)."""
        self._reset()
        mons = []
        for i, m in enumerate(self._mss().monitors[1:], 1):
            mons.append({"index": i, "left": m["left"], "top": m["top"], "width": m["width"],
                         "height": m["height"], "primary": bool(m.get("is_primary", i == 1)),
                         "name": m.get("name")})
        return mons

    def _dx_camera(self, mon):
        """The DXGI output whose desktop rectangle matches this monitor."""
        key = (mon["left"], mon["top"], mon["width"], mon["height"])
        if key not in self._cams:
            cam = None
            factory = next((v for v in vars(dxcam).values() if isinstance(v, dxcam.DXFactory)), None)
            for di, outputs in enumerate(factory.outputs if factory else []):
                for oi, output in enumerate(outputs):
                    r = output.desc.DesktopCoordinates
                    if (r.left, r.top, r.right - r.left, r.bottom - r.top) == key:
                        cam = dxcam.create(device_idx=di, output_idx=oi, output_color="BGRA",
                                           processor_backend="numpy")
            self._cams[key] = cam
        return self._cams[key]

    def latest(self, index):
        """(latest BGRA frame of the monitor, version); the version increases whenever the image changes."""
        mons = self._mss().monitors
        mon = mons[index] if 0 < index < len(mons) else mons[1]
        entry = self._latest.get(index)
        frame = None
        if time.monotonic() >= self._dxgi_retry_at:
            try:
                cam = self._dx_camera(mon)
                if cam is not None:
                    # No frame yet: take the current one. Otherwise only take a frame when the screen changed.
                    frame = cam.grab(new_frame_only=entry is not None)
                    self.backend = "dxgi"
                    if frame is None and entry is not None:
                        return entry
            except Exception as exc:
                log.warning("DXGI capture failed (%s), using GDI for now", exc)
                self._release_cams()
                self._dxgi_retry_at = time.monotonic() + DXGI_RETRY_SECONDS
                frame = None
        if frame is None:
            self.backend = "gdi"
            shot = self._mss().grab(mon)
            crc = zlib.crc32(shot.raw)
            if entry is not None and crc == self._crc.get(index):
                return entry
            self._crc[index] = crc
            frame = np.frombuffer(shot.raw, np.uint8).reshape(shot.height, shot.width, 4)
        entry = (frame, entry[1] + 1 if entry else 1)
        self._latest[index] = entry
        return entry
