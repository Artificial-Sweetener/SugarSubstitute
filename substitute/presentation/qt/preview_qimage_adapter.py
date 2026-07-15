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

"""Convert decoded Comfy preview images into detached Qt images."""

from __future__ import annotations

from PySide6.QtGui import QImage

from substitute.infrastructure.comfy.preview_image_decoder import DecodedPreviewImage


def preview_image_to_qimage(
    preview_image: DecodedPreviewImage,
    *,
    qimage_class: type[QImage] | None = None,
) -> QImage:
    """Return a detached QImage for one decoded preview image."""

    qimage_owner = qimage_class or QImage
    format_owner = getattr(qimage_owner, "Format", None)
    image_format = (
        getattr(format_owner, "Format_RGBA8888", None)
        if format_owner is not None
        else None
    )
    if image_format is None:
        image_format = getattr(qimage_owner, "Format_RGBA8888")
    qimage = qimage_owner(
        preview_image.rgba_bytes,
        preview_image.width,
        preview_image.height,
        image_format,
    )
    return qimage.copy()


__all__ = ["preview_image_to_qimage"]
