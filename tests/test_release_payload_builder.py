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

"""Tests for local release-channel payload generation."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools.release_assets import (
    NativeInstallerInput,
    PlatformReleaseInput,
    RUNTIME_REQUIRED_ROOTS,
    build_local_release_channel,
    build_installed_launcher_zip,
    inspect_payload_zip,
    sha256_file,
)
from launcher.sugarsubstitute_launcher.platforms import (
    LINUX_X64,
    MACOS_ARM64,
    WINDOWS_X64,
    InstallerFormat,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_release_builder_rejects_launcher_unsafe_version(tmp_path: Path) -> None:
    """Release assembly must reject versions launcher staging cannot consume."""

    repo_root = _write_fixture_repo(tmp_path)

    with pytest.raises(ValueError, match="Unsafe launcher version"):
        build_local_release_channel(
            repo_root=repo_root,
            output_dir=repo_root / ".local-release-channel",
            version="0.10.0-local.20260716",
        )


def test_release_payload_cli_runs_by_file_path(tmp_path: Path) -> None:
    """Release automation can invoke the CLI script outside the repository root."""

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(REPO_ROOT / "tools" / "build_release_payload.py"),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "package-launcher" in result.stdout


def test_release_payload_contains_required_runtime_roots(tmp_path: Path) -> None:
    """The app zip contains exactly the runtime roots the launcher installs."""

    repo_root = _write_fixture_repo(tmp_path)

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
    )

    archive_names = inspect_payload_zip(result.app_zip_path)
    assert "main.py" in archive_names
    assert "requirements.txt" in archive_names
    assert "sitecustomize.py" in archive_names
    assert "substitute/__init__.py" in archive_names
    assert "substitute/app/__init__.py" in archive_names
    assert "substitute/app/bootstrap/startup.py" in archive_names
    assert "sugarsubstitute_shared/__init__.py" in archive_names
    assert "third_party/manifest.toml" in archive_names
    assert set(RUNTIME_REQUIRED_ROOTS).issuperset(
        {archive_name.split("/", maxsplit=1)[0] for archive_name in archive_names}
    )


def test_release_payload_excludes_non_runtime_artifacts(tmp_path: Path) -> None:
    """The app zip excludes repo state, caches, test files, and user data."""

    repo_root = _write_fixture_repo(tmp_path)
    _write_file(repo_root / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write_file(repo_root / ".venv" / "pyvenv.cfg", "home = C:\\Python312\n")
    _write_file(repo_root / "tests" / "test_example.py", "def test_example(): pass\n")
    _write_file(repo_root / "user" / "settings.json", "{}\n")
    _write_file(repo_root / "appdata" / "state.json", "{}\n")
    _write_file(repo_root / "substitute" / "__pycache__" / "module.pyc", "cache")
    _write_file(repo_root / "substitute" / "debug.log", "noise")
    _write_file(repo_root / "third_party" / ".pytest_cache" / "README.md", "cache")

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
    )

    archive_names = inspect_payload_zip(result.app_zip_path)
    assert ".git/HEAD" not in archive_names
    assert ".venv/pyvenv.cfg" not in archive_names
    assert "tests/test_example.py" not in archive_names
    assert "user/settings.json" not in archive_names
    assert "appdata/state.json" not in archive_names
    assert "substitute/__pycache__/module.pyc" not in archive_names
    assert "substitute/debug.log" not in archive_names
    assert "third_party/.pytest_cache/README.md" not in archive_names


def test_local_release_channel_writes_manifest_and_checksums(tmp_path: Path) -> None:
    """The local channel emits production-shaped manifest and checksum files."""

    repo_root = _write_fixture_repo(tmp_path)
    output_dir = repo_root / ".local-release-channel"

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=output_dir,
        version="0.4.0",
        channel="stable",
        minimum_launcher_version="0.1.0",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["channel"] == "stable"
    assert manifest["version"] == "0.4.0"
    assert manifest["minimum_launcher_version"] == "0.1.0"
    assert manifest["app"]["filename"] == "SugarSubstitute-app-v0.4.0.zip"
    assert manifest["app"]["url"] == result.app_zip_path.as_uri()
    assert manifest["app"]["sha256"] == sha256_file(result.app_zip_path)
    assert manifest["app"]["size_bytes"] == result.app_zip_path.stat().st_size
    assert manifest["launchers"] == {}
    assert manifest["installers"] == {}

    checksums = result.checksums_path.read_text(encoding="utf-8")
    assert checksums == (
        f"{sha256_file(result.app_zip_path)}  SugarSubstitute-app-v0.4.0.zip\n"
    )


def test_local_release_channel_writes_optional_launcher_bundle_asset(
    tmp_path: Path,
) -> None:
    """The local channel includes installed-launcher bundle metadata when built."""

    repo_root = _write_fixture_repo(tmp_path)
    launcher_bundle_dir = _write_fixture_launcher_bundle(tmp_path / "launcher-dist")
    setup_path = _write_fixture_setup(tmp_path / "setup.exe", "setup")
    macos_bundle_dir = _write_fixture_macos_launcher_bundle(tmp_path / "macos-dist")
    macos_installer = _write_fixture_setup(tmp_path / "macos.dmg", "dmg")

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
        platform_inputs=(
            PlatformReleaseInput(
                target=WINDOWS_X64,
                launcher_source=launcher_bundle_dir,
                installers=(
                    NativeInstallerInput(InstallerFormat.WINDOWS_EXE, setup_path),
                ),
            ),
            PlatformReleaseInput(
                target=MACOS_ARM64,
                launcher_source=macos_bundle_dir,
                installers=(
                    NativeInstallerInput(InstallerFormat.DMG, macos_installer),
                ),
            ),
        ),
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    launcher = manifest["launchers"]["windows_x64"]
    installer = manifest["installers"]["windows_x64_exe"]
    launcher_zip = repo_root / ".local-release-channel" / launcher["filename"]
    installer_exe = repo_root / ".local-release-channel" / installer["filename"]
    macos_launcher = manifest["launchers"]["macos_arm64"]
    macos_installer_asset = manifest["installers"]["macos_arm64_dmg"]
    assert launcher["filename"] == (
        "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    )
    assert launcher["url"] == launcher_zip.as_uri()
    assert launcher["sha256"] == sha256_file(launcher_zip)
    assert installer["filename"] == "SugarSubstitute-Installer-Windows-x64.exe"
    assert installer["url"] == installer_exe.as_uri()
    assert installer["sha256"] == sha256_file(installer_exe)
    assert "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip" in (
        result.checksums_path.read_text(encoding="utf-8")
    )
    assert "SugarSubstitute-Installer-Windows-x64.exe" in (
        result.checksums_path.read_text(encoding="utf-8")
    )
    with zipfile.ZipFile(launcher_zip) as archive:
        assert "SugarSubstitute.exe" in archive.namelist()
        assert "launcher-bin/python312.dll" in archive.namelist()
    assert result.installer_assets["windows_x64_exe"].filename == installer_exe.name
    assert installer_exe.read_text(encoding="utf-8") == "setup"
    assert macos_launcher["filename"] == (
        "SugarSubstitute-installer-payload-macos-arm64-v0.4.0.zip"
    )
    assert macos_installer_asset["filename"] == (
        "SugarSubstitute-Installer-macOS-Apple-Silicon.dmg"
    )


def test_manifest_can_use_release_asset_base_url(tmp_path: Path) -> None:
    """The payload builder can emit production HTTPS asset URLs."""

    repo_root = _write_fixture_repo(tmp_path)
    launcher_bundle_dir = _write_fixture_launcher_bundle(tmp_path / "launcher-dist")

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
        platform_inputs=(
            PlatformReleaseInput(
                target=WINDOWS_X64,
                launcher_source=launcher_bundle_dir,
                installers=(
                    NativeInstallerInput(
                        InstallerFormat.WINDOWS_EXE,
                        _write_fixture_setup(tmp_path / "setup.exe", "setup"),
                    ),
                ),
            ),
        ),
        asset_base_url="https://github.com/acme/SugarSubstitute/releases/download/v0.4.0",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["app"]["url"] == (
        "https://github.com/acme/SugarSubstitute/releases/download/v0.4.0/"
        "SugarSubstitute-app-v0.4.0.zip"
    )
    assert manifest["launchers"]["windows_x64"]["url"] == (
        "https://github.com/acme/SugarSubstitute/releases/download/v0.4.0/"
        "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    )


def test_installed_launcher_zip_requires_onedir_support_dir(tmp_path: Path) -> None:
    """The installed launcher artifact rejects onefile-style single exe folders."""

    launcher_bundle_dir = tmp_path / "launcher-dist"
    _write_file(launcher_bundle_dir / "SugarSubstitute.exe", "launcher")

    try:
        build_installed_launcher_zip(
            launcher_bundle_dir=launcher_bundle_dir,
            output_path=tmp_path / "launcher.zip",
            target=WINDOWS_X64,
        )
    except FileNotFoundError as error:
        assert "launcher-bin" in str(error)
    else:
        raise AssertionError("Expected launcher bundle validation to fail.")


def test_linux_launcher_zip_restores_executable_mode(tmp_path: Path) -> None:
    """Artifact handoff must not strip the permanent Linux launcher execute bit."""

    launcher_bundle = _write_fixture_linux_launcher_bundle(tmp_path / "linux-dist")
    launcher_path = launcher_bundle / "SugarSubstitute"
    launcher_path.chmod(0o644)
    archive_path = build_installed_launcher_zip(
        launcher_bundle_dir=launcher_bundle,
        output_path=tmp_path / "launcher.zip",
        target=LINUX_X64,
    )

    with zipfile.ZipFile(archive_path) as archive:
        archived_mode = (archive.getinfo("SugarSubstitute").external_attr >> 16) & 0o777

    assert archived_mode == 0o755


def test_linux_release_requires_and_emits_appimage_and_debian_installers(
    tmp_path: Path,
) -> None:
    """Linux release assembly should publish both promised native formats."""

    repo_root = _write_fixture_repo(tmp_path)
    launcher_bundle = _write_fixture_linux_launcher_bundle(tmp_path / "linux-dist")
    appimage = _write_fixture_setup(tmp_path / "app.AppImage", "appimage")
    debian = _write_fixture_setup(tmp_path / "app.deb", "debian")

    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
        platform_inputs=(
            PlatformReleaseInput(
                target=LINUX_X64,
                launcher_source=launcher_bundle,
                installers=(
                    NativeInstallerInput(InstallerFormat.APPIMAGE, appimage),
                    NativeInstallerInput(InstallerFormat.DEB, debian),
                ),
            ),
        ),
    )

    assert set(result.installer_assets) == {
        "linux_x64_appimage",
        "linux_x64_deb",
    }
    assert result.installer_assets["linux_x64_appimage"].filename.endswith(".AppImage")
    assert result.installer_assets["linux_x64_deb"].filename.endswith(".deb")


def test_payload_zip_is_deterministic(tmp_path: Path) -> None:
    """Repeated builds from the same tree produce the same app payload hash."""

    repo_root = _write_fixture_repo(tmp_path)
    first = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
    )
    first_hash = sha256_file(first.app_zip_path)

    second = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
    )

    assert sha256_file(second.app_zip_path) == first_hash


def test_payload_zip_extracts_clean_runtime_app(tmp_path: Path) -> None:
    """The produced zip extracts to a clean installable app directory."""

    repo_root = _write_fixture_repo(tmp_path)
    result = build_local_release_channel(
        repo_root=repo_root,
        output_dir=repo_root / ".local-release-channel",
        version="0.4.0",
    )
    extract_root = tmp_path / "extract"

    with zipfile.ZipFile(result.app_zip_path) as archive:
        archive.extractall(extract_root)

    assert (extract_root / "main.py").is_file()
    assert (extract_root / "requirements.txt").is_file()
    assert (extract_root / "sitecustomize.py").is_file()
    assert (extract_root / "substitute").is_dir()
    assert (extract_root / "sugarsubstitute_shared").is_dir()
    assert (extract_root / "third_party").is_dir()
    assert not (extract_root / ".git").exists()
    assert not (extract_root / "tests").exists()


def test_project_requirements_do_not_install_sugar_dsl() -> None:
    """Frontend installer builds must leave Sugar-DSL on Substitute BackEnd."""

    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "sugar-dsl" not in requirements


def test_project_requirements_pin_current_qpane_baseline() -> None:
    """Frontend installer builds should require the supported QPane release."""

    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "qpane[mask,sam]>=2.0.4" in requirements


def _write_fixture_repo(tmp_path: Path) -> Path:
    """Write a minimal source tree that satisfies app payload packaging."""

    repo_root = tmp_path / "repo"
    _write_file(repo_root / "main.py", "print('app')\n")
    _write_file(repo_root / "requirements.txt", "PySide6\n")
    _write_file(repo_root / "sitecustomize.py", "# site customization\n")
    _write_file(repo_root / "substitute" / "__init__.py", '"""App package."""\n')
    _write_file(
        repo_root / "sugarsubstitute_shared" / "__init__.py",
        '"""Shared infrastructure package."""\n',
    )
    _write_file(repo_root / "substitute" / "app" / "__init__.py", '"""Bootstrap."""\n')
    _write_file(
        repo_root / "substitute" / "app" / "bootstrap" / "startup.py",
        "VALUE = 1\n",
    )
    _write_file(repo_root / "third_party" / "manifest.toml", "[[component]]\n")
    return repo_root


def _write_fixture_launcher_bundle(root: Path) -> Path:
    """Write a minimal PyInstaller onedir launcher bundle fixture."""

    _write_file(root / "SugarSubstitute.exe", "launcher")
    _write_file(root / "launcher-bin" / "python312.dll", "dll")
    return root


def _write_fixture_setup(path: Path, content: str) -> Path:
    """Write one minimal public installer fixture."""

    _write_file(path, content)
    return path


def _write_fixture_macos_launcher_bundle(root: Path) -> Path:
    """Write a minimal PyInstaller macOS app bundle fixture."""

    _write_file(
        root / "SugarSubstitute.app" / "Contents" / "MacOS" / "SugarSubstitute",
        "launcher",
    )
    _write_file(
        root / "SugarSubstitute.app" / "Contents" / "Frameworks" / "Python",
        "framework",
    )
    return root


def _write_fixture_linux_launcher_bundle(root: Path) -> Path:
    """Write a minimal PyInstaller Linux onedir launcher bundle fixture."""

    _write_file(root / "SugarSubstitute", "launcher")
    _write_file(root / "launcher-bin" / "libpython3.13.so", "runtime")
    return root


def _write_file(path: Path, content: str) -> None:
    """Write one fixture file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
