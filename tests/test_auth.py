from aiohttp.test_utils import make_mocked_request

from dancermd.server.auth import AuthGuard, is_local, same_origin


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_guard_blocks_after_max_failures_and_recovers():
    clock = FakeClock()
    guard = AuthGuard(max_fail=3, window=60, clock=clock)
    for _ in range(3):
        assert not guard.blocked("1.2.3.4")
        guard.fail("1.2.3.4")
    assert guard.blocked("1.2.3.4")
    assert not guard.blocked("5.6.7.8")
    clock.now = 61
    assert not guard.blocked("1.2.3.4")


def test_guard_success_resets_failures():
    guard = AuthGuard(max_fail=2)
    guard.fail("ip")
    guard.success("ip")
    guard.fail("ip")
    assert not guard.blocked("ip")


def _request(host, remote="127.0.0.1", **headers):
    return make_mocked_request("GET", "/dashboard", headers={"Host": host, **headers},
                               transport=_Transport(remote))


class _Transport:
    def __init__(self, remote):
        self.remote = remote

    def get_extra_info(self, name, default=None):
        return (self.remote, 12345) if name == "peername" else default


def test_is_local_accepts_loopback_hosts():
    assert is_local(_request("127.0.0.1:8765"))
    assert is_local(_request("localhost:8765"))


def test_is_local_rejects_rebinding_and_tunnel():
    assert not is_local(_request("evil.example:8765"))
    assert not is_local(_request("127.0.0.1:8765", **{"CF-Connecting-IP": "203.0.113.9"}))
    assert not is_local(_request("127.0.0.1:8765", remote="192.168.1.20"))


def test_same_origin():
    assert same_origin(_request("127.0.0.1:8765"))
    assert same_origin(_request("127.0.0.1:8765", Origin="http://127.0.0.1:8765"))
    assert not same_origin(_request("127.0.0.1:8765", Origin="http://evil.example"))
