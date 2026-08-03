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

"""Abuse live Input node previews through the real shared CuteCanvas document."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Callable
from uuid import UUID, uuid4

from cutecanvas import (
    CanvasViewportInteraction,
    PixelSelectionMode,
    VectorShapeKind,
)
from PySide6.QtCore import QCoreApplication, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
import pytest

from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
    MaskMaterializationResult,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker


def _image(color: str, width: int = 160, height: int = 120) -> QImage:
    """Return one opaque image fixture."""
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return the process QApplication used by the offscreen harness."""
    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _panel() -> tuple[QWidget, ImagePicker, MaskPicker]:
    """Mount production picker widgets under one offscreen panel."""
    panel = QWidget()
    layout = QVBoxLayout(panel)
    image_picker = ImagePicker(panel, thumbnail_size=192)
    image_picker.setProperty(
        "input_metadata",
        {
            "cube_alias": "cube",
            "node_name": "load_image",
            "key": "image",
        },
    )
    mask_picker = MaskPicker(
        cube_alias="cube",
        node_name="load_mask",
        parent=panel,
        thumbnail_size=192,
    )
    mask_picker.setProperty(
        "input_metadata",
        {
            "cube_alias": "cube",
            "node_name": "load_mask",
            "key": "image",
        },
    )
    layout.addWidget(image_picker)
    layout.addWidget(mask_picker)
    return panel, image_picker, mask_picker


def _result(image_id: UUID, mask_id: UUID) -> InputCanvasMaterializationResult:
    """Return one graph-identified image-plus-mask materialization."""
    return InputCanvasMaterializationResult(
        section_key="cube",
        surface_key="load_image",
        image_id=image_id,
        mask_results=(
            MaskMaterializationResult(
                association_key=("cube", "load_mask"),
                image_id=image_id,
                mask_id=mask_id,
                resolved_path=Path("never-read.png"),
                source="in_memory",
            ),
        ),
    )


def _center_color(preview: InputNodePreviewWidget) -> QColor:
    """Capture the center pixel of one mounted offscreen preview."""
    image = preview.canvas.grab().toImage()
    return image.pixelColor(image.rect().center())


def _wait_until(predicate: Callable[[], bool], *, timeout: float = 2.0) -> None:
    """Process queued Qt work until one semantic condition holds or times out."""
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        _app().processEvents()
        if predicate():
            return
    raise AssertionError("timed out waiting for live preview pixels")


def test_live_node_previews_share_authority_and_survive_erratic_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live damage must render without full exports, rebinding, or stale pixels."""
    app = _app()
    document = InputCanvasDocument(features=("mask",))
    panel, image_picker, mask_picker = _panel()
    panel.resize(460, 900)
    panel.show()
    coordinator = InputNodePreviewCoordinator(
        bindings=document.preview_bindings,
        active_panel=lambda: panel,
    )
    first_image_id = uuid4()
    second_image_id = uuid4()
    try:
        assert (
            document.ensure_image_cached(
                first_image_id,
                _image("royalblue"),
                None,
            ).value
            == "added"
        )
        first_mask_id = document.create_blank_mask(
            first_image_id,
            QSize(160, 120),
        )
        assert first_mask_id is not None
        assert coordinator.bind_materialization(
            _result(first_image_id, first_mask_id)
        ) == frozenset({("cube", "load_mask")})
        app.processEvents()

        image_preview = image_picker.live_preview()
        mask_preview = mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)
        assert image_preview.canvas.documentRuntime() is document.runtime
        assert mask_preview.canvas.documentRuntime() is document.runtime
        image_spec = image_preview.canvas.viewportSpec()
        mask_spec = mask_preview.canvas.viewportSpec()
        assert image_spec is not None
        assert mask_spec is not None
        assert image_spec.viewport_id != mask_spec.viewport_id
        image_color = _center_color(image_preview)
        assert image_color.blue() > image_color.red()
        empty_mask_color = _center_color(mask_preview)
        app.processEvents()
        preview_changes = QSignalSpy(mask_preview.canvas.sceneChanged)

        def reject_full_export(*_args: object, **_kwargs: object) -> None:
            """Fail if interactive preview damage enters an export pipeline."""

            raise AssertionError("live Input preview attempted a full document export")

        monkeypatch.setattr(document, "export_mask_image", reject_full_export)

        document.set_active_mask_id(first_mask_id)
        assert (
            document.canvas.addCoverageShape(
                VectorShapeKind.RECTANGLE,
                QRectF(20.0, 15.0, 120.0, 90.0),
                PixelSelectionMode.ADD,
            )
            is not None
        )
        _wait_until(lambda: preview_changes.count() > 0)
        _wait_until(
            lambda: _center_color(mask_preview).value() > empty_mask_color.value()
        )
        painted_mask_color = _center_color(mask_preview)
        assert painted_mask_color.value() > empty_mask_color.value()
        assert painted_mask_color.red() == painted_mask_color.green()
        assert painted_mask_color.green() == painted_mask_color.blue()

        for width, height in (
            (97, 420),
            (700, 103),
            (111, 109),
            (520, 480),
            (180, 640),
        ):
            image_preview.resize(width, height)
            mask_preview.resize(height, width)
            app.processEvents()
            image_spec = image_preview.canvas.viewportSpec()
            mask_spec = mask_preview.canvas.viewportSpec()
            assert image_spec is not None
            assert mask_spec is not None
            assert image_spec.interaction is CanvasViewportInteraction.FIT_ONLY
            assert mask_spec.interaction is CanvasViewportInteraction.FIT_ONLY

        assert (
            document.ensure_image_cached(
                second_image_id,
                _image("darkorange", 320, 90),
                None,
            ).value
            == "added"
        )
        second_mask_id = document.create_blank_mask(
            second_image_id,
            QSize(320, 90),
        )
        assert second_mask_id is not None
        for _ in range(20):
            coordinator.bind_materialization(_result(second_image_id, second_mask_id))
            coordinator.bind_materialization(_result(first_image_id, first_mask_id))
        coordinator.bind_materialization(_result(second_image_id, second_mask_id))
        app.processEvents()

        replacement_image = image_picker.live_preview()
        replacement_mask = mask_picker.live_preview()
        assert isinstance(replacement_image, InputNodePreviewWidget)
        assert isinstance(replacement_mask, InputNodePreviewWidget)
        assert replacement_image.binding.source != image_preview.binding.source
        assert replacement_mask.binding.source != mask_preview.binding.source
        assert replacement_image.canvas.documentRuntime() is document.runtime
        assert replacement_mask.canvas.documentRuntime() is document.runtime

        panel.close()
        panel.deleteLater()
        app.processEvents()
        assert document.set_current_image_id(first_image_id)
        assert document.set_active_mask_id(first_mask_id)
        assert (
            document.canvas.addCoverageShape(
                VectorShapeKind.ELLIPSE,
                QRectF(10.0, 10.0, 40.0, 40.0),
                PixelSelectionMode.ADD,
            )
            is not None
        )
        app.processEvents()
    finally:
        panel.close()
        document.close()


def test_large_raster_mask_preview_renders_authoritative_coverage(
    tmp_path: Path,
) -> None:
    """Large file-backed masks must render through the sampled hybrid path."""
    _app()
    document = InputCanvasDocument(features=("mask",))
    panel, _image_picker, mask_picker = _panel()
    panel.resize(460, 900)
    panel.show()
    image_id = uuid4()
    mask_path = tmp_path / "large-mask.png"
    mask = QImage(1920, 2688, QImage.Format.Format_Grayscale8)
    mask.fill(0)
    painter = QPainter(mask)
    painter.fillRect(QRect(240, 320, 1440, 2048), QColor("white"))
    painter.end()
    assert mask.save(str(mask_path))
    try:
        assert (
            document.ensure_image_cached(
                image_id,
                _image("black", 1920, 2688),
                None,
            ).value
            == "added"
        )
        mask_id = document.load_mask_from_file(image_id, mask_path)
        assert mask_id is not None
        coordinator = InputNodePreviewCoordinator(
            bindings=document.preview_bindings,
            active_panel=lambda: panel,
        )
        assert coordinator.bind_materialization(_result(image_id, mask_id)) == (
            frozenset({("cube", "load_mask")})
        )
        preview = mask_picker.live_preview()
        assert isinstance(preview, InputNodePreviewWidget)

        _wait_until(lambda: _center_color(preview).value() > 240)
        assert _center_color(preview).red() == 255
    finally:
        panel.close()
        document.close()


def test_restored_workflow_binds_once_and_path_refresh_preserves_live_previews(
    tmp_path: Path,
) -> None:
    """Late panel projection and generation refresh must retain one presentation."""
    app = _app()
    document = InputCanvasDocument(features=("mask",))
    active_panel: list[QWidget | None] = [None]
    coordinator = InputNodePreviewCoordinator(
        bindings=document.preview_bindings,
        active_panel=lambda: active_panel[0],
    )
    image_id = uuid4()
    image = _image("royalblue")
    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    assert image.save(str(image_path))
    mask = QImage(160, 120, QImage.Format.Format_Grayscale8)
    mask.fill(255)
    assert mask.save(str(mask_path))
    workflow = WorkflowState()
    try:
        assert (
            document.ensure_image_cached(image_id, image, image_path).value == "added"
        )
        mask_id = document.load_mask_from_file(image_id, mask_path)
        assert mask_id is not None
        workflow.canvas.bind_image("cube:load_image", image_id)
        workflow.canvas.bind_mask(("cube", "load_mask"), mask_id, image_id)

        assert coordinator.bind_workflow(workflow) == frozenset()
        panel, image_picker, mask_picker = _panel()
        active_panel[0] = panel
        panel.resize(460, 900)
        panel.show()

        assert coordinator.bind_workflow(workflow) == frozenset({("cube", "load_mask")})
        image_preview = image_picker.live_preview()
        mask_preview = mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)
        assert image_preview.sizeHint() == QSize(192, 144)
        assert mask_preview.sizeHint() == QSize(192, 144)
        mask_clicks = QSignalSpy(mask_picker.clicked)

        image_picker.set_thumbnail(str(image_path))
        mask_picker.refresh_mask_path(str(mask_path))
        app.processEvents()

        assert image_picker.live_preview() is image_preview
        assert mask_picker.live_preview() is mask_preview
        assert image_preview.sizeHint() == QSize(192, 144)
        assert mask_preview.sizeHint() == QSize(192, 144)
        QTest.mouseClick(mask_picker.preview_surface, Qt.MouseButton.LeftButton)
        assert mask_clicks.count() == 1
        assert coordinator.bind_workflow(workflow) == frozenset({("cube", "load_mask")})
        assert image_picker.live_preview() is image_preview
        assert mask_picker.live_preview() is mask_preview
    finally:
        active_panel_widget = active_panel[0]
        if active_panel_widget is not None:
            active_panel_widget.close()
        document.close()


def test_live_picker_content_uses_shared_rounded_highlight_surface() -> None:
    """Live image and mask pixels must retain picker chrome and passive input policy."""

    app = _app()
    document = InputCanvasDocument(features=("mask",))
    panel, image_picker, mask_picker = _panel()
    panel.resize(460, 900)
    panel.show()
    image_id = uuid4()
    try:
        assert document.ensure_image_cached(image_id, _image("cyan"), None)
        mask_id = document.create_blank_mask(image_id, QSize(160, 120))
        assert mask_id is not None
        coordinator = InputNodePreviewCoordinator(
            bindings=document.preview_bindings,
            active_panel=lambda: panel,
        )
        coordinator.bind_materialization(_result(image_id, mask_id))
        app.processEvents()

        for picker in (image_picker, mask_picker):
            preview = picker.live_preview()
            assert isinstance(preview, InputNodePreviewWidget)
            assert preview.testAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            surface = picker.preview_surface
            before = surface.grab().toImage()
            QTest.mouseMove(surface, surface.rect().center())
            app.processEvents()
            after = surface.grab().toImage()
            assert after != before
            assert surface.live_content() is preview
            assert surface.size() == preview.size() + QSize(12, 12)
            assert preview.canvas.viewportCornerRadius() == 8.0
            assert surface.graphicsEffect() is None
            assert all(
                child.graphicsEffect() is None
                for child in surface.findChildren(QWidget)
            )
    finally:
        panel.close()
        document.close()
