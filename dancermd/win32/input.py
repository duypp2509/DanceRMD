"""Mouse and keyboard injection with SendInput, including Unicode text (any language, emoji)."""

import ctypes
import time
from ctypes import wintypes

from ..errors import UserError
from .api import cursor_pos, user32

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR))


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR))


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD))


class _INPUTUNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (("type", wintypes.DWORD), ("u", _INPUTUNION))


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0001, 0x0002, 0x0004
BUTTONS = ("left", "right", "middle")


def enable_dpi_awareness():
    """Use physical pixels everywhere, so cursor coordinates match the captured frames at 125%/150% scaling."""
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    except AttributeError:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


def _send(inputs):
    if inputs:
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


# --------------------------------------------------------------------------- #
# Mouse
# --------------------------------------------------------------------------- #
_BUTTON_FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}


def _mouse_input(flags, data=0):
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi = MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    return inp


def move_to(x, y):
    user32.SetCursorPos(int(x), int(y))


def move_by(dx, dy):
    pos = cursor_pos()
    if pos:
        move_to(pos[0] + dx, pos[1] + dy)


def mouse_button(button, down):
    _send([_mouse_input(_BUTTON_FLAGS[button][0 if down else 1])])


def click(button="left", count=1):
    down, up = _BUTTON_FLAGS[button]
    _send([_mouse_input(flag) for _ in range(count) for flag in (down, up)])


def scroll(dy=0, dx=0):
    """dy > 0 scrolls up, dx > 0 scrolls right; 120 units is one wheel notch."""
    inputs = []
    if dy:
        inputs.append(_mouse_input(MOUSEEVENTF_WHEEL, dy))
    if dx:
        inputs.append(_mouse_input(MOUSEEVENTF_HWHEEL, dx))
    _send(inputs)


# --------------------------------------------------------------------------- #
# Keyboard
# --------------------------------------------------------------------------- #
VK = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0xA0, "ctrl": 0xA2, "alt": 0xA4,
    "pause": 0x13, "capslock": 0x14, "esc": 0x1B, "space": 0x20,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E, "win": 0x5B, "menu": 0x5D,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "media_next": 0xB0, "media_prev": 0xB1, "media_stop": 0xB2, "media_play_pause": 0xB3,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
# Keys that need the "extended" flag to be recognized (arrows, Home/End, Win, media keys...)
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D,
             0xA3, 0xA5, *range(0xAD, 0xB4)}
VK_RETURN, VK_TAB = 0x0D, 0x09


def _vk(name):
    name = name.lower()
    if name in VK:
        return VK[name]
    if len(name) == 1:
        res = user32.VkKeyScanW(name)
        if res != -1:
            return res & 0xFF
    raise UserError("input.unknown_key", "Unsupported key: {key}", key=name)


def _key_input(vk, up=False):
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED else 0)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), flags, 0, 0)
    return inp


def press_keys(names, repeat=1):
    """Press a key combination such as ["ctrl", "c"]; the last key is pressed ``repeat`` times."""
    vks = [_vk(n) for n in names]
    mods, key = vks[:-1], vks[-1]
    seq = [_key_input(vk) for vk in mods]
    for _ in range(repeat):
        seq += [_key_input(key), _key_input(key, up=True)]
    seq += [_key_input(vk, up=True) for vk in reversed(mods)]
    _send(seq)


def text_inputs(text):
    """INPUT events that type ``text`` independently of the keyboard layout."""
    seq = []
    for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
        if ch in "\n\t":
            vk = VK_RETURN if ch == "\n" else VK_TAB
            seq += [_key_input(vk), _key_input(vk, up=True)]
            continue
        # Send the UTF-16 code units directly (characters outside the BMP become surrogate pairs)
        units = ch.encode("utf-16-le")
        for i in range(0, len(units), 2):
            code = int.from_bytes(units[i:i + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.ki = KEYBDINPUT(0, code, flags, 0, 0)
                seq.append(inp)
    return seq


def type_text(text, chunk=400):
    seq = text_inputs(text)
    # Small batches so slow applications don't drop characters when a long text is pasted
    for i in range(0, len(seq), chunk):
        _send(seq[i:i + chunk])
        if i + chunk < len(seq):
            time.sleep(0.01)
