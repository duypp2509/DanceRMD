"""Power actions, display brightness, battery status and opening links."""

import ctypes
import os
import subprocess
from ctypes import wintypes

from ..errors import UserError
from .api import CREATE_NO_WINDOW, TOKEN_QUERY, advapi32, kernel32, user32
from .process import powershell
from .security import is_elevated

powrprof = ctypes.WinDLL("powrprof", use_last_error=True)


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = (("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD))


class LUID(ctypes.Structure):
    _fields_ = (("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG))


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = (("Luid", LUID), ("Attributes", wintypes.DWORD))


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = (("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1))


kernel32.GetSystemPowerStatus.argtypes = (ctypes.POINTER(SYSTEM_POWER_STATUS),)
advapi32.LookupPrivilegeValueW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID))
advapi32.AdjustTokenPrivileges.argtypes = (wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES),
                                           wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)
powrprof.SetSuspendState.argtypes = (wintypes.BOOLEAN, wintypes.BOOLEAN, wintypes.BOOLEAN)
powrprof.SetSuspendState.restype = wintypes.BOOLEAN

HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF = 0xFFFF, 0x0112, 0xF170, 2
TOKEN_ADJUST_PRIVILEGES, SE_PRIVILEGE_ENABLED = 0x20, 0x02


# --------------------------------------------------------------------------- #
# Power
# --------------------------------------------------------------------------- #
def lock():
    user32.LockWorkStation()


def display_off():
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)


def _enable_privilege(name):
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                     ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            raise ctypes.WinError(ctypes.get_last_error())
        tp = TOKEN_PRIVILEGES(1, (LUID_AND_ATTRIBUTES * 1)(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED)))
        advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None)
        err = ctypes.get_last_error()  # ERROR_NOT_ALL_ASSIGNED when the account lacks the privilege
        if err:
            raise ctypes.WinError(err)
    finally:
        kernel32.CloseHandle(token)


def _suspend(hibernate):
    _enable_privilege("SeShutdownPrivilege")
    if not powrprof.SetSuspendState(hibernate, False, False):
        raise ctypes.WinError(ctypes.get_last_error())


def sleep():
    _suspend(False)


def hibernate():
    _suspend(True)


def restart():
    subprocess.Popen(["shutdown", "/r", "/t", "0"], creationflags=CREATE_NO_WINDOW)


def shutdown():
    subprocess.Popen(["shutdown", "/s", "/t", "0"], creationflags=CREATE_NO_WINDOW)


# --------------------------------------------------------------------------- #
# Display and battery
# --------------------------------------------------------------------------- #
def get_brightness():
    """Built-in display brightness (0-100), or None when the display has no software control."""
    try:
        out = powershell("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
                         "-ErrorAction Stop | Select-Object -First 1).CurrentBrightness")
    except (UserError, subprocess.TimeoutExpired):
        return None
    return int(out) if out.isdigit() else None


def set_brightness(value):
    value = max(0, min(100, int(value)))
    powershell("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop"
               f" | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=0; Brightness={value}}}"
               " | Out-Null")
    return value


def battery():
    s = SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(s)) or s.BatteryFlag == 128 or s.BatteryLifePercent == 255:
        return None  # no battery (desktop PC) or unknown
    return {"percent": s.BatteryLifePercent, "charging": s.ACLineStatus == 1}


# --------------------------------------------------------------------------- #
# Links
# --------------------------------------------------------------------------- #
def open_url(url):
    if not url.lower().startswith(("http://", "https://")):
        raise UserError("url.bad_scheme", "Only http:// and https:// links can be opened")
    if is_elevated():
        subprocess.Popen(["explorer.exe", url])  # through Explorer, so the browser does not run elevated
    else:
        os.startfile(url)
