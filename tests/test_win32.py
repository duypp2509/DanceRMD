"""Pure helpers of the Windows layer (nothing is injected into the real desktop)."""

import xml.etree.ElementTree as ET

from dancermd.errors import UserError, error_payload
from dancermd.server.session import clamp_frac, clamp_int
from dancermd.services import elevation
from dancermd.win32 import input as winput

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_text_inputs_handle_newlines_and_surrogate_pairs():
    events = winput.text_inputs("a\n😀")
    keyboard = [e.ki for e in events]
    assert keyboard[0].wScan == ord("a") and keyboard[0].dwFlags == winput.KEYEVENTF_UNICODE
    assert keyboard[2].wVk == winput.VK_RETURN
    surrogates = [k.wScan for k in keyboard[4:] if not k.dwFlags & winput.KEYEVENTF_KEYUP]
    assert surrogates == [0xD83D, 0xDE00]


def test_unknown_key_is_a_user_error():
    try:
        winput.press_keys(["ctrl", "definitely-not-a-key"])
    except UserError as exc:
        assert exc.code == "input.unknown_key" and exc.params == {"key": "definitely-not-a-key"}
    else:
        raise AssertionError("expected UserError")


def test_clamping():
    assert clamp_int("12") == 12 and clamp_int(None) == 0 and clamp_int(10**9, 500) == 500
    assert clamp_frac(-1) == 0.0 and clamp_frac("0.25") == 0.25 and clamp_frac("x") == 0.0


def test_error_payload():
    assert error_payload(UserError("x.y", "Hello {name}", name="A")) == {
        "code": "x.y", "params": {"name": "A"}, "message": "Hello A"}
    assert error_payload(OSError("boom"))["code"] == "error.generic"


def test_task_xml_is_valid_and_configurable():
    xml = elevation.task_xml(r"C:\Apps\DanceRMD.exe", "--minimized", at_logon=True, run_level="HighestAvailable")
    root = ET.fromstring(xml.split("?>", 1)[1])
    assert root.find("t:Principals/t:Principal/t:RunLevel", NS).text == "HighestAvailable"
    assert root.find("t:Triggers/t:LogonTrigger", NS) is not None
    assert root.find("t:Settings/t:DisallowStartIfOnBatteries", NS).text == "false"
    assert root.find("t:Actions/t:Exec/t:Arguments", NS).text == "--minimized"
    plain = elevation.task_xml("a.exe", "", at_logon=False, run_level="LeastPrivilege")
    assert ET.fromstring(plain.split("?>", 1)[1]).find("t:Triggers/t:LogonTrigger", NS) is None
