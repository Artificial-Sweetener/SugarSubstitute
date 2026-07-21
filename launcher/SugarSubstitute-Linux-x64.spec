# -*- mode: python ; coding: utf-8 -*-
#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

# ruff: noqa: F821
"""PyInstaller onedir configuration for the installed Linux x64 launcher."""

from pathlib import Path

from tools.pyinstaller_support import build_launcher_data_files


launcher_root = Path(SPECPATH)
repo_root = launcher_root.parent
app_icon_path = (
    repo_root
    / "substitute"
    / "presentation"
    / "resources"
    / "app_icons"
    / "app_icon_256.png"
)
launcher_datas = build_launcher_data_files(
    repo_root=repo_root,
    app_icon_path=app_icon_path,
)

a = Analysis(
    [str(launcher_root / "sugarsubstitute_launcher" / "__main__.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=launcher_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cv2",
        "numpy",
        "PIL",
        "pytest",
        "scipy",
        "skimage",
        "torch",
        "torchaudio",
        "torchvision",
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name="SugarSubstitute",
    debug=False,
    bootloader_ignore_signals=False,
    exclude_binaries=True,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(app_icon_path),
    contents_directory="launcher-bin",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SugarSubstitute",
)
