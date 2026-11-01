"""Top-level application windows, as listed by Alt+Tab: titles, icons, thumbnails, activate and close."""

import base64
import ctypes
import io
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image

from ..errors import UserError
from .api import PROCESS_QUERY_LIMITED_INFORMATION, kernel32, user32, window_pid, window_title

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
version = ctypes.WinDLL("version")

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.GetShellWindow.restype = wintypes.HWND
user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
user32.SendMessageTimeoutW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t))
user32.SendMessageTimeoutW.restype = ctypes.c_size_t
user32.GetClassLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetClassLongPtrW.restype = ctypes.c_size_t
user32.PrivateExtractIconsW.argtypes = (wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT),
                                        wintypes.UINT, wintypes.UINT)
user32.DrawIconEx.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT, wintypes.HBRUSH, wintypes.UINT)
user32.DestroyIcon.argtypes = (wintypes.HICON,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SwitchToThisWindow.argtypes = (wintypes.HWND, wintypes.BOOL)
user32.PrintWindow.argtypes = (wintypes.HWND, wintypes.HDC, wintypes.UINT)
user32.GetDC.argtypes = (wintypes.HWND,)
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
user32.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t)
gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = (wintypes.HDC, wintypes.LPVOID, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD)
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (wintypes.HDC,)
dwmapi.DwmGetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD)
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD))
version.GetFileVersionInfoSizeW.argtypes = (wintypes.LPCWSTR, wintypes.LPVOID)
version.GetFileVersionInfoW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID)
version.VerQueryValueW.argtypes = (wintypes.LPCVOID, wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID),
                                   ctypes.POINTER(wintypes.UINT))


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = (("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD))


GW_OWNER, GWL_EXSTYLE = 4, -20
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW, WS_EX_NOACTIVATE = 0x80, 0x40000, 0x08000000
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14
WM_GETICON, WM_CLOSE = 0x7F, 0x0010
ICON_SMALL, ICON_BIG, ICON_SMALL2 = 0, 1, 2
GCLP_HICON, GCLP_HICONSM = -14, -34
SMTO_ABORTIFHUNG = 0x2
SW_RESTORE = 9
DI_NORMAL = 3
PW_RENDERFULLCONTENT = 2
VK_MENU, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x12, 0x1, 0x2
# UWP apps (Settings, Calculator...) live in this shared host process: use the window title as app name
HOST_EXES = {"applicationframehost.exe"}
ICON_SIZE = 64

_app_names = {}
_icons = {}  # icon key -> PNG data URL


# --------------------------------------------------------------------------- #
# Window list
# --------------------------------------------------------------------------- #
def _exe_path(hwnd):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, window_pid(hwnd))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else ""
    finally:
        kernel32.CloseHandle(handle)


def _is_host(exe):
    return Path(exe.lower()).name in HOST_EXES


def _app_name(exe, title):
    """Friendly application name: the FileDescription of the executable, e.g. "Google Chrome"."""
    key = exe.lower()
    if not exe or _is_host(exe):
        return title
    if key not in _app_names:
        name = ""
        size = version.GetFileVersionInfoSizeW(exe, None)
        if size:
            data = ctypes.create_string_buffer(size)
            if version.GetFileVersionInfoW(exe, 0, size, data):
                ptr, length = wintypes.LPVOID(), wintypes.UINT()
                if version.VerQueryValueW(data, r"\VarFileInfo\Translation", ctypes.byref(ptr), ctypes.byref(length)) \
                        and length.value >= 4:
                    lang, codepage = ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD * 2)).contents
                    query = rf"\StringFileInfo\{lang:04x}{codepage:04x}\FileDescription"
                    if version.VerQueryValueW(data, query, ctypes.byref(ptr), ctypes.byref(length)) and length.value:
                        name = ctypes.wstring_at(ptr, length.value).rstrip("\x00").strip()
        _app_names[key] = name or Path(exe).stem
    return _app_names[key]


def _is_alt_tab_window(hwnd, shell):
    """The Alt+Tab criteria: a visible, non-tool, non-owned top-level window that is not cloaked."""
    if hwnd == shell or not user32.IsWindowVisible(hwnd):
        return False
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    owned_or_tool = user32.GetWindow(hwnd, GW_OWNER) or ex & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    if owned_or_tool and not ex & WS_EX_APPWINDOW:
        return False
    cloaked = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return not cloaked.value  # cloaked: suspended UWP app, window on another virtual desktop...


def _center(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2


def list_windows():
    """Windows in Alt+Tab order (most recently used first). ``icon`` is a key for icon_data()."""
    shell, foreground = user32.GetShellWindow(), user32.GetForegroundWindow()
    found = []

    @WNDENUMPROC
    def visit(hwnd, _):
        if _is_alt_tab_window(hwnd, shell) and window_title(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    windows = []
    for hwnd in found:
        title, exe = window_title(hwnd), _exe_path(hwnd)
        windows.append({
            "id": hwnd, "title": title, "app": _app_name(exe, title), "icon": _icon_key(hwnd, exe),
            "min": bool(user32.IsIconic(hwnd)), "fg": hwnd == foreground, "center": _center(hwnd),
        })
    return windows


# --------------------------------------------------------------------------- #
# Icons
# --------------------------------------------------------------------------- #
def _render_icon(hicon, size):
    """Draw an HICON into an RGBA image. Drawing on black and on white and comparing the two recovers
    the alpha channel for both legacy (mask-based) and 32-bit alpha icons."""
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), size, -size, 1, 32, 0)
    hdc = gdi32.CreateCompatibleDC(None)
    layers = []
    try:
        for background in (0x00, 0xFF):
            bits = ctypes.c_void_p()
            bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
            old = gdi32.SelectObject(hdc, bitmap)
            ctypes.memset(bits, background, size * size * 4)
            user32.DrawIconEx(hdc, 0, 0, hicon, size, size, 0, None, DI_NORMAL)
            layers.append(np.frombuffer(ctypes.string_at(bits, size * size * 4), np.uint8)
                          .reshape(size, size, 4)[:, :, :3].astype(np.float32))
            gdi32.SelectObject(hdc, old)
            gdi32.DeleteObject(bitmap)
    finally:
        gdi32.DeleteDC(hdc)
    on_black, on_white = layers
    alpha = np.clip(255 - (on_white - on_black).max(axis=2), 0, 255)
    color = np.where(alpha[..., None] > 0, on_black * 255 / np.maximum(alpha[..., None], 1), 0)
    rgba = np.dstack([np.clip(color[..., ::-1], 0, 255), alpha]).astype(np.uint8)  # BGR -> RGB
    return Image.fromarray(rgba, "RGBA")


def _icon_handle(hwnd, exe, size):
    """(HICON, must_destroy). Prefer the icon inside the executable: it stays sharp at large sizes."""
    if exe and not _is_host(exe):
        icon = wintypes.HICON()
        if user32.PrivateExtractIconsW(exe, 0, size, size, ctypes.byref(icon), None, 1, 0) == 1 and icon:
            return icon.value, True
    result = ctypes.c_size_t()
    for kind in (ICON_BIG, ICON_SMALL2, ICON_SMALL):
        if user32.SendMessageTimeoutW(hwnd, WM_GETICON, kind, 0, SMTO_ABORTIFHUNG, 100, ctypes.byref(result)) \
                and result.value:
            return result.value, False
    for index in (GCLP_HICON, GCLP_HICONSM):
        handle = user32.GetClassLongPtrW(hwnd, index)
        if handle:
            return handle, False
    return None, False


def _icon_key(hwnd, exe):
    key = exe.lower() if exe and not _is_host(exe) else f"w{hwnd}"
    if key not in _icons:
        _icons[key] = None
        handle, owned = _icon_handle(hwnd, exe, ICON_SIZE)
        if handle:
            try:
                buf = io.BytesIO()
                _render_icon(handle, ICON_SIZE).save(buf, "PNG", optimize=True)
                _icons[key] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            except Exception:
                pass
            finally:
                if owned:
                    user32.DestroyIcon(handle)
    return key if _icons[key] else None


def icon_data(key):
    return _icons.get(key)


# --------------------------------------------------------------------------- #
# Thumbnails, activation, closing
# --------------------------------------------------------------------------- #
def thumbnail(hwnd, width=360):
    """JPEG data URL of the window content, even when other windows cover it. None when minimized or
    when the window can't be captured."""
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None
    rect, frame = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0 or w * h > 40_000_000:
        return None
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0)
    screen = user32.GetDC(None)
    hdc = gdi32.CreateCompatibleDC(screen)
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(hdc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT):  # also captures GPU-rendered apps
            return None
        img = Image.frombuffer("RGB", (w, h), ctypes.string_at(bits, w * h * 4), "raw", "BGRX", 0, 1)
    finally:
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc)
        user32.ReleaseDC(None, screen)
    # Windows 10/11 draw an invisible resize border: crop to the visible frame
    if not dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(frame), ctypes.sizeof(frame)):
        box = (frame.left - rect.left, frame.top - rect.top, frame.right - rect.left, frame.bottom - rect.top)
        if 0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h:
            img = img.crop(box)
    if max(hi for _, hi in img.getextrema()) < 12:  # all black: the app refuses to be captured
        return None
    img.thumbnail((width, width), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def title(hwnd):
    return window_title(hwnd)


def center(hwnd):
    return _center(hwnd)


def foreground():
    return user32.GetForegroundWindow()


def _wait_foreground(hwnd, timeout=0.3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.02)
    return False


def _require(hwnd):
    if not user32.IsWindow(hwnd):
        raise UserError("window.closed", "This window has already been closed")


def activate(hwnd):
    """Bring a window to the front, like picking it in Alt+Tab. Windows restricts background processes
    from stealing focus, so try the techniques window switchers commonly rely on, in order."""
    _require(hwnd)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    if _wait_foreground(hwnd, 0.1):
        return True
    # While Alt is held, Windows allows changing the foreground window (as during Alt+Tab)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    if _wait_foreground(hwnd):
        return True
    user32.SwitchToThisWindow(hwnd, True)
    return _wait_foreground(hwnd)


def close(hwnd):
    """Ask a window to close, like clicking its X (the app may still prompt to save)."""
    _require(hwnd)
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
