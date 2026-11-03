"""HTTP and WebSocket behaviour against an in-process server (no input is sent to the desktop)."""

import asyncio

import pytest
from aiohttp.test_utils import TestClient, TestServer

from dancermd import config
from dancermd.server import Hooks, make_app


def run(coro):
    return asyncio.run(coro)


async def _client():
    cfg = config.load()
    app = make_app(cfg, 0, mode="cli", hooks=Hooks())
    client = TestClient(TestServer(app, host="127.0.0.1"))
    await client.start_server()
    return client, cfg


@pytest.mark.parametrize("path", ["/", "/dashboard", "/static/shared/i18n.js", "/icons/app-icon.png"])
def test_pages_are_served(path):
    async def scenario():
        client, _ = await _client()
        try:
            resp = await client.get(path)
            assert resp.status == 200
        finally:
            await client.close()
    run(scenario())


def test_state_hides_nothing_locally_and_rejects_form_posts():
    async def scenario():
        client, cfg = await _client()
        try:
            state = await (await client.get("/api/state")).json()
            assert state["token"] == cfg["token"] and state["admin"]["available"] is False
            resp = await client.post("/api/token", data="a=1",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
            assert resp.status == 403
        finally:
            await client.close()
    run(scenario())


def test_websocket_rejects_a_wrong_token():
    async def scenario():
        client, _ = await _client()
        try:
            ws = await client.ws_connect("/ws")
            await ws.send_json({"t": "auth", "token": "wrong"})
            msg = await ws.receive_json()
            assert msg == {"t": "auth_fail", "reason": {"code": "auth.invalid", "params": {},
                                                        "message": "Wrong access code"}}
            await ws.close()
        finally:
            await client.close()
    run(scenario())


def test_rotating_the_token_changes_it():
    async def scenario():
        client, cfg = await _client()
        try:
            before = cfg["token"]
            state = await (await client.post("/api/token", json={})).json()
            assert state["token"] != before and config.load()["token"] == state["token"]
        finally:
            await client.close()
    run(scenario())


def test_dashboard_defaults_to_english_and_the_dark_theme():
    async def scenario():
        client, _ = await _client()
        try:
            state = await (await client.get("/api/state")).json()
            assert state["language_setting"] == "en" and state["language"] == "en"
            assert state["theme"] == "dark"
        finally:
            await client.close()
    run(scenario())


def test_theme_is_saved_and_validated():
    async def scenario():
        client, _ = await _client()
        try:
            state = await (await client.post("/api/theme", json={"theme": "light"})).json()
            assert state["theme"] == "light" and config.load()["theme"] == "light"
            resp = await client.post("/api/theme", json={"theme": "pink"})
            assert resp.status == 400 and config.load()["theme"] == "light"
        finally:
            await client.close()
    run(scenario())
