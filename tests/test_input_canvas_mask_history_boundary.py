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

"""Protect workflow-owned Input mask structure from user undo."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from substitute.presentation.canvas.input.input_document import InputCanvasDocument


def _application() -> QApplication:
    """Return the process application required by the real Input canvas."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_input_mask_survives_undo_beyond_every_user_edit() -> None:
    """Exhaustive undo must preserve the mask required by the workflow route."""

    application = _application()
    document = InputCanvasDocument(features=("mask",))
    try:
        image_id = uuid4()
        image = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("white"))
        document.ensure_image_cached(image_id, image, None)
        mask_id = document.create_blank_mask(image_id, image.size())

        assert mask_id is not None
        assert document.set_active_mask_id(mask_id)
        assert document.canvas.editor.history.can_undo is False
        for index in range(32):
            offset = float(index % 8 * 20)
            assert (
                document.canvas.editor.coverage.rectangle(
                    QRectF(offset, offset, 80.0, 80.0)
                )
                is not None
            )
        application.processEvents()

        for _ in range(32):
            assert document.canvas.editor.history.undo()
        for _ in range(8):
            assert document.canvas.editor.history.undo() is False

        assert document.contains_mask(image_id, mask_id)
        assert document.active_image_has_mask_target(image_id)
        assert document.canvas.editor.history.can_undo is False
        assert (
            document.canvas.editor.coverage.rectangle(QRectF(24.0, 24.0, 48.0, 48.0))
            is not None
        )
        assert document.canvas.editor.history.undo()
        assert document.contains_mask(image_id, mask_id)
        assert document.active_image_has_mask_target(image_id)
    finally:
        document.close()


def test_loaded_input_mask_is_not_document_admission_history(tmp_path: Path) -> None:
    """A routed mask loaded from disk must remain after empty-history undo."""

    application = _application()
    mask_path = tmp_path / "required-mask.png"
    mask = QImage(64, 48, QImage.Format.Format_Grayscale8)
    mask.fill(255)
    assert mask.save(str(mask_path))
    document = InputCanvasDocument(features=("mask",))
    try:
        image_id = uuid4()
        image = QImage(64, 48, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("white"))
        document.ensure_image_cached(image_id, image, None)

        mask_id = document.load_mask_from_file(image_id, mask_path)

        assert mask_id is not None
        assert document.canvas.editor.history.can_undo is False
        assert document.canvas.editor.history.undo() is False
        assert document.contains_mask(image_id, mask_id)
        application.processEvents()
    finally:
        document.close()
