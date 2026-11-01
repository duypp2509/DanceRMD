"""One connected phone: screen streaming, input, window switching and system commands.

Messages are JSON objects with a ``t`` (type) field; see docs/protocol.md.
"""

import asyncio
import itertools
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from ..errors import UserError, error_payload
from ..media import encoders
from ..win32 import clipboard, security, system, windows
from ..win32 import input as winput
from ..win32.api import cursor_pos

log = logging.getLogger(__name__)

MAX_FPS = {"jpeg": 20, "h264": 30}
# Frames in flight before the phone acknowledges one. More than one hides network latency.
FRAME_WINDOW = {"jpeg": 2, "h264": 3}
# When the screen stops changing, H.264 encodes a few more frames so the image sharpens.
REFINE_FRAMES = 5
CURSOR_HZ = 30
WINDOW_POLL_SECONDS = 1.2
MAX_THUMBNAILS = 24
HWND_LIMIT = 2 ** 63
POWER_ACTIONS = {
    "lock": system.lock,
    "display_off": system.display_off,
    "sleep": system.sleep,
    "hibernate": system.hibernate,
    "restart": system.restart,
    "shutdown": system.shutdown,
}

# One thread keeps input events in order
input_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="input")
_session_ids = itertools.count(1)


def clamp_int(value, limit=100000):
    try:
        return max(-limit, min(limit, int(value)))
    except (TypeError, ValueError):
        return 0


def clamp_frac(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _button(msg):
    button = msg.get("button", "left")
    if button not in winput.BUTTONS:
        raise UserError("input.bad_button", "Invalid mouse button")
    return button


async def in_capture_thread(capturer, fn, *args):
    return await asyncio.get_running_loop().run_in_executor(capturer.pool, fn, *args)


class Session:
    def __init__(self, ws, capturer, ip, device, uipi_hint):
        self.id = next(_session_ids)
        self.ip, self.device, self.since = ip, device, time.time()
        self.ws = ws
        self.capturer = capturer
        self.uipi_hint = uipi_hint  # how to lift the UIPI block on this build
        self.monitors = []
        self.monitor = 1
        self.quality = "medium"
        self.codec = "jpeg"         # "h264" once the phone can decode it and an encoder exists
        self.encoder = None         # used on the capture thread only
        self.streaming = False
        self.credits = 0            # frames that may still be sent before the phone acknowledges
        self.wake = asyncio.Event()
        self.force_frame = True
        self.held = set()           # mouse buttons held down, released on disconnect
        self.tasks = set()
        self.win_sub = False        # the phone wants window list updates
        self.win_refresh = asyncio.Event()
        self.win_last = None
        self.sent_icons = set()
        self.thumb_task = None

    def info(self):
        return {"id": self.id, "ip": self.ip, "device": self.device, "since": self.since}

    @property
    def geom(self):
        return self.monitors[self.monitor - 1] if 0 < self.monitor <= len(self.monitors) else None

    # ----- plumbing -----
    async def send(self, **msg):
        if not self.ws.closed:
            await self.ws.send_str(json.dumps(msg, ensure_ascii=False))

    async def toast(self, code, error=False, **params):
        await self.send(t="toast", code=code, params=params, error=error)

    async def toast_error(self, exc):
        await self.send(t="toast", error=True, **error_payload(exc))

    def spawn(self, coro):
        task = asyncio.create_task(self._quietly(coro))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    @staticmethod
    async def _quietly(coro):
        """Background tasks end silently when the phone disconnects; other failures are logged."""
        try:
            await coro
        except ConnectionResetError:
            pass
        except Exception:
            log.exception("Background task failed")

    async def run_bg(self, fn, *args, reply=None):
        """Run slow work (PowerShell, clipboard) without delaying mouse and keyboard input."""
        try:
            result = await asyncio.to_thread(fn, *args)
        except Exception as exc:
            await self.toast_error(exc)
            return
        if reply:
            await self.send(**reply(result))

    async def input(self, fn, *args):
        await asyncio.get_running_loop().run_in_executor(input_pool, fn, *args)

    async def load_monitors(self):
        self.monitors = await in_capture_thread(self.capturer, self.capturer.monitors)
        self.monitor = next((m["index"] for m in self.monitors if m["primary"]), 1)

    # ----- screen streaming -----
    def _produce(self, seen, refine, keyframe):
        """Capture thread: grab the latest frame and encode it if needed.
        Returns (frames, version, refine, decoder config)."""
        frame, version = self.capturer.latest(self.monitor)
        changed = version != seen or keyframe
        if changed:
            refine = REFINE_FRAMES
        elif self.codec == "h264" and refine > 0:
            refine -= 1
        else:
            return [], version, refine, None
        if self.encoder is None or (self.encoder.codec, self.encoder.quality) != (self.codec, self.quality):
            self.encoder = encoders.make_encoder(self.codec, self.quality)
            keyframe = True
        out = self.encoder.encode(frame, keyframe=keyframe)
        return out, version, refine, self.encoder.take_config()

    async def stream_loop(self):
        seen, refine, failing = 0, 0, False
        while True:
            await self.wake.wait()
            if not self.streaming or self.credits <= 0:
                self.wake.clear()  # wait for an acknowledgement ("next") or a settings change
                continue
            started = time.monotonic()
            keyframe, self.force_frame = self.force_frame, False
            try:
                out, seen, refine, config = await in_capture_thread(
                    self.capturer, self._produce, seen, refine, keyframe)
            except Exception as exc:
                log.warning("Capture/encode failed: %s", exc)
                self.encoder = None
                if not failing:
                    await self.toast("capture.failed", error=True)
                    failing = True
                await asyncio.sleep(1)
                continue
            failing = False
            if config:
                await self.send(**config)
            if not out:
                await asyncio.sleep(0.015)
                continue
            for kind, data in out:
                self.credits -= 1
                await self.ws.send_bytes(bytes([kind]) + data)
            await asyncio.sleep(max(0.0, 1 / MAX_FPS[self.codec] - (time.monotonic() - started)))

    async def set_stream(self, m):
        if "on" in m:
            self.streaming = bool(m["on"])
        if "monitor" in m and 0 < clamp_int(m["monitor"]) <= len(self.monitors):
            self.monitor = clamp_int(m["monitor"])
        if m.get("quality") in encoders.QUALITY:
            self.quality = m["quality"]
        if m.get("codec") in ("jpeg", "h264"):
            wants_h264 = m["codec"] == "h264"
            available = wants_h264 and await in_capture_thread(self.capturer, encoders.pick_h264)
            self.codec = "h264" if available else "jpeg"
        self.credits = FRAME_WINDOW[self.codec]
        self.force_frame = True
        self.wake.set()
        encoder = encoders.h264_label() if self.codec == "h264" else "JPEG"
        await self.send(t="stream", on=self.streaming, monitor=self.monitor, quality=self.quality,
                        codec=self.codec, encoder=encoder, capture=self.capturer.backend_label)

    # ----- background updates -----
    async def cursor_loop(self):
        last = None
        while True:
            await asyncio.sleep(1 / CURSOR_HZ)
            geom, pos = self.geom, cursor_pos()
            if not self.streaming or geom is None or pos is None:
                continue
            cur = (round((pos[0] - geom["left"]) / geom["width"], 4),
                   round((pos[1] - geom["top"]) / geom["height"], 4))
            if cur != last:
                last = cur
                await self.send(t="cursor", x=cur[0], y=cur[1])

    async def info_loop(self):
        while True:
            await asyncio.sleep(30)
            await self.send(t="sys", battery=system.battery())

    async def uipi_loop(self):
        """Tell the phone when an elevated window (e.g. Task Manager) blocks input, instead of failing silently."""
        if security.is_elevated():
            return
        last = None
        while True:
            await asyncio.sleep(1)
            title = security.blocked_window_title()
            if title != last:
                last = title
                await self.send(t="uipi", title=title, hint=self.uipi_hint)

    # ----- windows (Alt+Tab) -----
    def _monitor_at(self, point):
        x, y = point
        for m in self.monitors:
            if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
                return m["index"]
        return None

    async def window_loop(self):
        """Send the window list whenever it changes; each app icon is sent only once."""
        while True:
            try:
                await asyncio.wait_for(self.win_refresh.wait(), timeout=WINDOW_POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
            forced = self.win_refresh.is_set()
            self.win_refresh.clear()
            if not self.win_sub:
                continue
            found = await asyncio.to_thread(windows.list_windows)
            items = [{"id": w["id"], "title": w["title"], "app": w["app"], "icon": w["icon"], "min": w["min"],
                      "fg": w["fg"], "mon": None if w["min"] else self._monitor_at(w["center"])}
                     for w in found]
            if items == self.win_last and not forced:
                continue
            self.win_last = items
            icons = {k: windows.icon_data(k) for k in {w["icon"] for w in items if w["icon"]} - self.sent_icons}
            self.sent_icons.update(icons)
            await self.send(t="windows", list=items, icons=icons, multi=len(self.monitors) > 1)

    async def send_thumbnails(self, ids):
        for hwnd in ids[:MAX_THUMBNAILS]:
            data = await asyncio.to_thread(windows.thumbnail, hwnd)
            if data:
                await self.send(t="thumb", id=hwnd, data=data)

    async def activate_window(self, hwnd):
        reason = None
        try:
            ok = await asyncio.to_thread(windows.activate, hwnd)
            if not ok:
                reason = (UserError("window.blocked_admin",
                                    "The active window runs as administrator, so Windows blocked the switch")
                          if security.blocked_window_title() else
                          UserError("window.blocked", "Windows didn't allow switching to this window")).payload()
        except UserError as exc:
            ok, reason = False, exc.payload()
        await self._report_switch(hwnd, ok, reason)

    async def _report_switch(self, hwnd, ok, reason=None):
        title = windows.title(hwnd) if ok else ""
        if ok:
            # The window lives on another monitor: follow it with the stream
            mon = self._monitor_at(windows.center(hwnd))
            if mon and mon != self.monitor:
                await self.set_stream({"monitor": mon})
        await self.send(t="activated", id=hwnd, ok=ok, title=title, reason=reason)
        self.win_refresh.set()

    async def switch_previous(self):
        """Like pressing Alt+Tab once: send the real keys so Windows applies its own recency order."""
        before = windows.foreground()
        await self.input(winput.press_keys, ["alt", "tab"])
        for _ in range(10):
            await asyncio.sleep(0.05)
            after = windows.foreground()
            if after and after != before:
                await self._report_switch(after, True)
                return
        # The keys were swallowed (e.g. an elevated window is active): fall back to the z-order
        found = await asyncio.to_thread(windows.list_windows)
        others = [w for w in found if not w["fg"]]
        if others:
            await self.activate_window(others[0]["id"])
        else:
            await self.toast("switch.none")

    async def close_window(self, hwnd):
        try:
            await asyncio.to_thread(windows.close, hwnd)
        except UserError as exc:
            await self.toast_error(exc)
        await asyncio.sleep(0.4)
        self.win_refresh.set()

    def request_thumbnails(self, ids):
        if self.thumb_task:
            self.thumb_task.cancel()
        self.thumb_task = self.spawn(self.send_thumbnails(ids))

    # ----- message dispatch -----
    async def handle(self, m):
        t = m.get("t")
        if t == "move":
            await self.input(winput.move_by, clamp_int(m.get("dx"), 5000), clamp_int(m.get("dy"), 5000))
        elif t == "moveto":
            g = self.geom
            if g:
                x = g["left"] + round(clamp_frac(m.get("x")) * (g["width"] - 1))
                y = g["top"] + round(clamp_frac(m.get("y")) * (g["height"] - 1))
                await self.input(winput.move_to, x, y)
        elif t == "click":
            await self.input(winput.click, _button(m), 2 if m.get("double") else 1)
        elif t == "button":
            button, down = _button(m), bool(m.get("down"))
            (self.held.add if down else self.held.discard)(button)
            await self.input(winput.mouse_button, button, down)
        elif t == "scroll":
            await self.input(winput.scroll, clamp_int(m.get("dy"), 2400), clamp_int(m.get("dx"), 2400))
        elif t == "text":
            await self.input(winput.type_text, str(m.get("text", ""))[:20000])
        elif t == "keys":
            keys = m.get("keys")
            if not isinstance(keys, list) or not 0 < len(keys) <= 6 or not all(isinstance(k, str) for k in keys):
                raise UserError("input.bad_keys", "Invalid key combination")
            await self.input(winput.press_keys, keys, max(1, min(500, clamp_int(m.get("repeat", 1)))))
        elif t == "next":
            self.credits = min(self.credits + 1, FRAME_WINDOW[self.codec])
            self.wake.set()
        elif t == "keyframe":  # the phone's decoder needs a keyframe (error or reset)
            self.force_frame = True
            self.wake.set()
        elif t == "stream":
            await self.set_stream(m)
        elif t == "monitors":
            self.monitors = await in_capture_thread(self.capturer, self.capturer.monitors)
            await self.send(t="monitors", monitors=self.monitors, monitor=self.monitor)
        elif t == "power":
            action = m.get("action")
            if action not in POWER_ACTIONS:
                raise UserError("power.bad_action", "Invalid power action")
            await self.toast(f"power.{action}")
            await asyncio.sleep(0.3)  # let the message reach the phone before the PC goes down
            self.spawn(self.run_bg(POWER_ACTIONS[action]))
        elif t == "brightness":
            reply = lambda value: {"t": "brightness", "value": value}  # noqa: E731
            if "value" in m:
                self.spawn(self.run_bg(system.set_brightness, clamp_int(m["value"], 100), reply=reply))
            else:
                self.spawn(self.run_bg(system.get_brightness, reply=reply))
        elif t == "clipboard_get":
            self.spawn(self.run_bg(clipboard.get_text, reply=lambda text: {"t": "clipboard", "text": text}))
        elif t == "clipboard_set":
            self.spawn(self.run_bg(clipboard.set_text, str(m.get("text", ""))[:200000],
                                   reply=lambda _: {"t": "toast", "code": "clipboard.sent"}))
        elif t == "open_url":
            self.spawn(self.run_bg(system.open_url, str(m.get("url", "")).strip(),
                                   reply=lambda _: {"t": "toast", "code": "url.opened"}))
        elif t == "ping":
            await self.send(t="pong", ts=m.get("ts"))
        elif t == "windows":  # subscribe to / unsubscribe from window list updates
            self.win_sub = bool(m.get("on", True))
            if self.win_sub:
                self.win_last = None
                self.win_refresh.set()
        elif t == "activate":
            self.spawn(self.activate_window(clamp_int(m.get("id"), HWND_LIMIT)))
        elif t == "switch_prev":
            self.spawn(self.switch_previous())
        elif t == "close_window":
            self.spawn(self.close_window(clamp_int(m.get("id"), HWND_LIMIT)))
        elif t == "thumbs":
            self.request_thumbnails([clamp_int(i, HWND_LIMIT) for i in m.get("ids", []) if isinstance(i, int)])

    async def release_buttons(self):
        for button in self.held:
            await self.input(winput.mouse_button, button, False)
        self.held.clear()
