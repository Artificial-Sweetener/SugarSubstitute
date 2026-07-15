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

"""Test Linux package filesystem generation without requiring Linux tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_linux_installers import (
    LinuxInstallerBuildError,
    prepare_linux_package_roots,
)


def test_prepare_linux_package_roots_builds_appimage_and_debian_layouts(
    tmp_path: Path,
) -> None:
    """Both Linux formats should launch the same target-aware setup bundle."""

    setup_bundle = tmp_path / "setup"
    _write(setup_bundle / "SugarSubstitute Setup", "launcher")
    _write(setup_bundle / "launcher-bin" / "python", "runtime")
    _write(setup_bundle / "launcher-bin" / "launcher_assets" / "uv", "uv")
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")
    appdir = tmp_path / "AppDir"
    debian_root = tmp_path / "debian"

    prepare_linux_package_roots(
        setup_bundle=setup_bundle,
        icon_path=icon,
        version="1.2.3",
        appdir=appdir,
        debian_root=debian_root,
    )

    assert (appdir / "AppRun").is_file()
    assert (appdir / "usr" / "lib" / "sugarsubstitute-setup" / "launcher-bin").is_dir()
    assert (debian_root / "usr" / "bin" / "sugarsubstitute-setup").is_file()
    assert (debian_root / "opt" / "sugarsubstitute-setup" / "launcher-bin").is_dir()
    control = (debian_root / "DEBIAN" / "control").read_text(encoding="utf-8")
    assert "Architecture: amd64" in control
    assert "Version: 1.2.3" in control
    assert "libxcb-cursor0" in control
    assert "libxkbcommon-x11-0" in control


def test_prepare_linux_package_roots_rejects_incomplete_bundle(tmp_path: Path) -> None:
    """Linux packaging should fail before publishing an incomplete launcher."""

    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")

    with pytest.raises(LinuxInstallerBuildError, match="incomplete"):
        prepare_linux_package_roots(
            setup_bundle=tmp_path / "missing",
            icon_path=icon,
            version="1.2.3",
            appdir=tmp_path / "AppDir",
            debian_root=tmp_path / "debian",
        )


def _write(path: Path, content: str) -> None:
    """Write one Linux package fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
