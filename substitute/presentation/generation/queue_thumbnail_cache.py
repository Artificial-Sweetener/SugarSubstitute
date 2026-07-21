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

"""Load and cache generation queue thumbnails from output image paths."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
    qt_filesystem_path,
)


class GenerationQueueThumbnailCache:
    """Provide bounded lazy thumbnail pixmap loading for queue rows."""

    def __init__(self, *, capacity: int = 128) -> None:
        """Create a thumbnail cache with a fixed entry capacity."""

        self._capacity = max(1, capacity)
        self._cache: OrderedDict[tuple[Path, int, int], QPixmap] = OrderedDict()

    def thumbnail(self, path: Path, size: QSize) -> QPixmap | None:
        """Return a scaled thumbnail pixmap for an existing image path."""

        resolved_path = operational_path(path)
        if not resolved_path.exists():
            return None
        key = (resolved_path, size.width(), size.height())
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        pixmap = QPixmap(qt_filesystem_path(resolved_path))
        if pixmap.isNull():
            return None
        scaled = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cache[key] = scaled
        self._cache.move_to_end(key)
        while len(self._cache) > self._capacity:
            self._cache.popitem(last=False)
        return scaled

    def clear(self) -> None:
        """Clear all cached thumbnails."""

        self._cache.clear()


__all__ = ["GenerationQueueThumbnailCache"]
