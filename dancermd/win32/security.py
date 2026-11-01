"""Integrity levels, UIPI detection and Authenticode verification.

User Interface Privilege Isolation (UIPI) stops a normal process from sending input to windows of a
more privileged process, such as Task Manager for an administrator account. These helpers detect
that situation so the UI can explain it instead of failing silently.
"""

import ctypes
from ctypes import wintypes

from .api import (
    PROCESS_QUERY_LIMITED_INFORMATION,
    TOKEN_QUERY,
    advapi32,
    cursor_pos,
    kernel32,
    user32,
    window_pid,
    window_title,
)

advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD))
advapi32.GetSidSubAuthorityCount.argtypes = (wintypes.LPVOID,)
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = (wintypes.LPVOID, wintypes.DWORD)
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
user32.WindowFromPoint.argtypes = (wintypes.POINT,)
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND

INTEGRITY_MEDIUM, INTEGRITY_HIGH = 0x2000, 0x3000
TOKEN_INTEGRITY_LEVEL = 25
GA_ROOT = 2
_my_integrity = None


def _token_integrity(process_handle):
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        buf = ctypes.create_string_buffer(64)
        size = wintypes.DWORD()
        if not advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, buf, len(buf), ctypes.byref(size)):
            return None
        sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        return advapi32.GetSidSubAuthority(sid, advapi32.GetSidSubAuthorityCount(sid)[0] - 1)[0]
    finally:
        kernel32.CloseHandle(token)


def my_integrity():
    global _my_integrity
    if _my_integrity is None:
        _my_integrity = _token_integrity(kernel32.GetCurrentProcess()) or INTEGRITY_MEDIUM
    return _my_integrity


def is_elevated():
    return my_integrity() >= INTEGRITY_HIGH


def process_integrity(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        return _token_integrity(handle)
    finally:
        kernel32.CloseHandle(handle)


def blocked_window_title(max_len=50):
    """Title of a more privileged window that UIPI shields from our input (the active window or the
    one under the cursor), or None when input is not blocked."""
    mine = my_integrity()
    windows = [user32.GetForegroundWindow()]
    pos = cursor_pos()
    if pos:
        windows.append(user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(*pos)), GA_ROOT))
    for hwnd in windows:
        pid = window_pid(hwnd) if hwnd else 0
        if pid and (process_integrity(pid) or 0) > mine:
            name = window_title(hwnd, 256) or "Administrator window"
            return name if len(name) <= max_len else name[:max_len - 1] + "…"
    return None


# --------------------------------------------------------------------------- #
# Authenticode
# --------------------------------------------------------------------------- #
class _GUID(ctypes.Structure):
    _fields_ = (("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8))


class _WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = (("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE),
                ("pgKnownSubject", ctypes.c_void_p))


class _WINTRUST_DATA(ctypes.Structure):
    _fields_ = (("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", wintypes.LPVOID),
                ("pSIPClientData", wintypes.LPVOID), ("dwUIChoice", wintypes.DWORD),
                ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                ("pFile", ctypes.POINTER(_WINTRUST_FILE_INFO)), ("dwStateAction", wintypes.DWORD),
                ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPCWSTR),
                ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                ("pSignatureSettings", wintypes.LPVOID))


wintrust = ctypes.WinDLL("wintrust")
wintrust.WinVerifyTrust.argtypes = (wintypes.HWND, ctypes.POINTER(_GUID), ctypes.POINTER(_WINTRUST_DATA))
wintrust.WinVerifyTrust.restype = ctypes.c_long
WINTRUST_ACTION_GENERIC_VERIFY_V2 = _GUID(0x00AAC56B, 0xCD44, 0x11D0,
                                          (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
WTD_UI_NONE, WTD_CHOICE_FILE, WTD_STATEACTION_VERIFY, WTD_STATEACTION_CLOSE = 2, 1, 1, 2


def has_valid_signature(path):
    """Whether the file carries a valid Authenticode signature (the check Windows runs before launching it)."""
    info = _WINTRUST_FILE_INFO(ctypes.sizeof(_WINTRUST_FILE_INFO), str(path), None, None)
    data = _WINTRUST_DATA(cbStruct=ctypes.sizeof(_WINTRUST_DATA), dwUIChoice=WTD_UI_NONE,
                          dwUnionChoice=WTD_CHOICE_FILE, pFile=ctypes.pointer(info),
                          dwStateAction=WTD_STATEACTION_VERIFY)
    action = ctypes.byref(WINTRUST_ACTION_GENERIC_VERIFY_V2)
    result = wintrust.WinVerifyTrust(wintypes.HWND(-1), action, ctypes.byref(data))
    data.dwStateAction = WTD_STATEACTION_CLOSE
    wintrust.WinVerifyTrust(wintypes.HWND(-1), action, ctypes.byref(data))
    return result == 0
