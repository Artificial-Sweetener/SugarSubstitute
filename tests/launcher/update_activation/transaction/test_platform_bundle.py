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

"""Verify platform-native launcher bundle preservation."""

from __future__ import annotations

from pathlib import Path
import stat
import zipfile

import pytest

from sugarsubstitute_shared.launcher_update.models import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    LINUX_X64_BUNDLE,
    MACOS_ARM64_BUNDLE,
)
from sugarsubstitute_shared.launcher_update.transaction import LauncherUpdateTransaction

from .support import _asset


@pytest.mark.platforms("linux", "macos")
def test_stager_restores_safe_relative_macos_symlinks(tmp_path: Path) -> None:
    """Staging should reconstruct a PyInstaller-style macOS framework link."""

    archive = tmp_path / "macos-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            "launcher",
        )
        bundle.writestr(
            "SugarSubstitute.app/Contents/Frameworks/"
            "Python.framework/Versions/3.13/Python",
            "runtime",
        )
        link = zipfile.ZipInfo(
            "SugarSubstitute.app/Contents/Frameworks/Python.framework/Versions/Current"
        )
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "3.13")

    request_path = LauncherBundleStager().stage(
        install_root=tmp_path / "SugarSubstitute",
        version="0.11.0",
        target=MACOS_ARM64_BUNDLE,
        asset=_asset(archive),
    )
    request = LauncherUpdateRequest.load(request_path)
    restored_link = (
        request.staged_bundle_dir
        / "SugarSubstitute.app"
        / "Contents"
        / "Frameworks"
        / "Python.framework"
        / "Versions"
        / "Current"
    )

    assert restored_link.is_symlink()
    assert restored_link.readlink() == Path("3.13")


@pytest.mark.platforms("linux", "macos")
def test_transaction_preserves_macos_symlinks_during_promotion(tmp_path: Path) -> None:
    """Promotion must retain the staged PyInstaller bundle topology."""

    install_root = tmp_path / "SugarSubstitute"
    old_app = install_root / "SugarSubstitute.app" / "Contents"
    (old_app / "MacOS").mkdir(parents=True)
    (old_app / "MacOS" / "SugarSubstitute").write_text(
        "old launcher",
        encoding="utf-8",
    )
    (old_app / "Frameworks").mkdir()
    archive = tmp_path / "macos-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            "new launcher",
        )
        bundle.writestr(
            "SugarSubstitute.app/Contents/Frameworks/"
            "Python.framework/Versions/3.13/Python",
            "runtime",
        )
        link = zipfile.ZipInfo(
            "SugarSubstitute.app/Contents/Frameworks/Python.framework/Versions/Current"
        )
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "3.13")

    request_path = LauncherBundleStager().stage(
        install_root=install_root,
        version="0.11.0",
        target=MACOS_ARM64_BUNDLE,
        asset=_asset(archive),
    )
    LauncherUpdateTransaction(wait_timeout_seconds=0).apply(request_path=request_path)
    promoted_link = (
        install_root
        / "SugarSubstitute.app"
        / "Contents"
        / "Frameworks"
        / "Python.framework"
        / "Versions"
        / "Current"
    )

    assert promoted_link.is_symlink()
    assert promoted_link.readlink() == Path("3.13")


@pytest.mark.platforms("linux", "macos")
def test_stager_restores_linux_launcher_executable_mode(tmp_path: Path) -> None:
    """Portable extraction must leave the installed Linux launcher runnable."""

    archive = tmp_path / "linux-launcher.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        executable = zipfile.ZipInfo("SugarSubstitute")
        executable.external_attr = 0o100644 << 16
        bundle.writestr(executable, b"launcher")
        bundle.writestr("launcher-bin/runtime.txt", b"support")

    request_path = LauncherBundleStager().stage(
        install_root=tmp_path / "SugarSubstitute",
        version="0.11.0",
        target=LINUX_X64_BUNDLE,
        asset=_asset(archive),
    )
    request = LauncherUpdateRequest.load(request_path)
    installed_mode = (
        request.staged_bundle_dir / "SugarSubstitute"
    ).stat().st_mode & 0o777

    assert installed_mode == 0o755
