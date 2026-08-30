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

"""Verify local and HTTPS release-asset download policy."""

from __future__ import annotations

import ssl
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.downloader import (
    AssetDownloadError,
    AssetDownloader,
)
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from tests.launcher.installation_workflow.first_run.support import sha256, sha256_bytes


def test_asset_downloader_copies_file_url_to_destination(tmp_path: Path) -> None:
    """File release assets are copied through the same downloader interface."""

    source = tmp_path / "source.zip"
    source.write_bytes(b"payload")
    asset = ReleaseAsset(
        filename=source.name,
        url=source.as_uri(),
        sha256=sha256(source),
        size_bytes=source.stat().st_size,
    )
    destination = tmp_path / "downloads" / source.name

    result = AssetDownloader().download(asset=asset, destination_path=destination)

    assert result == destination
    assert destination.read_bytes() == b"payload"
    assert not destination.with_name(f"{destination.name}.partial").exists()


def test_asset_downloader_uses_supplied_verified_tls_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """HTTPS assets should use the launcher's owned system-trust context."""

    payload = b"payload"
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    class Response:
        """Serve deterministic bytes through the urlopen response protocol."""

        def __enter__(self) -> "Response":
            """Enter the fake response context."""

            return self

        def __exit__(self, *_args: object) -> None:
            """Exit the fake response context."""

        def read(self, _size: int = -1) -> bytes:
            """Return payload bytes once, then signal end-of-stream."""

            content, self._remaining = getattr(self, "_remaining", payload), b""
            return content

    def fake_urlopen(
        request: object, *, timeout: float, context: ssl.SSLContext
    ) -> Response:
        """Require the downloader's explicit verified TLS context."""

        assert str(request.full_url) == "https://example.invalid/payload.zip"  # type: ignore[attr-defined]
        assert timeout == 60.0
        assert context is tls_context
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    asset = ReleaseAsset(
        filename="payload.zip",
        url="https://example.invalid/payload.zip",
        sha256=sha256_bytes(payload),
        size_bytes=len(payload),
    )
    destination = tmp_path / "downloads" / asset.filename

    assert (
        AssetDownloader(tls_context=tls_context)
        .download(asset=asset, destination_path=destination)
        .read_bytes()
        == payload
    )


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
            asset=asset, destination_path=tmp_path / "downloads" / asset.filename
        )
