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
"""PyInstaller app-bundle configuration for the Apple Silicon setup launcher."""

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
bundle_icon_path = repo_root / "build" / "app_icon.icns"
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
    a.binaries,
    a.datas,
    [],
    name="SugarSubstitute Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name="SugarSubstitute Setup.app",
    icon=str(bundle_icon_path),
    bundle_identifier="ai.artificialsweetener.sugarsubstitute.setup",
)
