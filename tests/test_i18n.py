"""Translation consistency: every language has the same keys, and every server message has a translation."""

import re
from pathlib import Path

from dancermd import i18n
from dancermd.server.session import POWER_ACTIONS

PACKAGE = Path(__file__).resolve().parent.parent / "dancermd"
LOCALES = PACKAGE / "web" / "shared" / "locales"
KEY_RE = re.compile(r"^\s*'([\w.]+)':", re.MULTILINE)
SERVER_CODE_RES = (
    re.compile(r'UserError\(\s*"([\w.]+)"'),
    re.compile(r'(?:toast|_set_message)\("([\w.]+)"'),
    re.compile(r'"code": "([\w.]+)"'),
    re.compile(r'"(uipi\.hint_\w+)"'),
)


def js_keys(lang):
    return KEY_RE.findall((LOCALES / f"{lang}.js").read_text("utf-8"))


def server_codes():
    codes = {"error.generic"} | {f"power.{action}" for action in POWER_ACTIONS}
    for source in PACKAGE.rglob("*.py"):
        text = source.read_text("utf-8")
        for pattern in SERVER_CODE_RES:
            codes.update(pattern.findall(text))
    return codes


def test_python_languages_have_the_same_keys():
    assert set(i18n.STRINGS["en"]) == set(i18n.STRINGS["vi"])


def test_python_strings_format():
    i18n.set_language("vi")
    assert "DanceRMD" in i18n.t("tray.open")
    assert "2" in i18n.t("tray.connected", count=2)
    i18n.set_language("en")
    assert i18n.t("notify.phone_connected", device="iPhone", ip="10.0.0.2").startswith("iPhone (10.0.0.2)")


def test_resolve_falls_back_to_system_language():
    assert i18n.resolve("vi") == "vi"
    assert i18n.resolve("auto") in i18n.SUPPORTED
    assert i18n.resolve("xx") in i18n.SUPPORTED


def test_web_locales_have_the_same_keys_without_duplicates():
    en, vi = js_keys("en"), js_keys("vi")
    assert len(en) == len(set(en)), "duplicate keys in en.js"
    assert len(vi) == len(set(vi)), "duplicate keys in vi.js"
    assert set(en) == set(vi)


def test_every_server_message_is_translated():
    missing = server_codes() - set(js_keys("en"))
    assert not missing, f"server codes without a translation: {sorted(missing)}"


def test_device_kinds_are_translated_everywhere():
    kinds = {"iphone", "ipad", "android", "windows", "mac", "browser"}
    assert {f"device.{k}" for k in kinds} <= set(js_keys("en"))
    assert {f"device.{k}" for k in kinds} <= set(i18n.STRINGS["en"])
