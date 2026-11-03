# Security

DanceRMD gives full control of a Windows PC to whoever holds its access code. This document describes
what protects that code and the PC, the known limits, and how to report a vulnerability.

## Threat model

| Asset | Protection |
|---|---|
| Control of the PC | Every WebSocket connection must present the access code (96 random bits from `secrets`), compared in constant time. |
| The access code | Generated per installation and stored in `%APPDATA%\DanceRMD\config.json`. It travels in the URL fragment (`#k=`), which browsers never send over the network, and is removed from the address bar after the first load. |
| Guessing | 5 wrong codes within a minute block the client address for a minute. Through the tunnel the real client address (`CF-Connecting-IP`) is used. |
| The dashboard (shows the code) | Served only to this PC: loopback peer address, loopback `Host` header (defeats DNS rebinding), and no Cloudflare headers (requests relayed by the tunnel also come from 127.0.0.1). |
| Settings changes | `POST` requests must be same-origin `application/json`, which a foreign web page cannot send without a CORS preflight (CSRF). |
| Cross-site WebSockets | The `Origin` header must match the host. |
| Downloaded `cloudflared` | Fetched over HTTPS from Cloudflare's GitHub releases and run only if its Authenticode signature verifies (`WinVerifyTrust`). |
| Elevated mode | Opt-in. The scheduled task runs the installed executable for the current user only; links opened from the phone still start unelevated. |

## Known limits

- **Wi-Fi link**: plain HTTP inside the local network. Someone able to capture the traffic can read
  the screen and the access code. Use remote access (HTTPS) on networks you don't trust.
- **Remote access**: TLS is terminated by Cloudflare, which can technically see the traffic. Anyone
  with both the link and the code can connect, so treat the link like a password; the tray shows a
  notification for every new connection, and **Change code** revokes every phone at once.
- **Local users**: other processes running as the same Windows user can read the configuration file.
- **Secure desktop**: the lock screen and UAC prompts cannot be controlled, by design of Windows.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/duypp2509/DanceRMD/security/advisories/new) with
the affected version, the steps to reproduce and the impact. You can expect an acknowledgement within
a week. Fixes are released as a new version and credited in the changelog unless you prefer otherwise.

## Supported versions

Only the latest release receives security fixes.
