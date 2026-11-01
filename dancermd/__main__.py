"""Entry point for ``python -m dancermd`` and the PyInstaller executable.

    python -m dancermd              desktop app (window + tray icon)
    python -m dancermd --headless   console server, see dancermd.cli
"""

import sys
from pathlib import Path

if not __package__:
    # Executed as a plain script (PyInstaller, autostart from source): make the package importable.
    sys.path[0] = str(Path(__file__).resolve().parent.parent)


def run():
    if "--headless" in sys.argv[1:]:
        sys.argv.remove("--headless")
        from dancermd.cli import main
    else:
        from dancermd.desktop.main import main
    main()


if __name__ == "__main__":
    run()
