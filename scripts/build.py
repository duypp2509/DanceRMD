"""Build dist/DanceRMD.exe: a single-file executable that runs without a Python installation.

    python scripts/build.py        (or scripts/build.bat, which installs the build dependencies first)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import PyInstaller.__main__  # noqa: E402

from dancermd import APP_ID, APP_NAME, VERSION, branding  # noqa: E402

BUILD = ROOT / "build"
DIST = ROOT / "dist"
PACKAGE = ROOT / "dancermd"
COPYRIGHT = "Copyright (c) 2026 Phạm Phúc Duy. MIT License."

# Shown in the executable's Properties > Details
VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', '{name}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{app_id}'),
      StringStruct('LegalCopyright', '{copyright}'),
      StringStruct('OriginalFilename', '{app_id}.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
# Not used at runtime; dxcam works with numpy, so OpenCV (about 70 MB) is left out
EXCLUDES = ("cv2", "tkinter", "matplotlib", "scipy", "pandas")
# Loaded dynamically, so PyInstaller can't discover them on its own
HIDDEN_IMPORTS = ("dxcam.processor._numpy_kernels",)


def version_file():
    parts = [int(x) for x in VERSION.split(".")]
    nums = tuple(parts + [0] * (4 - len(parts)))
    path = BUILD / "version_info.txt"
    path.write_text(VERSION_INFO.format(nums=nums, name=APP_NAME, version=VERSION, app_id=APP_ID,
                                        copyright=COPYRIGHT), "utf-8")
    return path


def main():
    BUILD.mkdir(exist_ok=True)
    icon = BUILD / "icon.ico"
    branding.write_ico(icon)
    args = [
        str(PACKAGE / "__main__.py"),
        "--name", APP_ID,
        "--onefile", "--windowed", "--noconfirm", "--clean",
        "--icon", str(icon),
        "--version-file", str(version_file()),
        "--paths", str(ROOT),
        "--collect-submodules", "dancermd",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
    ]
    for module in EXCLUDES:
        args += ["--exclude-module", module]
    for module in HIDDEN_IMPORTS:
        args += ["--hidden-import", module]
    for folder in ("web", "resources"):
        args += ["--add-data", f"{PACKAGE / folder}{os.pathsep}dancermd/{folder}"]
    PyInstaller.__main__.run(args)

    exe = DIST / f"{APP_ID}.exe"
    print(f"\nBuilt {exe} ({exe.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
