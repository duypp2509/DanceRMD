"""Shared fixtures. Every test runs against a temporary data directory, never the real one."""

import pytest

from dancermd import paths


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(paths, "DATA_DIR", home)
    monkeypatch.setattr(paths, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(paths, "LOG_PATH", home / "dancermd.log")
    monkeypatch.setattr(paths, "CACHE_DIR", home / "cache")
    monkeypatch.setattr(paths, "BIN_DIR", home / "bin")
    monkeypatch.setattr(paths, "LEGACY_DATA_DIR", tmp_path / "legacy")
    monkeypatch.setenv(paths.HOME_ENV, str(home))
    return home
