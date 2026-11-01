import json

from dancermd import config, paths


def test_load_creates_token(data_dir):
    cfg = config.load()
    assert len(cfg["token"]) >= 16 and cfg["paired"] is False
    assert json.loads(paths.CONFIG_PATH.read_text("utf-8"))["token"] == cfg["token"]


def test_load_keeps_token_and_rotates_on_request():
    first = config.load()["token"]
    assert config.load()["token"] == first
    assert config.load(rotate_token=True)["token"] != first


def test_unreadable_config_starts_fresh():
    paths.DATA_DIR.mkdir(parents=True)
    paths.CONFIG_PATH.write_text("{not json", "utf-8")
    assert config.load()["token"]


def test_legacy_settings_are_imported(monkeypatch):
    legacy = paths.LEGACY_DATA_DIR
    (legacy / "bin").mkdir(parents=True)
    (legacy / "config.json").write_text(json.dumps({"token": "paired-token", "paired": True}), "utf-8")
    (legacy / "bin" / "cloudflared.exe").write_bytes(b"MZ")
    monkeypatch.delenv(paths.HOME_ENV)
    cfg = config.load()
    assert cfg["token"] == "paired-token" and cfg["paired"] is True
    assert (paths.BIN_DIR / "cloudflared.exe").read_bytes() == b"MZ"


def test_legacy_settings_are_ignored_for_isolated_instances():
    paths.LEGACY_DATA_DIR.mkdir(parents=True)
    (paths.LEGACY_DATA_DIR / "config.json").write_text(json.dumps({"token": "paired-token"}), "utf-8")
    assert config.load()["token"] != "paired-token"
