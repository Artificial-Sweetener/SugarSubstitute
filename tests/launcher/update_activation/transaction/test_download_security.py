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

"""Verify trusted launcher bundle download behavior."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import ssl

import pytest

from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset


def test_launcher_bundle_download_uses_explicit_system_trust_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher replacement downloads must share the verified TLS policy."""

    content = b"launcher bundle"
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    observed: list[tuple[float, ssl.SSLContext]] = []

    def fake_urlopen(
        _request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Record the HTTPS context and return one in-memory bundle."""

        observed.append((timeout, context))
        return io.BytesIO(content)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    destination = tmp_path / "launcher.zip"

    result = LauncherBundleDownloader(
        timeout_seconds=15.0,
        tls_context=tls_context,
    ).download(
        asset=LauncherBundleAsset(
            filename="launcher.zip",
            url="https://github.example/launcher.zip",
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        ),
        destination=destination,
    )

    assert result == destination
    assert destination.read_bytes() == content
    assert observed == [(15.0, tls_context)]
