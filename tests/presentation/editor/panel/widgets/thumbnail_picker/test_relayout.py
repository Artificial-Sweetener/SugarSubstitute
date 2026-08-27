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

"""Verify thumbnail changes propagate through mounted node-card geometry."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor

from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from tests.presentation.editor.panel.widgets.thumbnail_picker.support import (
    ThumbnailPickerOwner,
    create_test_image,
)


def test_image_card_relayouts_after_thumbnail_height_change(
    thumbnail_owner: ThumbnailPickerOwner,
    tmp_path: Path,
) -> None:
    """LoadImage card bodies expand after the selected image becomes taller."""

    wide_path = tmp_path / "wide.png"
    tall_path = tmp_path / "tall.png"
    create_test_image(wide_path, width=400, height=100, color="red")
    create_test_image(tall_path, width=400, height=600, color="blue")
    scenario = thumbnail_owner.build_card(
        class_type="LoadImage",
        image_path=str(wide_path),
    )
    picker = scenario.picker(ImagePicker)
    row, content_body = scenario.field_geometry()
    thumbnail_owner.wait_until(
        lambda: content_body.maximumHeight() >= row.sizeHint().height()
    )
    initial_row_height = row.sizeHint().height()

    picker.set_thumbnail(str(tall_path))
    thumbnail_owner.wait_until(
        lambda: (
            row.sizeHint().height() > initial_row_height
            and content_body.maximumHeight() >= row.sizeHint().height()
        )
    )

    assert row.sizeHint().height() > initial_row_height
    assert content_body.maximumHeight() >= row.sizeHint().height()


def test_mask_card_relayouts_after_thumbnail_height_change(
    thumbnail_owner: ThumbnailPickerOwner,
    tmp_path: Path,
) -> None:
    """LoadImageMask card bodies expand after the selected mask becomes taller."""

    wide_path = tmp_path / "wide.png"
    tall_path = tmp_path / "tall.png"
    create_test_image(wide_path, width=400, height=100, color="green")
    create_test_image(tall_path, width=400, height=600, color="yellow")
    scenario = thumbnail_owner.build_card(
        class_type="LoadImageMask",
        image_path=str(wide_path),
    )
    picker = scenario.picker(MaskPicker)
    row, content_body = scenario.field_geometry()
    thumbnail_owner.wait_until(
        lambda: content_body.maximumHeight() >= row.sizeHint().height()
    )
    initial_row_height = row.sizeHint().height()

    picker.set_mask_path(str(tall_path))
    thumbnail_owner.wait_until(
        lambda: (
            row.sizeHint().height() > initial_row_height
            and content_body.maximumHeight() >= row.sizeHint().height()
        )
    )

    assert row.sizeHint().height() > initial_row_height
    assert content_body.maximumHeight() >= row.sizeHint().height()


def test_mask_refresh_reads_updated_same_file_bytes(
    thumbnail_owner: ThumbnailPickerOwner,
    tmp_path: Path,
) -> None:
    """Autosave refresh bypasses stale same-path image data."""

    _ = thumbnail_owner.application
    mask_path = tmp_path / "mask.png"
    create_test_image(mask_path, width=4, height=4, color="red")
    first = MaskPicker._load_mask_pixmap_from_file_bytes(str(mask_path))

    create_test_image(mask_path, width=4, height=4, color="blue")
    second = MaskPicker._load_mask_pixmap_from_file_bytes(str(mask_path))

    assert first.toImage().pixelColor(0, 0) == QColor("red")
    assert second.toImage().pixelColor(0, 0) == QColor("blue")
