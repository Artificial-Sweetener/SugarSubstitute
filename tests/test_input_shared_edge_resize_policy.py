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

"""Prove shared-edge mode temporarily enables only mask-layer movement."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from cutecanvas import CuteCanvas, LayerPolicy

from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_scene_mapping_changes import (
    InputSceneMappingChanges,
)
from substitute.presentation.canvas.input.input_shared_edge_resize_policy import (
    InputSharedEdgeResizePolicy,
)


def test_edge_resize_enables_all_masks_and_restores_exact_normal_policies() -> None:
    """Mode entry should enable mask seams without unlocking the source raster."""

    _application()
    document = InputCanvasDocument(features=("mask",))
    image_id = uuid4()
    document.ensure_image_cached(image_id, _image(), None)
    assert document.set_current_image_id(image_id)
    first_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    second_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert first_mask_id is not None and second_mask_id is not None
    before = document.canvas.currentScene()
    assert before is not None
    for layer in before.layers:
        if layer.source_id in {first_mask_id, second_mask_id}:
            assert document.canvas.setLayerInteractionPolicy(
                before.scene_id,
                layer.layer_id,
                LayerPolicy(selectable=True, pixel_editable=True),
            )
    policy = InputSharedEdgeResizePolicy(document.canvas, parent=document.canvas)
    before = document.canvas.currentScene()
    assert before is not None
    original = {layer.layer_id: layer.interaction for layer in before.layers}
    source_ids = {
        layer.layer_id
        for layer in before.layers
        if layer.source_id not in {first_mask_id, second_mask_id}
    }

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE)
    active = document.canvas.currentScene()
    assert active is not None
    assert all(
        layer.interaction.movable
        for layer in active.layers
        if layer.source_id in {first_mask_id, second_mask_id}
    )
    assert all(
        not layer.interaction.movable
        for layer in active.layers
        if layer.layer_id in source_ids
    )

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
    restored = document.canvas.currentScene()
    assert restored is not None
    assert {layer.layer_id: layer.interaction for layer in restored.layers} == original
    policy.close()
    document.close()


def test_mounted_input_masks_resize_one_shared_edge_and_export_aligned(
    tmp_path: Path,
) -> None:
    """The Sugar document should apply one retained seam edit and export masks."""

    application = _application()
    document = InputCanvasDocument(features=("mask",))
    image_id = uuid4()
    document.ensure_image_cached(image_id, _source_image(), None)
    assert document.set_current_image_id(image_id)
    first_mask_id = document.load_mask_from_file(
        image_id,
        _save_mask(tmp_path / "left.png", QRect(40, 20, 60, 60)),
    )
    second_mask_id = document.load_mask_from_file(
        image_id,
        _save_mask(tmp_path / "right.png", QRect(100, 20, 60, 60)),
    )
    assert first_mask_id is not None and second_mask_id is not None
    policy = InputSharedEdgeResizePolicy(document.canvas, parent=document.canvas)
    mappings = InputSceneMappingChanges(document.canvas, parent=document.canvas)
    committed: list[None] = []
    pixel_changes: list[None] = []
    mappings.changed.connect(lambda: committed.append(None))
    document.maskContentChanged.connect(lambda: pixel_changes.append(None))
    document.canvas.resize(800, 600)
    document.canvas.show()
    application.processEvents()

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE)
    application.processEvents()
    start = _panel_point(document.canvas, 100.0, 50.0)
    end = _panel_point(document.canvas, 120.0, 50.0)
    QTest.mouseMove(document.canvas, start)
    QTest.mousePress(document.canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(document.canvas, end)
    assert committed == []
    QTest.mouseRelease(document.canvas, Qt.MouseButton.LeftButton, pos=end)
    application.processEvents()

    assert committed == []
    assert document.canvas.applyActiveEditSession()
    application.processEvents()
    assert committed == [None]
    assert pixel_changes == []
    first = document.canvas.captureMaskExport(first_mask_id)
    second = document.canvas.captureMaskExport(second_mask_id)
    source = document.generation_capture.capture(image_ids=(image_id,), mask_ids=())
    assert first is not None and second is not None and source is not None
    assert source.images[image_id].image.size() == QSize(200, 100)
    assert first.image.size() == second.image.size() == QSize(200, 100)
    assert first.image.pixelColor(110, 50).value() > 0
    assert second.image.pixelColor(110, 50).value() == 0
    assert first.image.pixelColor(130, 50).value() == 0
    assert second.image.pixelColor(130, 50).value() > 0

    archive = tmp_path / "resized-input.ccanvas"
    assert document.editable_persistence.save_editable_document(archive) == (image_id,)
    restored = InputCanvasDocument(features=("mask",))
    assert restored.editable_persistence.restore_editable_document(archive) == (
        image_id,
    )
    assert restored.set_current_image_id(image_id)
    restored_first = restored.canvas.captureMaskExport(first_mask_id)
    restored_second = restored.canvas.captureMaskExport(second_mask_id)
    assert restored_first is not None and restored_second is not None
    assert restored_first.image.pixelColor(110, 50).value() > 0
    assert restored_second.image.pixelColor(110, 50).value() == 0
    assert restored_first.image.pixelColor(130, 50).value() == 0
    assert restored_second.image.pixelColor(130, 50).value() > 0
    restored.close()

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
    application.processEvents()
    assert document.canvas.undoSceneEdit()
    application.processEvents()
    assert committed == [None, None]
    policy.close()
    document.close()


def test_policy_restores_every_visited_image_after_context_switch() -> None:
    """Leaving the mode should restore masks visited across composition changes."""

    application = _application()
    document = InputCanvasDocument(features=("mask",))
    first_image_id = uuid4()
    second_image_id = uuid4()
    first_mask_id = _create_restricted_mask(document, first_image_id)
    second_mask_id = _create_restricted_mask(document, second_image_id)
    assert document.set_current_image_id(first_image_id)
    policy = InputSharedEdgeResizePolicy(document.canvas, parent=document.canvas)

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE)
    application.processEvents()
    assert _mask_movable(document, first_mask_id)
    assert document.set_current_image_id(second_image_id)
    application.processEvents()
    assert _mask_movable(document, second_mask_id)

    assert document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
    application.processEvents()
    assert not _mask_movable(document, second_mask_id)
    assert document.set_current_image_id(first_image_id)
    application.processEvents()
    assert not _mask_movable(document, first_mask_id)
    policy.close()
    document.close()


def _application() -> QApplication:
    """Return the shared application required by CuteCanvas widgets."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _image() -> QImage:
    """Create one deterministic authored source raster."""

    image = QImage(24, 16, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("red"))
    return image


def _source_image() -> QImage:
    """Create the fixed authored image used to validate generation export."""

    image = QImage(200, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("red"))
    return image


def _save_mask(path: Path, coverage: QRect) -> Path:
    """Persist one deterministic rectangular grayscale mask."""

    image = QImage(200, 100, QImage.Format.Format_Grayscale8)
    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(coverage, QColor("white"))
    painter.end()
    assert image.save(str(path))
    return path


def _panel_point(canvas: CuteCanvas, x: float, y: float) -> QPoint:
    """Map one scene position to the mounted widget for pointer probing."""

    panel_rect = canvas.sceneToPanelRect(QRectF(x, y, 1.0, 1.0))
    assert panel_rect is not None
    return panel_rect.center().toPoint()


def _create_restricted_mask(
    document: InputCanvasDocument,
    image_id: UUID,
) -> UUID:
    """Create one mask whose normal policy intentionally forbids movement."""

    document.ensure_image_cached(image_id, _image(), None)
    assert document.set_current_image_id(image_id)
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    scene = document.canvas.currentScene()
    assert scene is not None
    layer = next(layer for layer in scene.layers if layer.source_id == mask_id)
    assert document.canvas.setLayerInteractionPolicy(
        scene.scene_id,
        layer.layer_id,
        LayerPolicy(selectable=True, pixel_editable=True),
    )
    return mask_id


def _mask_movable(document: InputCanvasDocument, mask_id: UUID) -> bool:
    """Return the active mask layer's current movement permission."""

    scene = document.canvas.currentScene()
    assert scene is not None
    return next(
        layer.interaction.movable
        for layer in scene.layers
        if layer.source_id == mask_id
    )
