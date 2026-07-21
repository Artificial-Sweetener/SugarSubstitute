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

"""Contract tests for Qt-backed image repository behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from substitute.infrastructure.persistence import QtImageStore
from sugarsubstitute_shared.windows_long_paths import operational_path


class _Size:
    """Expose a Qt-like size object for blank-mask save tests."""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        """Return width."""

        return self._width

    def height(self) -> int:
        """Return height."""

        return self._height


def test_save_blank_mask_creates_transparent_image_with_requested_size(
    tmp_path: Path,
) -> None:
    """Qt image store should preserve blank-mask save behavior."""

    image_path = tmp_path / "mask.png"
    store = QtImageStore()

    saved = store.save_blank_mask(image_path, size=_Size(21, 34))

    assert saved is True
    assert store.image_dimensions(image_path) == (21, 34)


def test_save_blank_image_creates_opaque_surface_with_requested_size(
    tmp_path: Path,
) -> None:
    """Synthetic Input backing images should be readable opaque RGB surfaces."""

    image_path = tmp_path / "input-surface.png"
    store = QtImageStore()

    saved = store.save_blank_image(image_path, width=1024, height=768)
    loaded = store.load_image(image_path)

    assert saved is True
    assert store.image_dimensions(image_path) == (1024, 768)
    assert isinstance(loaded, QImage)
    assert loaded.hasAlphaChannel() is False


def test_image_dimensions_returns_saved_image_size(tmp_path: Path) -> None:
    """Qt image store should report dimensions for readable image files."""

    image_path = tmp_path / "sample.png"
    image = QImage(13, 17, QImage.Format.Format_ARGB32)
    image.fill(0)
    assert image.save(str(image_path))

    dimensions = QtImageStore().image_dimensions(image_path)

    assert dimensions == (13, 17)


def test_image_dimensions_returns_none_for_missing_image(tmp_path: Path) -> None:
    """Qt image store should fail closed when dimensions are unreadable."""

    dimensions = QtImageStore().image_dimensions(tmp_path / "missing.png")

    assert dimensions is None


@pytest.mark.platforms("windows")
def test_qt_image_store_round_trips_an_image_beyond_max_path(tmp_path: Path) -> None:
    """Qt file APIs should consume the extended namespace without UI involvement."""

    image_path = operational_path(tmp_path / "qt-image")
    while len(str(image_path)) < 285:
        image_path /= "segment-0123456789abcdef"
    image_path /= "image.png"
    store = QtImageStore()

    assert store.save_blank_image(image_path, width=19, height=23) is True
    loaded = store.load_image(image_path)

    assert isinstance(loaded, QImage)
    assert store.image_dimensions(image_path) == (19, 23)
