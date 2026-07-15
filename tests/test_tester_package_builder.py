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

"""Tests for offline tester package generation."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tools.build_tester_package import (
    SETUP_EXE_NAME,
    TESTER_PACKAGE_PREFIX,
    build_tester_package,
)


def test_tester_package_places_setup_exe_next_to_release_channel(
    tmp_path: Path,
) -> None:
    """The extracted package should expose the setup exe under `dist`."""

    release_channel = _write_release_channel(tmp_path / ".local-release-channel")
    setup_exe = _write_file(tmp_path / "dist" / SETUP_EXE_NAME, "setup")

    result = build_tester_package(
        release_channel_dir=release_channel,
        setup_exe_path=setup_exe,
        output_dir=tmp_path / "out",
    )

    package_root = f"{TESTER_PACKAGE_PREFIX}0.4.0"
    assert result.version == "0.4.0"
    assert result.setup_exe_path == result.package_dir / "dist" / SETUP_EXE_NAME
    assert result.release_channel_dir == (
        result.package_dir / "dist" / ".local-release-channel"
    )
    assert result.setup_exe_path.read_text(encoding="utf-8") == "setup"
    assert (result.release_channel_dir / "manifest.json").is_file()
    assert (result.release_channel_dir / "SugarSubstitute-app-v0.4.0.zip").is_file()
    assert (
        result.release_channel_dir
        / "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    ).is_file()
    assert (
        result.release_channel_dir / "SugarSubstitute-Installer-Windows-x64.exe"
    ).is_file()

    with zipfile.ZipFile(result.zip_path) as archive:
        archive_names = set(archive.namelist())

    assert f"{package_root}/dist/{SETUP_EXE_NAME}" in archive_names
    assert f"{package_root}/dist/.local-release-channel/manifest.json" in archive_names
    assert (
        f"{package_root}/dist/.local-release-channel/SugarSubstitute-app-v0.4.0.zip"
    ) in archive_names
    assert (
        f"{package_root}/dist/.local-release-channel/"
        "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    ) in archive_names
    assert (
        f"{package_root}/dist/.local-release-channel/"
        "SugarSubstitute-Installer-Windows-x64.exe"
    ) in archive_names


def test_tester_package_requires_launcher_bundle_in_manifest(tmp_path: Path) -> None:
    """Offline tester setup needs the installed-launcher bundle asset."""

    release_channel = _write_release_channel(
        tmp_path / ".local-release-channel",
        include_launcher=False,
    )
    setup_exe = _write_file(tmp_path / "dist" / SETUP_EXE_NAME, "setup")

    with pytest.raises(ValueError, match="launcher bundle"):
        build_tester_package(
            release_channel_dir=release_channel,
            setup_exe_path=setup_exe,
            output_dir=tmp_path / "out",
        )


def test_tester_package_requires_setup_exe_name(tmp_path: Path) -> None:
    """The user-facing executable name should stay stable in tester zips."""

    release_channel = _write_release_channel(tmp_path / ".local-release-channel")
    setup_exe = _write_file(tmp_path / "dist" / "wrong.exe", "setup")

    with pytest.raises(ValueError, match=SETUP_EXE_NAME):
        build_tester_package(
            release_channel_dir=release_channel,
            setup_exe_path=setup_exe,
            output_dir=tmp_path / "out",
        )


def _write_release_channel(root: Path, *, include_launcher: bool = True) -> Path:
    """Write a minimal local release channel fixture."""

    app_zip = _write_file(root / "SugarSubstitute-app-v0.4.0.zip", "app")
    launcher_zip = _write_file(
        root / "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip",
        "launcher",
    )
    installer_exe = _write_file(root / SETUP_EXE_NAME, "setup")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "channel": "stable",
        "version": "0.4.0",
        "minimum_launcher_version": "0.1.0",
        "app": {
            "filename": app_zip.name,
            "url": app_zip.as_uri(),
            "sha256": _sha256(app_zip),
            "size_bytes": app_zip.stat().st_size,
        },
        "launchers": {},
        "installers": {
            "windows_x64": {
                "filename": installer_exe.name,
                "url": installer_exe.as_uri(),
                "sha256": _sha256(installer_exe),
                "size_bytes": installer_exe.stat().st_size,
            }
        },
    }
    if include_launcher:
        manifest["launchers"] = {
            "windows_x64": {
                "filename": launcher_zip.name,
                "url": launcher_zip.as_uri(),
                "sha256": _sha256(launcher_zip),
                "size_bytes": launcher_zip.stat().st_size,
            }
        }
    _write_file(root / "manifest.json", json.dumps(manifest))
    _write_file(root / "checksums.txt", "checksums")
    return root


def _write_file(path: Path, content: str) -> Path:
    """Write one text fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    """Return one file SHA256 digest."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
