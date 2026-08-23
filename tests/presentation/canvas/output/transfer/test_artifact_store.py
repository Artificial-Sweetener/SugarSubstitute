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

"""Contract tests for selected Output transfer artifact materialization."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QColor, QImage

from substitute.domain.generation import JpegOutputSettings, OutputTransferFormat
from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifactStore,
)
from substitute.infrastructure.comfy.jpeg_companion_encoder import (
    JpegCompanionEncoder,
)


def test_png_transfer_stages_memory_only_image_and_retains_it_until_close(
    tmp_path: Path,
) -> None:
    """Memory-only Output images should remain transferable through staged PNG."""

    store = OutputTransferArtifactStore(tmp_path / "transfers")

    artifact = store.materialize(
        _image(),
        canonical_path=None,
        transfer_format=OutputTransferFormat.CANONICAL_PNG,
        jpeg_settings=JpegOutputSettings(),
    )

    assert artifact is not None
    assert artifact.staged is True
    assert artifact.mime_type == "image/png"
    assert artifact.path.suffix == ".png"
    assert artifact.path.is_file()
    assert artifact.image.size() == _image().size()

    store.close()

    assert artifact.path.exists() is False


def test_released_staged_transfer_is_deleted_before_store_shutdown(
    tmp_path: Path,
) -> None:
    """A replaced drag or clipboard target must not accumulate staged artifacts."""

    store = OutputTransferArtifactStore(tmp_path / "transfers")
    artifact = store.materialize(
        _image(),
        canonical_path=None,
        transfer_format=OutputTransferFormat.CANONICAL_PNG,
        jpeg_settings=JpegOutputSettings(),
    )

    assert artifact is not None
    artifact.release()

    assert artifact.path.exists() is False


def test_store_removes_only_stale_managed_artifacts_at_startup(tmp_path: Path) -> None:
    """A later application process should reclaim abandoned transfer files safely."""

    stale_png = tmp_path / "output-transfer-stale.png"
    stale_jpeg = tmp_path / "output-transfer-stale.jpg"
    unrelated = tmp_path / "user-output.png"
    nested = tmp_path / "output-transfer-folder"
    stale_png.write_bytes(b"stale")
    stale_jpeg.write_bytes(b"stale")
    unrelated.write_bytes(b"keep")
    nested.mkdir()

    OutputTransferArtifactStore(tmp_path)

    assert stale_png.exists() is False
    assert stale_jpeg.exists() is False
    assert unrelated.read_bytes() == b"keep"
    assert nested.is_dir()


def test_jpeg_transfer_uses_exact_existing_companion_when_available(
    tmp_path: Path,
) -> None:
    """A configured JPEG transfer should use the canonical path's exact sibling."""

    canonical_path = tmp_path / "output.png"
    image = _image()
    assert image.save(str(canonical_path), "PNG")  # type: ignore[call-overload]
    companion_path = canonical_path.with_suffix(".jpg")
    assert image.save(str(companion_path), "JPG")  # type: ignore[call-overload]
    store = OutputTransferArtifactStore(tmp_path / "transfers")

    artifact = store.materialize(
        image,
        canonical_path=canonical_path,
        transfer_format=OutputTransferFormat.COMPANION_JPEG,
        jpeg_settings=JpegOutputSettings(enabled=True),
    )

    assert artifact is not None
    assert artifact.staged is False
    assert artifact.path == companion_path
    assert artifact.mime_type == "image/jpeg"
    assert artifact.data == companion_path.read_bytes()


def test_jpeg_transfer_stages_jpeg_without_a_durable_companion(tmp_path: Path) -> None:
    """Missing companions should produce JPEG, never silently fall back to PNG."""

    store = OutputTransferArtifactStore(tmp_path / "transfers")

    artifact = store.materialize(
        _image(),
        canonical_path=None,
        transfer_format=OutputTransferFormat.COMPANION_JPEG,
        jpeg_settings=JpegOutputSettings(enabled=True, quality=80),
    )

    assert artifact is not None
    assert artifact.staged is True
    assert artifact.path.suffix == ".jpg"
    assert artifact.mime_type == "image/jpeg"
    assert artifact.data.startswith(b"\xff\xd8")


def test_store_removes_a_staged_file_when_encoding_is_cancelled(tmp_path: Path) -> None:
    """Cancellation after encoding must leave no artifact for a stale transfer."""

    cancellation = _CancellationFlag()
    store = OutputTransferArtifactStore(
        tmp_path / "transfers",
        jpeg_encoder=_CancellingJpegEncoder(cancellation),
    )

    artifact = store.materialize(
        _image(),
        canonical_path=None,
        transfer_format=OutputTransferFormat.COMPANION_JPEG,
        jpeg_settings=JpegOutputSettings(enabled=True),
        cancellation_requested=lambda: cancellation.requested,
    )

    assert artifact is None
    assert (tmp_path / "transfers").exists() is False


class _CancellationFlag:
    """Expose mutable cancellation state to one deterministic encoder test."""

    def __init__(self) -> None:
        """Start with cancellation disabled."""

        self.requested = False


class _CancellingJpegEncoder(JpegCompanionEncoder):
    """Request cancellation immediately after producing valid JPEG bytes."""

    def __init__(self, cancellation: _CancellationFlag) -> None:
        """Retain the test-owned cancellation state."""

        self._cancellation = cancellation

    def encode(self, image: Image.Image, settings: JpegOutputSettings) -> bytes:
        """Produce the selected representation before requesting cancellation."""

        encoded = super().encode(image, settings)
        self._cancellation.requested = True
        return encoded


def _image() -> QImage:
    """Return a deterministic transparent image for transfer materialization."""

    image = QImage(8, 6, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(2, 3, QColor(255, 0, 0, 128))
    image.setDevicePixelRatio(1.0)
    return image
