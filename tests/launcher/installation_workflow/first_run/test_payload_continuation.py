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

"""Verify first-run application payload installation and update handoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig, ReleaseSourceConfig
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import build_app_launch_command
from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    LocalFolderReleaseSource,
)
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from tests.launcher.installation_workflow.first_run.support import (
    write_manifest,
    write_valid_payload_zip,
)


def test_continue_install_installs_app_payload_from_local_channel(
    tmp_path: Path,
) -> None:
    """Continuing install downloads, verifies, extracts, and promotes app payload."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    write_manifest(release_root / "manifest.json", app_zip=app_zip)
    layout = InstallLayout.from_root(tmp_path / "install")

    result = FirstRunInstaller().continue_install(
        layout=layout, release_source=LocalFolderReleaseSource(release_root)
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
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    write_manifest(release_root / "manifest.json", app_zip=app_zip)
    release_source = LocalFolderReleaseSource(release_root)
    layout = InstallLayout.from_root(tmp_path / "install")
    FirstRunInstaller().continue_install(layout=layout, release_source=release_source)

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
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest_path = release_root / "manifest.json"
    write_manifest(manifest_path, app_zip=app_zip)
    manifest_url = (
        "https://github.com/acme/SugarSubstitute/releases/latest/download/manifest.json"
    )
    layout = InstallLayout.from_root(tmp_path / "install")

    class Response:
        """Return manifest bytes through the urlopen context-manager protocol."""

        def __enter__(self) -> "Response":
            """Enter the fake response context."""

            return self

        def __exit__(self, *_args: object) -> None:
            """Exit the fake response context."""

        def read(self) -> bytes:
            """Return manifest JSON bytes."""

            return manifest_path.read_bytes()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda _request, *, timeout, context: Response()
    )
    FirstRunInstaller().continue_install(
        layout=layout, release_source=GitHubReleaseSource(manifest_url)
    )

    assert LauncherConfig.load(
        layout.config_path
    ).release_source == ReleaseSourceConfig(
        kind="github_release_manifest", manifest_url=manifest_url
    )


def test_continue_install_persists_manifest_channel(tmp_path: Path) -> None:
    """First-run installation must bind later updates to the installed channel."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest_path = release_root / "manifest.json"
    write_manifest(manifest_path, app_zip=app_zip)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["channel"] = "canary"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    layout = InstallLayout.from_root(tmp_path / "install")

    FirstRunInstaller().continue_install(
        layout=layout, release_source=LocalFolderReleaseSource(release_root)
    )

    assert LauncherConfig.load(layout.config_path).channel == "canary"
    assert LauncherUpdateState.load(layout.state_path).last_manifest_channel == "canary"
