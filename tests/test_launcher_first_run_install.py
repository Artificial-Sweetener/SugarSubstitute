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

"""Tests for first-run launcher install services."""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Callable, Sequence
import hashlib
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.downloader import (
    AssetDownloadError,
    AssetDownloader,
)
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.config import LauncherConfig, ReleaseSourceConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.payload import (
    AppPayloadInstaller,
    PayloadInstallError,
    safe_extract_zip,
)
from launcher.sugarsubstitute_launcher import process
from launcher.sugarsubstitute_launcher.process import (
    ProcessStartupError,
    build_app_launch_command,
    build_continue_install_command,
    start_detached,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    LocalFolderReleaseSource,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)


def test_local_folder_release_source_loads_manifest(tmp_path: Path) -> None:
    """Local release sources load the same manifest schema used in production."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    _write_manifest(release_root / "manifest.json", app_zip=app_zip)

    manifest = LocalFolderReleaseSource(release_root).load_manifest()

    assert manifest.version == "0.4.0"
    assert manifest.app.filename == app_zip.name
    assert manifest.app.url == app_zip.as_uri()
    assert manifest.launcher_for(WINDOWS_X64) is None
    assert manifest.installer_for(WINDOWS_X64) is None


def test_local_folder_release_source_rebases_assets_to_manifest_folder(
    tmp_path: Path,
) -> None:
    """Portable release folders should keep working after the tree is moved."""

    release_root = tmp_path / "SugarSubstitute" / "dist" / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    stale_root = tmp_path / "old-machine" / ".local-release-channel"
    stale_zip = stale_root / app_zip.name
    payload = {
        "schema_version": 1,
        "channel": "stable",
        "version": "0.4.0",
        "minimum_launcher_version": "0.1.0",
        "app": {
            "filename": app_zip.name,
            "url": stale_zip.as_uri(),
            "sha256": _sha256(app_zip),
            "size_bytes": app_zip.stat().st_size,
        },
        "launchers": {},
        "installers": {},
    }
    _write_file(release_root / "manifest.json", json.dumps(payload))

    manifest = LocalFolderReleaseSource(release_root).load_manifest()

    assert manifest.app.url == app_zip.as_uri()


def test_github_release_source_loads_manifest_from_https_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GitHub release sources parse the same manifest schema as local sources."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest_path = release_root / "manifest.json"
    _write_manifest(manifest_path, app_zip=app_zip)

    class _Response:
        """Return manifest bytes through the urlopen context-manager protocol."""

        def __enter__(self) -> "_Response":
            """Enter the fake response context."""

            return self

        def __exit__(self, *_args: object) -> None:
            """Exit the fake response context."""

        def read(self) -> bytes:
            """Return manifest JSON bytes."""

            return manifest_path.read_bytes()

    def _fake_urlopen(request: object, *, timeout: float) -> _Response:
        """Validate the requested URL and return a fake response."""

        assert "manifest.json" in str(request.full_url)  # type: ignore[attr-defined]
        assert timeout == 30.0
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    manifest = GitHubReleaseSource(
        "https://github.com/acme/SugarSubstitute/releases/download/v0.4.0/manifest.json"
    ).load_manifest()

    assert manifest.version == "0.4.0"
    assert manifest.app.filename == app_zip.name


def test_github_release_source_rejects_http_manifest_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote update manifests must be fetched over HTTPS."""

    def _unexpected_urlopen(*_args: object, **_kwargs: object) -> object:
        """Fail if an insecure URL reaches the network layer."""

        raise AssertionError("HTTP manifest URL should be rejected before download.")

    monkeypatch.setattr("urllib.request.urlopen", _unexpected_urlopen)

    with pytest.raises(ValueError, match="must use HTTPS"):
        GitHubReleaseSource(
            "http://github.com/acme/SugarSubstitute/releases/download/v0.4.0/manifest.json"
        ).load_manifest()


def test_first_run_installs_launcher_bundle_and_builds_continue_command(
    tmp_path: Path,
) -> None:
    """The permanent onedir launcher bundle is installed into the chosen root."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    launcher_zip = _write_valid_launcher_bundle_zip(
        release_root / "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    )
    _write_manifest(
        release_root / "manifest.json",
        app_zip=app_zip,
        launcher_zip=launcher_zip,
    )
    started_commands: list[list[str]] = []

    result = FirstRunInstaller(
        process_starter=_record_command(started_commands)
    ).install_downloaded_launcher(
        install_root=tmp_path / "Programs" / "SugarSubstitute",
        release_source=LocalFolderReleaseSource(release_root),
    )

    assert result.layout.executable_path.read_bytes() == b"launcher"
    assert (
        result.layout.root / "launcher-bin" / "python312.dll"
    ).read_bytes() == b"dll"
    assert result.continue_command == build_continue_install_command(
        layout=result.layout
    )
    assert started_commands == [result.continue_command]


def test_continue_install_command_carries_handoff_geometry(tmp_path: Path) -> None:
    """Continuation command should preserve the setup window frame."""

    layout = InstallLayout.from_root(tmp_path / "Programs" / "SugarSubstitute")

    command = build_continue_install_command(
        layout=layout,
        handoff_geometry="10,20,1260,800",
    )

    assert command == [
        str(layout.executable_path),
        "--continue-install",
        f"--install-root={layout.root}",
        "--handoff-geometry=10,20,1260,800",
    ]


def test_continue_install_installs_app_payload_from_local_channel(
    tmp_path: Path,
) -> None:
    """Continuing install downloads, verifies, extracts, and promotes app payload."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    _write_manifest(release_root / "manifest.json", app_zip=app_zip)
    layout = InstallLayout.from_root(tmp_path / "install")

    result = FirstRunInstaller().continue_install(
        layout=layout,
        release_source=LocalFolderReleaseSource(release_root),
    )

    assert result.app_version == "0.4.0"
    assert (layout.app_dir / "main.py").is_file()
    assert (layout.app_dir / "requirements.txt").is_file()
    assert (layout.app_dir / "sitecustomize.py").is_file()
    assert (layout.app_dir / "substitute").is_dir()
    assert (layout.app_dir / "third_party").is_dir()
    assert result.app_command == build_app_launch_command(layout=layout)
    assert layout.config_path.is_file()
    assert LauncherConfig.load(layout.config_path).release_source is None
    update_state = LauncherUpdateState.load(layout.state_path)
    assert update_state.installed_app_version == "0.4.0"
    assert update_state.last_manifest_channel == "stable"
    assert update_state.last_update_check_utc is None
    assert update_state.last_successful_update_utc is None
    assert not (layout.app_dir / ".git").exists()


def test_first_normal_launch_does_not_reinstall_first_run_payload(
    tmp_path: Path,
) -> None:
    """The first launcher restart should recognize the payload just installed."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    _write_manifest(release_root / "manifest.json", app_zip=app_zip)
    release_source = LocalFolderReleaseSource(release_root)
    layout = InstallLayout.from_root(tmp_path / "install")
    FirstRunInstaller().continue_install(
        layout=layout,
        release_source=release_source,
    )

    result = LauncherUpdateOrchestrator().run(
        layout=layout,
        config=LauncherConfig.load(layout.config_path),
        release_source=release_source,
        no_update_check=False,
    )

    assert result.checked_manifest is True
    assert result.installed_update is False
    assert result.skipped_reason == "installed_current"
    assert result.failure_reason is None


def test_continue_install_persists_github_release_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Production first install should store the GitHub source for later updates."""

    release_root = tmp_path / ".release"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest_path = release_root / "manifest.json"
    _write_manifest(manifest_path, app_zip=app_zip)
    manifest_url = (
        "https://github.com/acme/SugarSubstitute/releases/latest/download/manifest.json"
    )
    layout = InstallLayout.from_root(tmp_path / "install")

    class _Response:
        """Return manifest bytes through the urlopen context-manager protocol."""

        def __enter__(self) -> "_Response":
            """Enter the fake response context."""

            return self

        def __exit__(self, *_args: object) -> None:
            """Exit the fake response context."""

        def read(self) -> bytes:
            """Return manifest JSON bytes."""

            return manifest_path.read_bytes()

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda _request, *, timeout: _Response(),
    )

    FirstRunInstaller().continue_install(
        layout=layout,
        release_source=GitHubReleaseSource(manifest_url),
    )

    assert LauncherConfig.load(layout.config_path).release_source == (
        ReleaseSourceConfig(
            kind="github_release_manifest",
            manifest_url=manifest_url,
        )
    )


def test_app_launch_command_uses_hidden_console_python(tmp_path: Path) -> None:
    """The app handoff uses python.exe so startup failures can be logged."""

    layout = InstallLayout.from_root(tmp_path / "install")

    assert build_app_launch_command(layout=layout) == [
        str(layout.runtime_python),
        str(layout.app_entrypoint),
        f"--install-root={layout.root}",
    ]


def test_start_detached_reports_immediate_app_startup_exit(tmp_path: Path) -> None:
    """Immediate app-process exit is reported with startup log context."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write_file(layout.app_entrypoint, "raise RuntimeError('boom')\n")

    with pytest.raises(ProcessStartupError, match="exited before the setup window"):
        start_detached(
            [
                "python",
                str(layout.app_entrypoint),
                f"--install-root={layout.root}",
            ]
        )

    startup_log = layout.logs_dir / "app-startup.log"
    assert startup_log.is_file()
    assert "RuntimeError: boom" in startup_log.read_text(encoding="utf-8")


def test_child_process_environment_removes_pyinstaller_temp_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Child app launches must not inherit PyInstaller's temp DLL search path."""

    meipass = tmp_path / "_MEI12345"
    bundled_bin = meipass / "PySide6"
    normal_bin = tmp_path / "normal-bin"
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setenv(
        "PATH",
        f"{bundled_bin}{os.pathsep}{normal_bin}",
    )

    environment = process._child_process_environment()  # noqa: SLF001

    path_entries = environment["PATH"].split(os.pathsep)
    assert str(bundled_bin) not in path_entries
    assert str(normal_bin) in path_entries


def test_app_payload_installer_rejects_checksum_mismatch(tmp_path: Path) -> None:
    """Payload installation fails closed when manifest checksum is wrong."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = _write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest = ReleaseManifest(
        schema_version=1,
        channel="stable",
        version="0.4.0",
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=app_zip.name,
            url=app_zip.as_uri(),
            sha256="0" * 64,
            size_bytes=app_zip.stat().st_size,
        ),
        launchers={},
        installers={},
    )

    with pytest.raises(PayloadInstallError, match="SHA256 mismatch"):
        AppPayloadInstaller().install(
            layout=InstallLayout.from_root(tmp_path / "install"),
            manifest=manifest,
        )


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    """Archive extraction rejects entries that escape the destination."""

    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(PayloadInstallError, match="unsafe path"):
        safe_extract_zip(zip_path=zip_path, destination_dir=tmp_path / "extract")


def test_safe_extract_rejects_symlink_entries(tmp_path: Path) -> None:
    """Archive extraction rejects symlink-like zip entries."""

    zip_path = tmp_path / "symlink.zip"
    symlink_info = zipfile.ZipInfo("link")
    symlink_info.external_attr = 0o120777 << 16
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(symlink_info, "target")

    with pytest.raises(PayloadInstallError, match="symlink"):
        safe_extract_zip(zip_path=zip_path, destination_dir=tmp_path / "extract")


def test_asset_downloader_copies_file_url_to_destination(tmp_path: Path) -> None:
    """File release assets are copied through the same downloader interface."""

    source = tmp_path / "source.zip"
    source.write_bytes(b"payload")
    asset = ReleaseAsset(
        filename=source.name,
        url=source.as_uri(),
        sha256=_sha256(source),
        size_bytes=source.stat().st_size,
    )
    destination = tmp_path / "downloads" / source.name

    result = AssetDownloader().download(asset=asset, destination_path=destination)

    assert result == destination
    assert destination.read_bytes() == b"payload"
    assert not destination.with_name(f"{destination.name}.partial").exists()


def test_asset_downloader_rejects_http_remote_asset(tmp_path: Path) -> None:
    """Remote release assets must use HTTPS even though local file assets work."""

    asset = ReleaseAsset(
        filename="payload.zip",
        url="http://example.invalid/payload.zip",
        sha256="0" * 64,
        size_bytes=None,
    )

    with pytest.raises(AssetDownloadError, match="must use HTTPS"):
        AssetDownloader().download(
            asset=asset,
            destination_path=tmp_path / "downloads" / asset.filename,
        )


def _record_command(
    started_commands: list[list[str]],
) -> Callable[[Sequence[str]], None]:
    """Return a process starter that records commands without launching."""

    def starter(command: Sequence[str]) -> None:
        """Record one subprocess command."""

        started_commands.append(list(command))

    return starter


def _write_manifest(
    path: Path, *, app_zip: Path, launcher_zip: Path | None = None
) -> None:
    """Write a minimal local release manifest for tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _manifest_payload(app_zip=app_zip, launcher_zip=launcher_zip)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest_payload(
    *,
    app_zip: Path,
    launcher_zip: Path | None = None,
) -> dict[str, object]:
    """Return a local release manifest payload fixture."""

    payload: dict[str, object] = {
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
        "installers": {},
    }
    if launcher_zip is not None:
        payload["launchers"] = {
            "windows_x64": {
                "filename": launcher_zip.name,
                "url": launcher_zip.as_uri(),
                "sha256": _sha256(launcher_zip),
                "size_bytes": launcher_zip.stat().st_size,
            },
        }
    return payload


def _write_valid_payload_zip(path: Path) -> Path:
    """Write a minimal valid app payload zip."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("main.py", "print('app')\n")
        archive.writestr("requirements.txt", "PySide6\n")
        archive.writestr("sitecustomize.py", "# site customization\n")
        archive.writestr("substitute/__init__.py", '"""App package."""\n')
        archive.writestr("third_party/manifest.toml", "[[component]]\n")
    return path


def _write_valid_launcher_bundle_zip(path: Path) -> Path:
    """Write a minimal valid PyInstaller onedir launcher bundle zip."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SugarSubstitute.exe", b"launcher")
        archive.writestr("launcher-bin/python312.dll", b"dll")
    return path


def _write_file(path: Path, content: str) -> None:
    """Write one text fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    """Return the SHA256 hex digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
