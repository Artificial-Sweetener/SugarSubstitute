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

"""Verify local and GitHub release-manifest source behavior."""

from __future__ import annotations

import json
import ssl
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    LocalFolderReleaseSource,
)
from tests.launcher.installation_workflow.first_run.support import (
    sha256,
    write_file,
    write_manifest,
    write_valid_payload_zip,
)


def test_local_folder_release_source_loads_manifest(tmp_path: Path) -> None:
    """Local release sources load the same manifest schema used in production."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    write_manifest(release_root / "manifest.json", app_zip=app_zip)

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
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    stale_zip = tmp_path / "old-machine" / ".local-release-channel" / app_zip.name
    payload = {
        "schema_version": 1,
        "channel": "stable",
        "version": "0.4.0",
        "minimum_launcher_version": "0.1.0",
        "app": {
            "filename": app_zip.name,
            "url": stale_zip.as_uri(),
            "sha256": sha256(app_zip),
            "size_bytes": app_zip.stat().st_size,
        },
        "launchers": {},
        "installers": {},
    }
    write_file(release_root / "manifest.json", json.dumps(payload))

    manifest = LocalFolderReleaseSource(release_root).load_manifest()

    assert manifest.app.url == app_zip.as_uri()


def test_github_release_source_loads_manifest_from_https_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GitHub release sources parse the same manifest schema as local sources."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    manifest_path = release_root / "manifest.json"
    write_manifest(manifest_path, app_zip=app_zip)

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

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def fake_urlopen(
        request: object, *, timeout: float, context: ssl.SSLContext
    ) -> Response:
        """Validate the requested URL and return a fake response."""

        assert "manifest.json" in str(request.full_url)  # type: ignore[attr-defined]
        assert timeout == 30.0
        assert context is tls_context
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    manifest = GitHubReleaseSource(
        "https://github.com/acme/SugarSubstitute/releases/download/v0.4.0/manifest.json",
        tls_context=tls_context,
    ).load_manifest()

    assert manifest.version == "0.4.0"
    assert manifest.app.filename == app_zip.name


def test_github_release_source_rejects_http_manifest_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote update manifests must be fetched over HTTPS."""

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("HTTP manifest URL should be rejected before download.")
        ),
    )

    with pytest.raises(ValueError, match="must use HTTPS"):
        GitHubReleaseSource(
            "http://github.com/acme/SugarSubstitute/releases/download/v0.4.0/manifest.json"
        ).load_manifest()
