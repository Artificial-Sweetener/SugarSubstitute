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

"""Materialize durable or staged artifacts for authorized Output transfers."""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from substitute.domain.generation import JpegOutputSettings, OutputTransferFormat
from substitute.infrastructure.comfy.jpeg_companion_encoder import (
    JpegCompanionEncoder,
)


class OutputTransferMaterializationError(RuntimeError):
    """Report that one configured outbound representation could not be built."""


class OutputTransferArtifactLease:
    """Retain one staged transfer path until its native consumer is replaced."""

    def __init__(self, release: Callable[[], None]) -> None:
        """Store the store-owned release operation for one staged artifact."""

        self._release = release
        self._released = False

    def release(self) -> None:
        """Release this lease once without affecting later transfer artifacts."""

        if self._released:
            return
        self._released = True
        self._release()


@dataclass(frozen=True, slots=True)
class OutputTransferArtifact:
    """Describe one selected representation and the file retained for consumers."""

    path: Path
    mime_type: str
    data: bytes
    image: QImage
    staged: bool
    lease: OutputTransferArtifactLease | None = None

    def __post_init__(self) -> None:
        """Detach mutable Qt pixels and normalized byte/path values."""

        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "data", bytes(self.data))
        object.__setattr__(self, "image", QImage(self.image))

    def release(self) -> None:
        """Release the staged path after its native transfer consumer retires."""

        if self.lease is not None:
            self.lease.release()


class OutputTransferArtifactStore:
    """Reuse authorized files or retain staged transfer representations."""

    def __init__(
        self,
        staging_directory: Path,
        *,
        jpeg_encoder: JpegCompanionEncoder | None = None,
    ) -> None:
        """Configure the application-owned staging directory and JPEG encoder."""

        self._staging_directory = Path(staging_directory)
        self._jpeg_encoder = jpeg_encoder or JpegCompanionEncoder()
        self._staged_paths: set[Path] = set()
        self._discard_stale_artifacts()

    def materialize(
        self,
        image: QImage,
        *,
        canonical_path: Path | None,
        transfer_format: OutputTransferFormat,
        jpeg_settings: JpegOutputSettings,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> OutputTransferArtifact | None:
        """Return one exact PNG or JPEG artifact for a transferable Output image."""

        if _is_cancelled(cancellation_requested):
            return None
        if image.isNull():
            raise OutputTransferMaterializationError(
                "Output image pixels are unavailable."
            )
        selected_path = _selected_existing_path(canonical_path, transfer_format)
        if selected_path is not None:
            artifact = _artifact_from_path(selected_path, transfer_format)
            if artifact is not None:
                return None if _is_cancelled(cancellation_requested) else artifact
        data = _encode_transfer_image(
            image,
            transfer_format=transfer_format,
            jpeg_settings=jpeg_settings,
            jpeg_encoder=self._jpeg_encoder,
        )
        if _is_cancelled(cancellation_requested):
            return None
        return self._stage(data, transfer_format, cancellation_requested)

    def close(self) -> None:
        """Delete only staged files created and retained by this store."""

        for path in tuple(self._staged_paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            self._staged_paths.discard(path)

    def _stage(
        self,
        data: bytes,
        transfer_format: OutputTransferFormat,
        cancellation_requested: Callable[[], bool] | None,
    ) -> OutputTransferArtifact | None:
        """Write one collision-safe staged artifact retained until explicit cleanup."""

        if _is_cancelled(cancellation_requested):
            return None
        self._staging_directory.mkdir(parents=True, exist_ok=True)
        path = (
            self._staging_directory
            / f"output-transfer-{uuid4().hex}{_suffix(transfer_format)}"
        )
        try:
            path.write_bytes(data)
        except OSError as error:
            raise OutputTransferMaterializationError(
                "Unable to stage the configured output transfer."
            ) from error
        if _is_cancelled(cancellation_requested):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        self._staged_paths.add(path)
        return _artifact_from_data(
            path,
            data,
            transfer_format,
            staged=True,
            lease=OutputTransferArtifactLease(lambda: self._release_staged_path(path)),
        )

    def _release_staged_path(self, path: Path) -> None:
        """Delete one no-longer-consumed staged artifact without touching durable files."""

        if path not in self._staged_paths:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return
        self._staged_paths.discard(path)

    def _discard_stale_artifacts(self) -> None:
        """Remove only prior-process transfer files from the managed cache root."""

        try:
            candidates = tuple(self._staging_directory.iterdir())
        except FileNotFoundError:
            return
        except OSError:
            return
        for path in candidates:
            if not _is_stale_transfer_artifact(path):
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


def _selected_existing_path(
    canonical_path: Path | None,
    transfer_format: OutputTransferFormat,
) -> Path | None:
    """Return the authorized canonical or exact companion path when it exists."""

    if canonical_path is None or canonical_path.suffix.casefold() != ".png":
        return None
    selected = (
        canonical_path
        if transfer_format is OutputTransferFormat.CANONICAL_PNG
        else canonical_path.with_suffix(".jpg")
    )
    return selected if selected.is_file() else None


def _artifact_from_path(
    path: Path,
    transfer_format: OutputTransferFormat,
) -> OutputTransferArtifact | None:
    """Read and validate one durable selected representation."""

    try:
        return _artifact_from_data(
            path, path.read_bytes(), transfer_format, staged=False
        )
    except (OSError, OutputTransferMaterializationError):
        return None


def _artifact_from_data(
    path: Path,
    data: bytes,
    transfer_format: OutputTransferFormat,
    *,
    staged: bool,
    lease: OutputTransferArtifactLease | None = None,
) -> OutputTransferArtifact:
    """Decode selected bytes so URL, raw MIME, and image data remain identical."""

    image = QImage.fromData(data)
    if image.isNull():
        raise OutputTransferMaterializationError(
            "Configured output transfer is invalid."
        )
    return OutputTransferArtifact(
        path=path,
        mime_type=_mime_type(transfer_format),
        data=data,
        image=image,
        staged=staged,
        lease=lease,
    )


def _encode_transfer_image(
    image: QImage,
    *,
    transfer_format: OutputTransferFormat,
    jpeg_settings: JpegOutputSettings,
    jpeg_encoder: JpegCompanionEncoder,
) -> bytes:
    """Encode the exact representation requested by transfer policy."""

    png_data = _encode_png(image)
    if transfer_format is OutputTransferFormat.CANONICAL_PNG:
        return png_data
    try:
        with Image.open(io.BytesIO(png_data)) as pillow_image:
            return jpeg_encoder.encode(pillow_image, jpeg_settings)
    except Exception as error:
        raise OutputTransferMaterializationError(
            "Unable to encode the configured JPEG output transfer."
        ) from error


def _encode_png(image: QImage) -> bytes:
    """Encode detached Output pixels as a canonical PNG byte stream."""

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OutputTransferMaterializationError("Unable to encode the output image.")
    try:
        # PySide accepts a str here even though its generated overload exposes bytes.
        if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
            raise OutputTransferMaterializationError(
                "Unable to encode the output image."
            )
        return bytes(buffer.data().data())
    finally:
        buffer.close()


def _mime_type(transfer_format: OutputTransferFormat) -> str:
    """Return the canonical MIME type for one selected transfer format."""

    return (
        "image/png"
        if transfer_format is OutputTransferFormat.CANONICAL_PNG
        else "image/jpeg"
    )


def _suffix(transfer_format: OutputTransferFormat) -> str:
    """Return the durable suffix for one selected transfer format."""

    return ".png" if transfer_format is OutputTransferFormat.CANONICAL_PNG else ".jpg"


def _is_stale_transfer_artifact(path: Path) -> bool:
    """Recognize one regular file created by this store in an earlier process."""

    return (
        not path.is_symlink()
        and path.is_file()
        and path.stem.startswith("output-transfer-")
        and path.suffix.casefold() in {".png", ".jpg"}
    )


def _is_cancelled(cancellation_requested: Callable[[], bool] | None) -> bool:
    """Return whether the current transfer task has been cancelled."""

    return cancellation_requested is not None and cancellation_requested()


__all__ = [
    "OutputTransferArtifact",
    "OutputTransferArtifactLease",
    "OutputTransferArtifactStore",
    "OutputTransferMaterializationError",
]
