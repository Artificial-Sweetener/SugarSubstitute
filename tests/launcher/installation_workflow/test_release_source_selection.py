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

"""Verify release-source selection for launcher installation workflows."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.installation.release_source_policy import (
    resolve_initial_install_release_source,
)
from launcher.sugarsubstitute_launcher.config import DEFAULT_RELEASE_MANIFEST_URL
from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    VersionBoundReleaseSource,
)


def test_frozen_local_test_installer_prefers_embedded_release_channel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep packaged local-test installs off the GitHub release channel."""

    release_root = tmp_path / "launcher_local_release"
    release_root.mkdir()
    (release_root / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    source = resolve_initial_install_release_source(frozen_setup=True)

    assert source == LocalFolderReleaseSource(release_root.resolve())


def test_frozen_installer_uses_production_release_without_embedded_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind a production frozen installer to its exact release version."""

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_packaged_release_root",
        lambda: None,
    )

    source = resolve_initial_install_release_source(frozen_setup=True)

    assert isinstance(source, VersionBoundReleaseSource)
    assert source.manifest_url.endswith(
        f"/releases/download/v{source.expected_version}/manifest.json"
    )
    assert source.manifest_url != DEFAULT_RELEASE_MANIFEST_URL


def test_frozen_canary_installer_binds_rolling_canary_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify frozen Canary setup builds against the rolling canary feed."""

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_packaged_release_root",
        lambda: None,
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.RELEASE_CHANNEL",
        "canary",
    )

    source = resolve_initial_install_release_source(
        frozen_setup=True,
        release_version="0.21.0-canary.42",
    )

    assert isinstance(source, VersionBoundReleaseSource)
    assert source.expected_channel == "canary"
    assert source.expected_version == "0.21.0-canary.42"
    assert source.manifest_url.endswith(
        "/releases/download/canary-latest/manifest.json"
    )
    assert source.update_manifest_url.endswith(
        "/releases/download/canary-latest/manifest.json"
    )


def test_source_installer_uses_worktree_release_channel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve source-run installation from its worktree-local release channel."""

    release_root = tmp_path / ".local-release-channel"
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_packaged_release_root",
        lambda: None,
    )
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: release_root,
    )

    source = resolve_initial_install_release_source(frozen_setup=False)

    assert source == LocalFolderReleaseSource(release_root)
