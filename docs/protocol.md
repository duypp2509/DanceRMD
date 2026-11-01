# Protocol

The phone talks to DanceRMD over a single WebSocket at `/ws` (`wss://` through the tunnel). Text
messages are JSON objects with a `t` (type) field; screen frames are binary messages.

## Handshake

1. The client opens `/ws`. Cross-origin connections are rejected with HTTP 403.
2. Its first message must be `{"t": "auth", "token": "<access code>"}` within 10 seconds.
3. On success the server sends `hello`; otherwise `auth_fail` and closes the socket.

| Close code | Meaning | Client behaviour |
|---|---|---|
| 4000 | No valid `auth` message | Reconnect |
| 4001 | Wrong access code, or too many attempts | Show the sign-in screen |
| 4002 | Disconnected from the dashboard | Don't reconnect automatically |
| 4003 | The access code was changed | Forget the stored code, show the sign-in screen |

The token is taken from the URL fragment (`/#k=<token>`), stored in `localStorage` and removed from the
address bar.

## Binary frames

```
+--------+--------------------------------+
| 1 byte | payload                        |
+--------+--------------------------------+
  type     1 = JPEG image
           2 = H.264 keyframe (Annex B)
           3 = H.264 delta frame (Annex B)
```

Before the first H.264 keyframe, and whenever the encoder restarts, the server sends a `video`
message with the WebCodecs decoder configuration.

### Flow control

The server only sends while the session has credits. A `stream` message resets the credits to the
window size (2 for JPEG, 3 for H.264); every `next` from the client returns one. JPEG clients send
`next` after drawing a frame, H.264 clients after queuing it to the decoder.

## Client → server

| `t` | Fields | Effect |
|---|---|---|
| `auth` | `token` | First message, see above |
| `stream` | `on?`, `monitor?`, `quality?` (`low`/`medium`/`high`), `codec?` (`jpeg`/`h264`) | Change streaming settings; answered with `stream` |
| `next` | | Acknowledge a frame (returns one credit) |
| `keyframe` | | Request a keyframe (decoder error or reset) |
| `monitors` | | Re-read the monitor layout; answered with `monitors` |
| `move` | `dx`, `dy` | Relative pointer move in physical pixels |
| `moveto` | `x`, `y` (0–1) | Absolute position on the current monitor |
| `click` | `button` (`left`/`right`/`middle`), `double?` | Click |
| `button` | `button`, `down` | Press or release (drag and drop) |
| `scroll` | `dx`, `dy` | Wheel units (120 = one notch) |
| `text` | `text` | Type Unicode text (up to 20,000 characters) |
| `keys` | `keys` (1–6 names), `repeat?` | Key combination, e.g. `["ctrl", "shift", "esc"]` |
| `power` | `action` (`lock`/`display_off`/`sleep`/`hibernate`/`restart`/`shutdown`) | Power action |
| `brightness` | `value?` (0–100) | Set, or read when omitted; answered with `brightness` |
| `clipboard_get` | | Answered with `clipboard` |
| `clipboard_set` | `text` | Copy text to the PC clipboard |
| `open_url` | `url` (`http(s)://` only) | Open a link in the PC's default browser |
| `windows` | `on` | Subscribe to window list updates |
| `activate` | `id` | Bring a window to the front; answered with `activated` |
| `switch_prev` | | Alt+Tab once; answered with `activated` |
| `close_window` | `id` | Ask a window to close (`WM_CLOSE`) |
| `thumbs` | `ids` | Request thumbnails; answered with one `thumb` each |
| `ping` | `ts` | Answered with `pong` carrying the same `ts` |

Key names: `backspace tab enter shift ctrl alt pause capslock esc space pageup pagedown end home left up
right down printscreen insert delete win menu volume_mute volume_down volume_up media_next media_prev
media_stop media_play_pause f1`–`f12`, or any single character.

## Server → client

| `t` | Fields | Sent |
|---|---|---|
| `hello` | `host`, `version`, `monitors`, `monitor`, `battery`, `qualities` | After authentication |
| `auth_fail` | `reason` (error payload) | Before closing with 4001 |
| `stream` | `on`, `monitor`, `quality`, `codec`, `encoder`, `capture` | After every `stream` request, and when the stream follows a window to another monitor |
| `video` | `codec`, `config` (e.g. `avc1.640033`), `width`, `height`, `encoder` | Before H.264 keyframes that change the configuration |
| `monitors` | `monitors`, `monitor` | Answer to `monitors` |
| `cursor` | `x`, `y` (0–1 on the current monitor) | Up to 30 times per second while streaming |
| `sys` | `battery` (`{percent, charging}` or `null`) | Every 30 seconds |
| `windows` | `list`, `icons` (new icons only), `multi` | When the window list changes (subscribed clients) |
| `thumb` | `id`, `data` (JPEG data URL) | Answer to `thumbs` |
| `activated` | `id`, `ok`, `title`, `reason` | After `activate` / `switch_prev` |
| `uipi` | `title` (or `null`), `hint` (code) | When an elevated window starts or stops blocking input |
| `brightness` | `value` (or `null` when unsupported) | Answer to `brightness` |
| `clipboard` | `text` | Answer to `clipboard_get` |
| `toast` | `code`, `params`, `message?`, `error` | Notices and errors |
| `pong` | `ts` | Answer to `ping` |

A monitor is `{index, left, top, width, height, primary, name}` in physical pixels. A window is
`{id, title, app, icon, min, fg, mon}`; `icon` is a key into the `icons` map, `fg` marks the active
window, `mon` the monitor index (or `null` when minimized).

## Errors and notices

The server never sends user-facing sentences. Errors and notices carry a translation code:

```json
{"t": "toast", "error": true, "code": "input.unknown_key", "params": {"key": "foo"}, "message": "Unsupported key: foo"}
```

The client looks `code` up in `web/shared/locales/<lang>.js` and fills in `params`; `message` is the
English fallback. The same payload shape is used for `auth_fail.reason`, `activated.reason`, the
tunnel status and dashboard API errors (`{"ok": false, "error": {...}}`).

## Dashboard API

Every route is restricted to this PC: loopback client address, loopback `Host` header, no Cloudflare
headers. `POST` requests must be same-origin with `Content-Type: application/json`.

| Method and path | Body | Result |
|---|---|---|
| `GET /dashboard` | | The dashboard page (`/pair` redirects here) |
| `GET /api/state` | | Links and QR codes, devices, tunnel, options, GPU info |
| `POST /api/token` | `{}` | New access code; disconnects every phone (4003) |
| `POST /api/kick` | `{"id": n}` | Disconnect one phone (4002) |
| `POST /api/tunnel` | `{"enabled": bool}` | Start or stop remote access (remembered) |
| `POST /api/autostart` | `{"enabled": bool}` | Start with Windows |
| `POST /api/admin` | `{"enabled": bool}` | Admin mode; the app restarts (desktop only) |
| `POST /api/language` | `{"language": "auto" \| "en" \| "vi"}` | Dashboard and tray language |
| `POST /api/firewall` | `{}` | Run the firewall script elevated |
| `POST /api/install` | `{}` | Install the running executable (packaged build only) |
| `POST /api/show` | `{}` | Bring the window to the front (used by a second launch) |
| `POST /api/quit` | `{}` | Exit (used by an installer replacing the executable) |
