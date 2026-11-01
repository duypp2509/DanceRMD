"""Child processes: PowerShell, elevation (UAC) and lifetime binding."""

import ctypes
import subprocess
from ctypes import wintypes

from ..errors import UserError
from .api import CREATE_NO_WINDOW, kernel32, shell32
from .security import is_elevated


def powershell(script, timeout=15):
    """Run a PowerShell command and return its standard output."""
    res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    if res.returncode != 0:
        detail = res.stderr.strip().splitlines()[0] if res.stderr.strip() else f"exit code {res.returncode}"
        raise UserError("powershell.failed", "PowerShell failed: {detail}", detail=detail)
    return res.stdout.strip()


# --------------------------------------------------------------------------- #
# Elevation
# --------------------------------------------------------------------------- #
class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = (("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", wintypes.LPVOID), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE))


shell32.ShellExecuteW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.LPCWSTR, ctypes.c_int)
shell32.ShellExecuteW.restype = wintypes.HINSTANCE
shell32.ShellExecuteExW.argtypes = (ctypes.POINTER(_SHELLEXECUTEINFOW),)
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
SEE_MASK_NOCLOSEPROCESS, SEE_MASK_NOASYNC = 0x40, 0x100
ERROR_CANCELLED = 1223


def run_as_admin(file, params, timeout=120):
    """Run a program elevated and wait for it; returns the exit code. Shows the UAC prompt when needed."""
    if is_elevated():
        return subprocess.run(f'"{file}" {params}', capture_output=True, creationflags=CREATE_NO_WINDOW,
                              timeout=timeout).returncode
    info = _SHELLEXECUTEINFOW(cbSize=ctypes.sizeof(_SHELLEXECUTEINFOW),
                              fMask=SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC,
                              lpVerb="runas", lpFile=str(file), lpParameters=params, nShow=0)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.get_last_error() == ERROR_CANCELLED:
            raise UserError("uac.cancelled", "The administrator prompt was declined")
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        kernel32.WaitForSingleObject(info.hProcess, timeout * 1000)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return code.value
    finally:
        kernel32.CloseHandle(info.hProcess)


def run_elevated_script(script, *args):
    """Start a PowerShell script elevated in a visible window, without waiting for it."""
    params = f'-NoProfile -ExecutionPolicy Bypass -File "{script}" ' + " ".join(args)
    result = shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 1)
    if (result or 0) <= 32:
        raise UserError("uac.cancelled", "The administrator prompt was declined")


# --------------------------------------------------------------------------- #
# Lifetime binding
# --------------------------------------------------------------------------- #
class _IO_COUNTERS(ctypes.Structure):
    _fields_ = tuple((name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount"))


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD))


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t))


kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_job = None


def kill_with_this_process(popen):
    """Put a child process in a job object, so it ends with this app even if the app is killed."""
    global _job
    if _job is None:
        job = kernel32.CreateJobObjectW(None, None)
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                         ctypes.sizeof(info))
        _job = job
    kernel32.AssignProcessToJobObject(_job, int(popen._handle))
