# Development

## Setup

DanceRMD targets Windows 10/11 and Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt     # or: pip install -e .[dev]
```

## Running from source

```bash
python -m dancermd                      # desktop app: dashboard window + tray icon
python -m dancermd --headless           # console server; prints the links and a QR code
python -m dancermd --headless --port 8790 --new-token --no-browser
```

The desktop app and the headless server share the settings in `%APPDATA%\DanceRMD`. To run a
throwaway copy next to an installed one, give it its own data folder and port:

```powershell
$env:DANCERMD_HOME = "$env:TEMP\dancermd-dev"
python -m dancermd --port 8790
```

An isolated copy uses its own single-instance lock and never imports or removes the settings of
"Remote Laptop" 1.x.

The web UI has no build step: edit the files in `dancermd/web/` and reload the page on the phone (or in
a desktop browser with device emulation). Every UI file is served with `Cache-Control: no-cache`.

## Tests and linting

```bash
pytest          # about 40 tests, a few seconds
ruff check .
```

The suite covers the access-control rules, the token rate limiter, configuration and migration, the
encoders, Unicode input generation, the scheduled-task XML, the HTTP/WebSocket behaviour of an
in-process server and translation consistency. Tests never inject input into the desktop and always
use a temporary data directory (`tests/conftest.py`).

Things that need a real device are checked by hand before a release:

- [ ] Phone on the same Wi-Fi: QR code, touchpad, typing (including Vietnamese), shortcuts, clipboard.
- [ ] Remote access: tunnel link, H.264 on the phone (Settings shows "In use: H.264 · …").
- [ ] Window switcher: strip, grid with thumbnails, close, three-finger swipes, multi-monitor follow.
- [ ] Landscape layout on a small phone.
- [ ] Admin mode: UAC once, then Task Manager can be controlled; turning it off restarts unelevated.
- [ ] Install, update over a running copy, uninstall from Settings > Apps.

## Translations

- Web UI strings live in `dancermd/web/shared/locales/en.js` and `vi.js`. Markup uses `data-i18n`,
  `data-i18n-html` (trusted dictionary strings only) and `data-i18n-attr`; scripts call `I18N.t()`.
- Desktop strings (tray menu, notifications, dialogs) live in `dancermd/i18n.py`.
- Server code never sends sentences: raise `UserError("area.what", "English text", **params)` or send
  a toast code, and add the code to both locale files. `tests/test_i18n.py` fails when a code has no
  translation or when the two languages drift apart.

To add a language, copy `en.js` to `<code>.js`, translate it, load it from both HTML pages, add the
code to `i18n.SUPPORTED`, extend `STRINGS` in `dancermd/i18n.py` and add it to the language selectors.

## Building

```bash
python scripts/build.py                 # or scripts\build.bat
```

PyInstaller produces a single `dist\DanceRMD.exe` (about 70 MB) with the web UI and resources
embedded and the version information taken from `dancermd/__init__.py`. Opening the executable offers
to install it.

## Releasing

1. Update `__version__` in `dancermd/__init__.py` and add a section to `CHANGELOG.md`.
2. Run the tests and the manual checklist above.
3. Build `dist\DanceRMD.exe`.
4. Tag the commit (`git tag v2.0.0 && git push --tags`) and create a GitHub release with the
   executable attached. The website's download buttons point to `releases/latest`.

The website in `website/` deploys to GitHub Pages through `.github/workflows/pages.yml` on every push
to `main` that touches it (*Settings > Pages > Source: GitHub Actions*).

## Code style

- Python: formatted for a 120-column limit, imports sorted, checked by `ruff`. Comments explain *why*;
  Win32 constants get names instead of magic numbers.
- JavaScript: plain ES2020+ without a framework or bundler; `'use strict'`, small functions, DOM
  updates keyed by id so periodic refreshes never move a button under the user's finger.
- UI: touch targets of at least 44 px, visible focus, `aria-*` labels on icon-only buttons, and
  confirmation only for destructive power actions.
