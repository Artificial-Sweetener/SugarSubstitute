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

"""Verify the SugarSubstitute Input CuteCanvas document boundary."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.application.workflows.input_canvas_document_port import (
    CanvasDocumentMutation,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from cutecanvas import CuteCanvas, EditorCapability

from tests.support.cutecanvas.input_document import InputDocumentFactory
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _image(color: QColor) -> QImage:
    """Create one non-null source image for document admission tests."""

    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def _app() -> QApplication:
    """Return a QApplication before constructing one CuteCanvas widget."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_input_document_uses_application_identity_for_persisted_compositions(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Input routes should retain host UUIDs as restorable composition identities."""

    _app()
    document = input_document_factory()
    first_image_id = uuid4()
    second_image_id = uuid4()
    first = _image(QColor("red"))
    second = _image(QColor("blue"))

    assert (
        document.ensure_image_cached(first_image_id, first, None)
        is CanvasDocumentMutation.ADDED
    )
    assert (
        document.ensure_image_cached(second_image_id, second, None)
        is CanvasDocumentMutation.ADDED
    )
    assert document.current_image_id() is None
    assert document.set_current_image_id(first_image_id) is True
    assert document.current_image_id() == first_image_id
    assert set(document.canvas.compositionIDs())
    assert first_image_id in document.canvas.compositionIDs()


def test_input_document_close_is_idempotent(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Repeated host teardown should close one Input document only once."""

    _app()
    document = input_document_factory()

    document.close()
    document.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_input_document_exports_inactive_mask_without_route_mutation(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Generation preflight can read a dirty inactive mask without changing Input focus."""

    _app()
    document = input_document_factory()
    first_image_id = uuid4()
    second_image_id = uuid4()
    assert (
        document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
        is CanvasDocumentMutation.ADDED
    )
    first_mask_id = document.create_blank_mask(first_image_id, QSize(24, 16))
    assert first_mask_id is not None
    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.ADDED
    )
    assert document.set_current_image_id(second_image_id) is True

    exported = document.export_mask_image(first_mask_id)

    assert exported is not None
    assert exported.size() == QSize(24, 16)
    assert document.current_image_id() == second_image_id


def test_input_document_relays_repeated_real_mask_history_signals(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Repeated mask mutations and replay should invalidate consumers exactly."""

    app = _app()
    document = input_document_factory()
    image_id = uuid4()
    document.ensure_image_cached(image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(image_id)
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    changes: list[None] = []
    document.maskContentChanged.connect(lambda: changes.append(None))
    coverage = QImage(24, 16, QImage.Format.Format_Grayscale8)
    coverage.fill(255)

    try:
        for cycle in range(32):
            assert document.canvas.replaceMaskImage(mask_id, coverage)
            app.processEvents()
            assert len(changes) == cycle * 2 + 1

            assert document.canvas.undoSceneEdit()
            app.processEvents()
            assert len(changes) == cycle * 2 + 2
    finally:
        document.close()


def test_input_document_admission_never_steals_an_existing_route(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Background admission and replacement must leave the active image unchanged."""

    app = _app()
    document = input_document_factory()
    first_image_id = uuid4()
    second_image_id = uuid4()
    document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(first_image_id)
    active_composition_id = document.canvas.currentCompositionID()

    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.ADDED
    )
    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("green")), None)
        is CanvasDocumentMutation.REPLACED
    )
    app.processEvents()

    assert document.current_image_id() == first_image_id
    assert document.canvas.currentCompositionID() == active_composition_id


def test_input_document_replacement_preserves_active_masks_and_view(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Regeneration must not replace an active image's composition-owned state."""

    app = _app()
    document = input_document_factory()
    image_id = uuid4()
    source = _image(QColor("red"))
    document.ensure_image_cached(image_id, source, None)
    assert document.set_current_image_id(image_id)
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    document.canvas.resize(640, 420)
    document.canvas.show()
    app.processEvents()
    document.canvas.applyZoom(document.canvas.currentZoom() * 1.8)
    zoom = document.canvas.currentZoom()
    viewport = document.canvas.currentViewportRect()
    composition_id = document.canvas.currentCompositionID()

    assert (
        document.ensure_image_cached(image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.REPLACED
    )
    app.processEvents()

    assert document.canvas.currentCompositionID() == composition_id
    assert document.current_image_id() == image_id
    assert document.canvas.currentZoom() == zoom
    assert document.canvas.currentViewportRect() == viewport
    assert tuple(
        mask.mask_id for mask in document.canvas.listMasksForComposition(composition_id)
    ) == (mask_id,)


def test_input_document_retires_only_the_requested_unreferenced_composition(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Application reference accounting should control document composition lifetime."""

    _app()
    document = input_document_factory()
    first_image_id = uuid4()
    second_image_id = uuid4()
    document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
    document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)

    assert document.remove_unreferenced_image(first_image_id) is True
    assert document.contains(first_image_id) is False
    assert document.contains(second_image_id) is True
    assert document.set_current_image_id(first_image_id) is False
    assert document.set_current_image_id(second_image_id) is True


def test_input_document_allows_mask_movement_without_unlocking_source_image(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Move should target the selected mask while the source image remains fixed."""

    _app()
    document = input_document_factory()
    image_id = uuid4()
    document.ensure_image_cached(image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(image_id)
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None

    masks = document.canvas.listMasksForComposition()
    assert len(masks) == 1
    mask = masks[0]
    assert mask.mask_id == mask_id
    assert mask.interaction.movable is True
    assert EditorCapability.MOVE_LAYERS in document.canvas.editorPolicy().capabilities

    snapshot = document.canvas.currentScene()
    assert snapshot is not None
    source_layers = [layer for layer in snapshot.layers if layer.source_id != mask_id]
    assert source_layers
    assert all(layer.interaction.movable is False for layer in source_layers)
    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_MOVE) is True
    assert document.current_canvas_operation() == CuteCanvas.CONTROL_MODE_MOVE


def test_input_document_accepts_registered_cutecanvas_operations_only(
    input_document_factory: InputDocumentFactory,
) -> None:
    """The document boundary should activate native operations without product IDs."""

    _app()
    document = input_document_factory()
    image_id = uuid4()
    document.ensure_image_cached(image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(image_id)
    assert document.create_blank_mask(image_id, QSize(24, 16)) is not None

    for operation_id in (
        CuteCanvas.CONTROL_MODE_MOVE,
        CuteCanvas.CONTROL_MODE_MASK_RECTANGLE,
        CuteCanvas.CONTROL_MODE_MASK_ELLIPSE,
        CuteCanvas.CONTROL_MODE_MASK_LASSO,
        CuteCanvas.CONTROL_MODE_DRAW_BRUSH,
        CuteCanvas.CONTROL_MODE_PANZOOM,
    ):
        assert document.set_canvas_operation(operation_id) is True
        assert document.current_canvas_operation() == operation_id

    assert document.set_canvas_operation("foreign-operation") is False


def test_input_document_accepts_new_selection_during_temporary_navigation(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Toolbar selection remains truthful while Space keeps Pan/Zoom effective."""

    app = _app()
    document = input_document_factory()
    image_id = uuid4()
    document.ensure_image_cached(image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(image_id)
    assert document.create_blank_mask(image_id, QSize(24, 16)) is not None
    canvas = document.canvas
    canvas.show()
    canvas.setFocus()
    app.processEvents()
    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_DRAW_BRUSH)

    QTest.keyPress(canvas, Qt.Key.Key_Space)
    assert document.current_canvas_operation() == CuteCanvas.CONTROL_MODE_PANZOOM
    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_MASK_RECTANGLE)
    assert document.current_canvas_operation() == CuteCanvas.CONTROL_MODE_PANZOOM

    QTest.keyRelease(canvas, Qt.Key.Key_Space)
    assert document.current_canvas_operation() == CuteCanvas.CONTROL_MODE_MASK_RECTANGLE


def test_input_document_round_trips_complete_editable_authority(
    tmp_path: Path,
    input_document_factory: InputDocumentFactory,
) -> None:
    """Session persistence should retain exact image and hybrid mask identities."""

    _app()
    archive_path = tmp_path / "input-document.ccanvas"
    image_id = uuid4()
    source = input_document_factory()
    source.ensure_image_cached(image_id, _image(QColor("red")), None)
    mask_id = source.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    coverage = QImage(24, 16, QImage.Format.Format_Grayscale8)
    coverage.fill(255)
    assert source.canvas.replaceMaskImage(mask_id, coverage)

    saved_ids = source.editable_persistence.save_editable_document(archive_path)
    source.close()

    restored = input_document_factory()
    assert (
        restored.editable_persistence.restore_editable_document(archive_path)
        == saved_ids
        == (image_id,)
    )
    assert restored.contains(image_id)
    assert restored.contains_mask(image_id, mask_id)
    exported = restored.export_mask_image(mask_id)
    assert exported is not None
    assert exported.size() == QSize(24, 16)
    assert QColor(exported.pixel(12, 8)).red() == 255

    replacement = _image(QColor("blue"))
    assert (
        restored.ensure_image_cached(image_id, replacement, tmp_path / "source.png")
        is CanvasDocumentMutation.REPLACED
    )
    assert restored.contains_mask(image_id, mask_id)
    restored.close()


def test_restored_input_document_paints_existing_mask_before_render_settles(
    tmp_path: Path,
    input_document_factory: InputDocumentFactory,
) -> None:
    """Input editing must stay live while a large restored mask is still loading."""

    app = _app()
    archive = tmp_path / "loading-input-document.ccanvas"
    image_id = uuid4()
    source = input_document_factory()
    source_closed = False
    restored: InputCanvasDocument | None = None
    try:
        image = QImage(4096, 4096, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("white"))
        source.ensure_image_cached(image_id, image, None)
        mask_id = source.create_blank_mask(image_id, image.size())
        assert mask_id is not None
        existing = QImage(4096, 4096, QImage.Format.Format_Grayscale8)
        existing.fill(0)
        painter = QPainter(existing)
        try:
            painter.fillRect(QRect(256, 256, 1024, 1024), QColor("white"))
        finally:
            painter.end()
        assert source.canvas.replaceMaskImage(mask_id, existing)
        source.canvas.resize(1024, 1024)
        source.canvas.show()
        app.processEvents()
        source.canvas.setZoomFit()
        assert source.set_canvas_operation(CuteCanvas.CONTROL_MODE_DRAW_BRUSH)
        for index in range(16):
            QTest.mouseClick(
                source.canvas,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                QPoint(160 + index % 4 * 180, 180 + index // 4 * 180),
            )
            app.processEvents()
        source.editable_persistence.save_editable_document(archive)
        source.close()
        source_closed = True

        restored = input_document_factory()
        assert restored.editable_persistence.restore_editable_document(archive) == (
            image_id,
        )
        assert restored.set_current_image_id(image_id)
        assert restored.set_active_mask_id(mask_id)
        assert restored.set_canvas_operation(CuteCanvas.CONTROL_MODE_DRAW_BRUSH)
        restored.canvas.setBrushSize(128)
        restored.canvas.resize(1024, 1024)
        restored.canvas.show()
        app.processEvents()
        restored.canvas.setZoomFit()
        point = QPoint(512, 512)
        history_before = restored.canvas.getMaskUndoState(mask_id)
        assert history_before is not None

        QTest.mousePress(
            restored.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )

        def stroke_is_visible() -> bool:
            """Report whether the active brush stroke reached the mounted canvas."""

            color = restored.canvas.grab().toImage().pixelColor(point)
            channels = color.red(), color.green(), color.blue()
            return max(channels) - min(channels) >= 20

        wait_for_qt_condition(stroke_is_visible)
        QTest.mouseRelease(
            restored.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )

        def stroke_is_committed() -> bool:
            """Report whether release committed one undoable mask edit."""

            history_after = restored.canvas.getMaskUndoState(mask_id)
            return (
                history_after is not None
                and history_after.undo_depth > history_before.undo_depth
            )

        wait_for_qt_condition(stroke_is_committed)
        assert stroke_is_visible()
        exported = restored.export_mask_image(mask_id)
        assert exported is not None
        assert exported.pixelColor(2048, 2048).red() > 0
        assert restored.canvas.undoSceneEdit()
    finally:
        if restored is not None:
            restored.close()
        if not source_closed:
            source.close()
