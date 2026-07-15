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

"""Test authoritative launcher platform-target behavior."""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest

from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.launcher_bundle import LauncherBundleInstaller
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.platforms import (
    MACOS_ARM64,
    LINUX_X64,
    WINDOWS_X64,
    InstallerFormat,
    UnsupportedLauncherPlatformError,
    detect_launcher_target,
)


def test_detect_launcher_target_supports_windows_x64() -> None:
    """Windows x64 should resolve to the official Windows release target."""

    assert detect_launcher_target(system="Windows", machine="AMD64") is WINDOWS_X64


def test_detect_launcher_target_supports_apple_silicon() -> None:
    """Apple Silicon should resolve to the official macOS release target."""

    assert detect_launcher_target(system="Darwin", machine="arm64") is MACOS_ARM64


def test_detect_launcher_target_supports_linux_x64() -> None:
    """Linux x64 should resolve to Comfy Desktop's supported Linux target."""

    assert detect_launcher_target(system="Linux", machine="x86_64") is LINUX_X64


def test_linux_target_owns_both_published_installer_formats() -> None:
    """Linux release policy should expose both AppImage and Debian artifacts."""

    assert tuple(specification.format for specification in LINUX_X64.installers) == (
        InstallerFormat.APPIMAGE,
        InstallerFormat.DEB,
    )
    assert LINUX_X64.installer(InstallerFormat.APPIMAGE).filename.endswith(".AppImage")
    assert LINUX_X64.installer(InstallerFormat.DEB).filename.endswith(".deb")


@pytest.mark.parametrize(
    ("system", "machine"),
    (("Darwin", "x86_64"), ("Linux", "arm64"), ("Windows", "arm64")),
)
def test_detect_launcher_target_fails_closed_for_unpublished_targets(
    system: str,
    machine: str,
) -> None:
    """Unpublished launcher combinations should fail before selecting assets."""

    with pytest.raises(UnsupportedLauncherPlatformError):
        detect_launcher_target(system=system, machine=machine)


def test_macos_install_layout_uses_bundle_and_posix_runtime_paths(
    tmp_path: Path,
) -> None:
    """macOS installs should use an app bundle and POSIX virtual environment."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute", target=MACOS_ARM64)

    assert layout.executable_path == (
        layout.root / "SugarSubstitute.app" / "Contents" / "MacOS" / "SugarSubstitute"
    )
    assert layout.runtime_python == layout.root / "runtime" / ".venv" / "bin" / "python"
    assert layout.runtime_gui_python == layout.runtime_python
    assert layout.uv_executable == layout.root / "runtime" / "uv" / "uv"


def test_macos_default_install_root_stays_user_writable() -> None:
    """The default Apple Silicon install should not require administrator access."""

    assert default_install_root(target=MACOS_ARM64) == (
        Path.home() / "Applications" / "SugarSubstitute"
    )


def test_linux_install_layout_uses_posix_runtime_paths(tmp_path: Path) -> None:
    """Linux installs should use a native executable and POSIX runtime paths."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute", target=LINUX_X64)

    assert layout.executable_path == layout.root / "SugarSubstitute"
    assert layout.runtime_python == layout.root / "runtime" / ".venv" / "bin" / "python"
    assert layout.uv_executable == layout.root / "runtime" / "uv" / "uv"
    assert default_install_root(target=LINUX_X64) == (
        Path.home() / ".local" / "share" / "SugarSubstitute"
    )


def test_macos_target_resolves_install_root_outside_app_bundle(tmp_path: Path) -> None:
    """Installed launcher discovery should find state beside the macOS app bundle."""

    executable = (
        tmp_path
        / "install"
        / "SugarSubstitute.app"
        / "Contents"
        / "MacOS"
        / "SugarSubstitute"
    )

    assert (
        MACOS_ARM64.install_root_for_executable(executable)
        == (tmp_path / "install").resolve()
    )


def test_macos_launcher_bundle_installs_app_bundle(tmp_path: Path) -> None:
    """The Apple Silicon launcher should promote one complete app bundle."""

    archive_path = tmp_path / "launcher.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "SugarSubstitute.app/Contents/MacOS/SugarSubstitute",
            b"launcher",
        )
        archive.writestr(
            "SugarSubstitute.app/Contents/Frameworks/Python",
            b"framework",
        )
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        size_bytes=archive_path.stat().st_size,
    )
    manifest = ReleaseManifest(
        schema_version=1,
        channel="stable",
        version="1.0.0",
        minimum_launcher_version="1.0.0",
        app=asset,
        launchers={MACOS_ARM64.key: asset},
        installers={},
    )
    layout = InstallLayout.from_root(tmp_path / "install", target=MACOS_ARM64)

    result = LauncherBundleInstaller().install(layout=layout, manifest=manifest)

    assert result.executable_path.read_bytes() == b"launcher"
    assert result.support_dir == (
        layout.root / "SugarSubstitute.app" / "Contents" / "Frameworks"
    )


def test_manifest_selects_assets_by_target_key() -> None:
    """One manifest should resolve independent Windows and macOS artifacts."""

    payload = {
        "schema_version": 1,
        "channel": "stable",
        "version": "1.0.0",
        "minimum_launcher_version": "1.0.0",
        "app": _asset_payload("app.zip"),
        "launchers": {
            WINDOWS_X64.key: _asset_payload("windows.zip"),
            MACOS_ARM64.key: _asset_payload("macos.zip"),
        },
        "installers": {
            WINDOWS_X64.key: _asset_payload("windows.exe"),
            MACOS_ARM64.key: _asset_payload("macos.dmg"),
        },
    }

    manifest = ReleaseManifest.from_json(payload)

    windows_launcher = manifest.launcher_for(WINDOWS_X64)
    macos_launcher = manifest.launcher_for(MACOS_ARM64)
    macos_installer = manifest.installer_for(MACOS_ARM64)
    assert windows_launcher is not None
    assert macos_launcher is not None
    assert macos_installer is not None
    assert windows_launcher.filename == "windows.zip"
    assert macos_launcher.filename == "macos.zip"
    assert macos_installer.filename == "macos.dmg"


def test_manifest_schema_two_selects_each_linux_installer_format() -> None:
    """Manifest schema two should distinguish AppImage and Debian downloads."""

    payload = {
        "schema_version": 2,
        "channel": "stable",
        "version": "1.0.0",
        "minimum_launcher_version": "1.0.0",
        "app": _asset_payload("app.zip"),
        "launchers": {LINUX_X64.key: _asset_payload("linux.zip")},
        "installers": {
            LINUX_X64.installer_key(InstallerFormat.APPIMAGE): _asset_payload(
                "SugarSubstitute.AppImage"
            ),
            LINUX_X64.installer_key(InstallerFormat.DEB): _asset_payload(
                "SugarSubstitute.deb"
            ),
        },
    }

    manifest = ReleaseManifest.from_json(payload)

    appimage = manifest.installer_for(LINUX_X64, InstallerFormat.APPIMAGE)
    debian = manifest.installer_for(LINUX_X64, InstallerFormat.DEB)
    assert appimage is not None
    assert debian is not None
    assert appimage.filename == "SugarSubstitute.AppImage"
    assert debian.filename == "SugarSubstitute.deb"


def test_manifest_schema_one_maps_legacy_installer_to_primary_format() -> None:
    """Existing manifests should remain readable through schema evolution."""

    payload = {
        "schema_version": 1,
        "channel": "stable",
        "version": "1.0.0",
        "minimum_launcher_version": "1.0.0",
        "app": _asset_payload("app.zip"),
        "launchers": {},
        "installers": {WINDOWS_X64.key: _asset_payload("setup.exe")},
    }

    manifest = ReleaseManifest.from_json(payload)

    installer = manifest.installer_for(WINDOWS_X64)
    assert installer is not None
    assert installer.filename == "setup.exe"


def _asset_payload(filename: str) -> dict[str, object]:
    """Return one valid manifest asset fixture."""

    return {
        "filename": filename,
        "url": f"https://example.invalid/{filename}",
        "sha256": "0" * 64,
        "size_bytes": 1,
    }
