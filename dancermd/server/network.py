"""Network addresses, connection links and client identification."""

import ipaddress
import socket

TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")
_ADDRESS_ORDER = {"lan": 0, "tailscale": 1, "other": 2}
_DEVICES = (("iPhone", "iphone"), ("iPad", "ipad"), ("Android", "android"), ("Windows", "windows"),
            ("Macintosh", "mac"))


def lan_addresses():
    """[{"kind", "ip"}] with the primary network first, then Tailscale, then other adapters.
    ``kind`` is "lan", "tailscale", "other", or "local" when no network is available."""
    primary = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # UDP connect sends nothing; it only resolves the default route
            primary = s.getsockname()[0]
    except OSError:
        pass
    ips = [primary] if primary else []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith(("127.", "169.254.")):
                ips.append(ip)
    except OSError:
        pass
    result = []
    for ip in ips:
        if ipaddress.ip_address(ip) in TAILSCALE_NET:
            kind = "tailscale"
        elif ip == primary:
            kind = "lan"
        else:
            kind = "other"
        result.append({"kind": kind, "ip": ip})
    result.sort(key=lambda a: _ADDRESS_ORDER[a["kind"]])
    return result or [{"kind": "local", "ip": "127.0.0.1"}]


def access_url(base, token):
    """Connection link; the token travels in the fragment, which browsers never send to servers."""
    return f"{base}/#k={token}"


def lan_url(ip, port, token):
    return access_url(f"http://{ip}:{port}", token)


def client_ip(request):
    """The phone's real address. Through Cloudflare Tunnel, requests arrive from 127.0.0.1 carrying
    a CF-Connecting-IP header."""
    forwarded = request.headers.get("CF-Connecting-IP")
    if forwarded and request.remote in ("127.0.0.1", "::1"):
        return forwarded
    return request.remote


def device_kind(user_agent):
    """A coarse device type for display: iphone, ipad, android, windows, mac or browser."""
    for marker, kind in _DEVICES:
        if marker in user_agent:
            return kind
    return "browser"
