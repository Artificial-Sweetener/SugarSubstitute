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

"""Verify byte observations through both release download adapters."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import io
from pathlib import Path
import ssl

import pytest

from launcher.sugarsubstitute_launcher.downloader import (
    AssetDownloader,
    AssetDownloadError,
)
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from sugarsubstitute_shared.asset_transfer import TransferProgress
from sugarsubstitute_shared.launcher_update.downloader import (
    LauncherBundleDownloader,
    LauncherBundleDownloadError,
)
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset


def _download(
    kind: str,
    url: str,
    destination: Path,
    content: bytes,
    observer: Callable[[TransferProgress], None],
) -> Path:
    """Invoke the selected production adapter with the same immutable asset facts."""
    digest = hashlib.sha256(content).hexdigest()
    if kind == "application":
        return AssetDownloader(progress_observer=observer).download(
            asset=ReleaseAsset("asset.zip", url, digest, len(content)),
            destination_path=destination,
        )
    return LauncherBundleDownloader(progress_observer=observer).download(
        asset=LauncherBundleAsset("asset.zip", url, digest, len(content)),
        destination=destination,
    )


@pytest.mark.parametrize("kind", ["application", "launcher"])
@pytest.mark.parametrize("scheme", ["file", "https"])
def test_transfer_reports_bytes_before_destination_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    scheme: str,
) -> None:
    """Expose partial transfer progress without replacing the previous artifact early."""
    content = b"synthetic artifact" * 150_000
    source = tmp_path / "source.zip"
    source.write_bytes(content)
    destination = tmp_path / "download.zip"
    destination.write_bytes(b"previous artifact")
    events: list[TransferProgress] = []

    def observe(progress: TransferProgress) -> None:
        """Check the public destination remains untouched throughout notifications."""
        assert destination.read_bytes() == b"previous artifact"
        events.append(progress)

    def response(
        request: object,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> io.BytesIO:
        """Supply deterministic network bytes without external traffic."""
        assert timeout == 60.0
        assert context.verify_mode == ssl.CERT_REQUIRED
        return io.BytesIO(content)

    monkeypatch.setattr("urllib.request.urlopen", response)
    url = source.as_uri() if scheme == "file" else "https://example.invalid/asset.zip"
    assert _download(kind, url, destination, content, observe) == destination
    assert destination.read_bytes() == content
    assert events[0].completed_bytes == 0
    assert events[-1].completed_bytes == len(content)
    assert any(0 < event.completed_bytes < len(content) for event in events)
    assert [event.completed_bytes for event in events] == sorted(
        event.completed_bytes for event in events
    )
    assert {event.total_bytes for event in events} == {len(content)}
    assert not destination.with_suffix(".zip.partial").exists()


@pytest.mark.parametrize("kind", ["application", "launcher"])
def test_transfer_observer_failure_preserves_successful_download(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    kind: str,
) -> None:
    """Retire a failed observer without making valid release bytes unavailable."""
    source = tmp_path / "source.zip"
    content = b"synthetic artifact"
    source.write_bytes(content)
    calls = 0

    def observe(progress: TransferProgress) -> None:
        """Represent an unavailable presentation receiver."""
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic unavailable transfer observer")

    result = _download(kind, source.as_uri(), tmp_path / "result.zip", content, observe)
    assert result.read_bytes() == content
    assert calls == 1
    assert "synthetic unavailable transfer observer" in caplog.text


@pytest.mark.parametrize("kind", ["application", "launcher"])
def test_truncated_transfer_keeps_previous_destination(
    tmp_path: Path,
    kind: str,
) -> None:
    """Keep byte notifications separate from successful size validation and promotion."""
    content = b"complete synthetic release"
    source = tmp_path / "truncated.zip"
    source.write_bytes(content[:5])
    destination = tmp_path / "download.zip"
    destination.write_bytes(b"previous artifact")
    events: list[TransferProgress] = []
    with pytest.raises(
        (AssetDownloadError, LauncherBundleDownloadError), match="size mismatch"
    ):
        _download(kind, source.as_uri(), destination, content, events.append)
    assert destination.read_bytes() == b"previous artifact"
    assert events[-1].completed_bytes == 5
    assert events[-1].total_bytes == len(content)
    assert not destination.with_suffix(".zip.partial").exists()
