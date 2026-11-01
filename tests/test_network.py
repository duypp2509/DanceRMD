from dancermd.server import network


def test_device_kind():
    assert network.device_kind("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)") == "iphone"
    assert network.device_kind("Mozilla/5.0 (Linux; Android 14; Pixel 8)") == "android"
    assert network.device_kind("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "windows"
    assert network.device_kind("curl/8.0") == "browser"


def test_token_travels_in_fragment():
    assert network.lan_url("192.168.1.5", 8765, "abc") == "http://192.168.1.5:8765/#k=abc"
    assert network.access_url("https://x.trycloudflare.com", "abc") == "https://x.trycloudflare.com/#k=abc"


def test_lan_addresses_shape():
    addresses = network.lan_addresses()
    assert addresses
    assert all(a["kind"] in ("lan", "tailscale", "other", "local") and a["ip"] for a in addresses)
