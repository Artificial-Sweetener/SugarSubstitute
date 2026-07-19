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

"""Encode optional JPEG companions from canonical output images."""

from __future__ import annotations

import io

from PIL import Image

from substitute.domain.generation import JpegOutputSettings, JpegSizingMode

_MIN_TARGET_QUALITY = 1
_MAX_TARGET_QUALITY = 95


class JpegCompanionEncoder:
    """Encode RGB JPEG bytes using fixed quality or a bounded size search."""

    def encode(self, image: Image.Image, settings: JpegOutputSettings) -> bytes:
        """Return JPEG bytes matching the configured sizing policy."""

        prepared = _jpeg_compatible_image(image)
        if settings.sizing_mode is JpegSizingMode.QUALITY:
            return _encode_quality(prepared, settings.quality)
        return _encode_target_size(prepared, settings.target_size_kib * 1024)


def _jpeg_compatible_image(image: Image.Image) -> Image.Image:
    """Flatten transparency against white and return an RGB image."""

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _encode_quality(image: Image.Image, quality: int) -> bytes:
    """Encode one optimized JPEG at a bounded quality."""

    buffer = io.BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=max(1, min(quality, 100)),
        optimize=True,
    )
    return buffer.getvalue()


def _encode_target_size(image: Image.Image, target_bytes: int) -> bytes:
    """Return the closest bounded-quality JPEG at or below the target when possible."""

    lower = _MIN_TARGET_QUALITY
    upper = _MAX_TARGET_QUALITY
    best_under: bytes | None = None
    smallest: bytes | None = None
    while lower <= upper:
        quality = (lower + upper) // 2
        encoded = _encode_quality(image, quality)
        if smallest is None or len(encoded) < len(smallest):
            smallest = encoded
        if len(encoded) <= target_bytes:
            best_under = encoded
            lower = quality + 1
        else:
            upper = quality - 1
    if best_under is not None:
        return best_under
    if smallest is None:
        raise RuntimeError("JPEG target-size search produced no candidate.")
    return smallest


__all__ = ["JpegCompanionEncoder"]
