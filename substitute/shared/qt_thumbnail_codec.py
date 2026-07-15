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

"""Read and write SugarSubstitute Qt-ready thumbnail assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile

from PySide6.QtGui import QImage

_MAGIC = b"SQTHMB1\0"
_VERSION = 1
_HEADER = struct.Struct("<8sHIIIIQ")
CONTENT_FORMAT_ARGB32_PREMULTIPLIED = "sqthumb-qimage-argb32-premultiplied"


@dataclass(frozen=True, slots=True)
class QtThumbnailInfo:
    """Describe one written Qt-ready thumbnail asset."""

    width: int
    height: int
    content_format: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class PreparedQtThumbnail:
    """Describe a prepared Qt thumbnail image and its raw payload."""

    width: int
    height: int
    qt_format: int
    bytes_per_line: int
    content_format: str
    payload: bytes

    @property
    def byte_size(self) -> int:
        """Return the raw thumbnail payload byte count."""

        return len(self.payload)


def prepare_qt_thumbnail(image: QImage) -> PreparedQtThumbnail:
    """Convert one ``QImage`` into the durable Qt thumbnail payload format."""

    if image.isNull():
        raise ValueError("Cannot prepare a null thumbnail image.")
    prepared = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return PreparedQtThumbnail(
        width=prepared.width(),
        height=prepared.height(),
        qt_format=prepared.format().value,
        bytes_per_line=prepared.bytesPerLine(),
        content_format=CONTENT_FORMAT_ARGB32_PREMULTIPLIED,
        payload=bytes(prepared.constBits()),
    )


def image_from_qt_thumbnail_payload(
    *,
    width: int,
    height: int,
    qt_format: int,
    bytes_per_line: int,
    payload: bytes,
) -> QImage | None:
    """Return a detached ``QImage`` from raw Qt thumbnail payload fields."""

    if width <= 0 or height <= 0 or bytes_per_line <= 0:
        return None
    expected_minimum_size = bytes_per_line * height
    if len(payload) < expected_minimum_size:
        return None
    try:
        image_format = QImage.Format(qt_format)
    except ValueError:
        return None
    image = QImage(
        payload,
        width,
        height,
        bytes_per_line,
        image_format,
    )
    if image.isNull():
        return None
    return image.copy()


def write_qt_thumbnail(path: Path, image: QImage) -> QtThumbnailInfo:
    """Persist one prepared ``QImage`` as an atomic Qt thumbnail asset."""

    prepared = prepare_qt_thumbnail(image)
    header = _HEADER.pack(
        _MAGIC,
        _VERSION,
        prepared.width,
        prepared.height,
        prepared.qt_format,
        prepared.bytes_per_line,
        prepared.byte_size,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "wb",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(header)
        handle.write(prepared.payload)
    temporary_path.replace(path)
    return QtThumbnailInfo(
        width=prepared.width,
        height=prepared.height,
        content_format=CONTENT_FORMAT_ARGB32_PREMULTIPLIED,
        byte_size=prepared.byte_size,
    )


def read_qt_thumbnail(path: Path) -> QImage | None:
    """Return a detached ``QImage`` from one thumbnail asset, or ``None`` if invalid."""

    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < _HEADER.size:
        return None
    magic, version, width, height, qt_format, bytes_per_line, payload_size = (
        _HEADER.unpack(data[: _HEADER.size])
    )
    if magic != _MAGIC or version != _VERSION:
        return None
    payload = data[_HEADER.size :]
    if len(payload) != payload_size:
        return None
    if width <= 0 or height <= 0 or bytes_per_line <= 0:
        return None
    expected_minimum_size = bytes_per_line * height
    if payload_size < expected_minimum_size:
        return None
    return image_from_qt_thumbnail_payload(
        width=width,
        height=height,
        qt_format=qt_format,
        bytes_per_line=bytes_per_line,
        payload=payload,
    )


__all__ = [
    "CONTENT_FORMAT_ARGB32_PREMULTIPLIED",
    "PreparedQtThumbnail",
    "QtThumbnailInfo",
    "image_from_qt_thumbnail_payload",
    "prepare_qt_thumbnail",
    "read_qt_thumbnail",
    "write_qt_thumbnail",
]
