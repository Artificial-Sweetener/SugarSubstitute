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

"""Tests for immutable installer-to-release binding."""

from __future__ import annotations

import pytest

from launcher.sugarsubstitute_launcher.config import DEFAULT_RELEASE_MANIFEST_URL
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    VersionBoundReleaseSource,
    production_installer_release_source,
    release_source_config_for,
)


def test_production_installer_source_uses_exact_tagged_manifest() -> None:
    """A released installer must not resolve its initial app through latest."""

    source = production_installer_release_source("0.20.0")

    assert source.manifest_url == (
        "https://github.com/Artificial-Sweetener/SugarSubstitute/"
        "releases/download/v0.20.0/manifest.json"
    )
    assert source.expected_version == "0.20.0"
    assert "releases/latest" not in source.manifest_url


def test_bound_installer_persists_stable_update_feed() -> None:
    """Initial version binding must not prevent later application updates."""

    config = release_source_config_for(production_installer_release_source("0.20.0"))

    assert config is not None
    assert config.manifest_url == DEFAULT_RELEASE_MANIFEST_URL


def test_bound_installer_rejects_manifest_version_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tagged endpoint serving another version must fail closed."""

    monkeypatch.setattr(
        GitHubReleaseSource,
        "load_manifest",
        lambda _self: _manifest("0.21.0"),
    )
    source = VersionBoundReleaseSource(
        manifest_url="https://example.invalid/v0.20.0/manifest.json",
        expected_version="0.20.0",
    )

    with pytest.raises(ValueError, match="expected 0.20.0, got 0.21.0"):
        source.load_manifest()


def _manifest(version: str) -> ReleaseManifest:
    """Return one valid manifest with the requested version."""

    return ReleaseManifest(
        schema_version=2,
        channel="stable",
        version=version,
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=f"SugarSubstitute-app-v{version}.zip",
            url=f"https://example.invalid/SugarSubstitute-app-v{version}.zip",
            sha256="0" * 64,
            size_bytes=1,
        ),
        launchers={},
        installers={},
    )
