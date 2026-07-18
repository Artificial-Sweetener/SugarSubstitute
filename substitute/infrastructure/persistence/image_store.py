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

"""Implement filesystem-backed image load/save operations for canvas services."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QImageReader

from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("infrastructure.persistence.image_store")


class QtImageStore:
    """Provide Qt-backed image load and transparent-mask save operations."""

    def load_image(self, path: Path) -> object | None:
        """Load image with auto-transform enabled and return QImage on success."""

        resolved_path = Path(path)
        try:
            reader = QImageReader(str(resolved_path))
            reader.setAutoTransform(True)
            image = reader.read()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to read image",
                path=resolved_path,
                error=error,
            )
            return None

        if image.isNull():
            log_warning(
                _LOGGER,
                "Image reader returned null image",
                path=resolved_path,
            )
            return None
        return image

    def save_image(self, path: Path, *, image: object) -> bool:
        """Persist Qt-compatible image object at destination path."""

        resolved_path = Path(path)
        if image is None:
            log_warning(
                _LOGGER,
                "Image save rejected because image payload is missing",
                path=resolved_path,
            )
            return False

        is_null = getattr(image, "isNull", None)
        if callable(is_null) and bool(is_null()):
            log_warning(
                _LOGGER,
                "Image save rejected because image payload is null",
                path=resolved_path,
            )
            return False

        save_image = getattr(image, "save", None)
        if not callable(save_image):
            log_warning(
                _LOGGER,
                "Image save rejected because payload does not expose save()",
                path=resolved_path,
                image_type=type(image).__name__,
            )
            return False

        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            return bool(save_image(str(resolved_path)))
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to save image payload",
                path=resolved_path,
                image_type=type(image).__name__,
                error=error,
            )
            return False

    def save_blank_mask(self, path: Path, *, size: object) -> bool:
        """Write a transparent ARGB32 mask image at the provided size."""

        width_getter = getattr(size, "width", None)
        height_getter = getattr(size, "height", None)
        if not callable(width_getter) or not callable(height_getter):
            log_warning(
                _LOGGER,
                "Mask save rejected because size object is invalid",
                size_type=type(size).__name__,
            )
            return False
        try:
            width = int(width_getter())
            height = int(height_getter())
            if width <= 0 or height <= 0:
                log_warning(
                    _LOGGER,
                    "Mask save rejected because dimensions are invalid",
                    width=width,
                    height=height,
                )
                return False
            resolved_path = Path(path)
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            blank_image = QImage(
                width, height, QImage.Format.Format_ARGB32_Premultiplied
            )
            blank_image.fill(getattr(Qt, "transparent", 0))
            return bool(blank_image.save(str(resolved_path)))
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to save blank mask image",
                path=path,
                error=error,
            )
            return False

    def save_blank_image(self, path: Path, *, width: int, height: int) -> bool:
        """Write an opaque neutral RGB image for synthetic Input canvas backing."""

        resolved_path = Path(path)
        if width <= 0 or height <= 0:
            log_warning(
                _LOGGER,
                "Blank image save rejected because dimensions are invalid",
                path=resolved_path,
                width=width,
                height=height,
            )
            return False
        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            blank_image = QImage(width, height, QImage.Format.Format_RGB32)
            blank_image.fill(QColor(24, 24, 24))
            return bool(blank_image.save(str(resolved_path)))
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to save blank Input canvas image",
                path=resolved_path,
                width=width,
                height=height,
                error=error,
            )
            return False

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return readable image dimensions after Qt reader transformations."""

        resolved_path = Path(path)
        try:
            reader = QImageReader(str(resolved_path))
            reader.setAutoTransform(True)
            image = reader.read()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to read image dimensions",
                path=resolved_path,
                error=error,
            )
            return None

        if image.isNull():
            log_warning(
                _LOGGER,
                "Image dimension read returned null image",
                path=resolved_path,
            )
            return None
        return (int(image.width()), int(image.height()))


__all__ = [
    "QtImageStore",
]
