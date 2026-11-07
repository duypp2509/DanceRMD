# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-11-07

### Added
- Theme setting for the desktop app: dark (default), light, or follow Windows.

### Changed
- Redesigned desktop app window: a sidebar with a **Connect** page (QR code, connected phones, remote
  access, troubleshooting) and a **Settings** page (general, permissions, security, network,
  technical details). Choose "Same Wi-Fi" or "Over the Internet" with a toggle instead of an
  address list, and confirm a new access code in an in-app dialog.
- The desktop app starts in English. "Same as Windows" is still available in Settings > Language.

## [2.0.0] - 2026-11-01

The project is renamed from **Remote Laptop** to **DanceRMD**.

### Added
- English user interface alongside Vietnamese, for the phone, the dashboard and the tray menu.
  The language follows the device automatically and can be chosen in the settings.
- Language selector in the phone settings and in the dashboard.
- Product website (`website/`), deployed to GitHub Pages.
- Test suite (pytest), linting (ruff) and a continuous integration workflow.
- Documentation: architecture, WebSocket protocol, development and security policy.

### Changed
- The code is organized as the `dancermd` package (`server`, `media`, `win32`, `services`, `desktop`,
  `web`) and starts with `python -m dancermd`; the headless server is `python -m dancermd --headless`.
- New brand colors across the phone UI and the dashboard.
- The server sends translation codes instead of sentences, so every message follows the UI language.
- App icons are rendered on demand instead of being stored as generated files.
- The dashboard moved to `/dashboard` (`/pair` redirects).
- Settings live in `%APPDATA%\DanceRMD`; the log file is `dancermd.log`.

### Migration
- Settings from Remote Laptop 1.x are imported on first start, so paired phones keep working.
- Installing DanceRMD removes Remote Laptop's shortcuts, uninstall entry, autostart entry and admin
  task, and keeps "start with Windows" if it was on.

## Earlier releases (as Remote Laptop)

### 1.3.0
- Window switcher like Alt+Tab: quick-switch strip, grid with live thumbnails, close window,
  Show desktop, three-finger swipes, automatic monitor follow.
- Landscape layout with a side rail and slide-out drawers.

### 1.x
Milestones before 1.3.0, oldest first:
- Control a Windows laptop from a phone browser: screen streaming, touchpad, keyboard with Unicode
  typing, shortcuts, media keys, brightness, clipboard and power actions.
- Desktop app: dashboard window, system tray icon, single instance, start with Windows.
- Per-user installation with Start menu shortcuts and an uninstall entry; custom app icon.
- GPU pipeline: DXGI capture and hardware H.264 encoding, decoded with WebCodecs.
- Remote access through a Cloudflare quick tunnel.
- "Run as administrator" mode through a scheduled task, and a warning on the phone when an elevated
  window blocks input (UIPI).

[2.1.0]: https://github.com/duypp2509/DanceRMD/releases/tag/v2.1.0
[2.0.0]: https://github.com/duypp2509/DanceRMD/releases/tag/v2.0.0
