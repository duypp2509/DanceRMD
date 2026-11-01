"""Admin mode: a scheduled task that starts DanceRMD elevated without a UAC prompt.

Windows (UIPI) blocks a normal process from controlling elevated windows such as Task Manager.
Creating the task needs one UAC confirmation; afterwards the app relaunches itself through the task
and gets administrator rights unattended, which matters when nobody is at the PC to click "Yes".
"""

import os
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from .. import APP_ID, APP_NAME
from ..errors import UserError
from ..win32.api import CREATE_NO_WINDOW
from ..win32.process import run_as_admin

TASK_NAME = f"{APP_NAME} (Admin)"


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)


def task_exists(name=TASK_NAME):
    return _schtasks("/query", "/tn", name).returncode == 0


def run_task():
    return _schtasks("/run", "/tn", TASK_NAME).returncode == 0


def task_xml(command, arguments, at_logon, run_level):
    user = escape(f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".lstrip("\\"))
    trigger = f"<LogonTrigger><Enabled>true</Enabled><UserId>{user}</UserId></LogonTrigger>" if at_logon else ""
    # Task Scheduler defaults would skip the task on battery, stop it after 3 days and lower its
    # CPU priority (7); override them so the app behaves as if started by hand.
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Runs {escape(APP_NAME)} with administrator rights</Description></RegistrationInfo>
  <Triggers>{trigger}</Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>{run_level}</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{escape(str(command))}</Command><Arguments>{escape(arguments)}</Arguments></Exec>
  </Actions>
</Task>
"""


def install_task(command, arguments, at_logon, run_level="HighestAvailable"):
    """Create or replace the task; ``at_logon`` also starts it when the user signs in.
    Shows the UAC prompt unless the app is already elevated."""
    xml = Path(tempfile.gettempdir()) / f"{APP_ID}-task.xml"
    xml.write_text(task_xml(command, arguments, at_logon, run_level), encoding="utf-16")
    try:
        params = f'/create /f /tn "{TASK_NAME}" /xml "{xml}"'
        if run_level == "HighestAvailable":
            code = run_as_admin("schtasks.exe", params)
        else:
            code = subprocess.run(f"schtasks.exe {params}", capture_output=True,
                                  creationflags=CREATE_NO_WINDOW).returncode
    finally:
        xml.unlink(missing_ok=True)
    if code != 0:
        raise UserError("task.create_failed", "Couldn't create the administrator task (error {code})", code=code)


def remove_task(name=TASK_NAME):
    if task_exists(name):
        run_as_admin("schtasks.exe", f'/delete /f /tn "{name}"')
