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
"""Build a Windows installer carrying a worktree-local release channel."""

from pathlib import Path

from tools.pyinstaller_support import resolve_uv_executable


launcher_root = Path(SPECPATH)
repo_root = launcher_root.parent
release_root = repo_root / "build" / "local-test-release-channel"
app_icon_path = (
    repo_root
    / "substitute"
    / "presentation"
    / "resources"
    / "app_icons"
    / "app_icon.ico"
)
uv_path = resolve_uv_executable()
manifest_path = release_root / "manifest.json"
app_payloads = tuple(release_root.glob("SugarSubstitute-app-v*.zip"))
launcher_payloads = tuple(
    release_root.glob("SugarSubstitute-installer-payload-windows-x64-v*.zip")
)
if not manifest_path.is_file() or len(app_payloads) != 1 or len(launcher_payloads) != 1:
    raise FileNotFoundError(
        "Build the local test release channel before packaging this installer: "
        f"{release_root}"
    )

launcher_datas = [
    (str(app_icon_path), "launcher_assets"),
    (uv_path, "launcher_assets"),
    (str(manifest_path), "launcher_local_release"),
    (str(app_payloads[0]), "launcher_local_release"),
    (str(launcher_payloads[0]), "launcher_local_release"),
]

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
    name="SugarSubstitute-Local-Test-Installer-Windows-x64",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon_path),
)
