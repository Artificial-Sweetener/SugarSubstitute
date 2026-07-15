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

"""Decode Comfy preview image bytes without Qt dependencies."""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

from PIL import Image


class _PreviewImage(Protocol):
    """Describe the Pillow image behavior required for preview decoding."""

    width: int
    height: int

    def convert(self, mode: str) -> "_PreviewImage":
        """Return this image converted to another pixel mode."""

    def tobytes(self, *args: str) -> bytes:
        """Return raw image bytes for the requested format."""


@dataclass(frozen=True)
class DecodedPreviewImage:
    """Describe one decoded RGBA preview image payload."""

    rgba_bytes: bytes
    width: int
    height: int


def decode_preview_image(
    image_bytes: bytes,
    *,
    open_image: Callable[[io.BytesIO], object] | None = None,
) -> DecodedPreviewImage:
    """Decode preview image bytes into detached RGBA payload data."""

    image = cast(_PreviewImage, (open_image or Image.open)(io.BytesIO(image_bytes)))
    try:
        preview_image = image.convert("RGBA")
        return DecodedPreviewImage(
            rgba_bytes=preview_image.tobytes("raw", "RGBA"),
            width=preview_image.width,
            height=preview_image.height,
        )
    finally:
        close = getattr(image, "close", None)
        if callable(close):
            close()


__all__ = [
    "DecodedPreviewImage",
    "decode_preview_image",
]
