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

"""Verify restored regional masks bind live previews during panel projection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from cutecanvas import PixelSelectionMode, VectorShapeKind
from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QWidget

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)
from substitute.presentation.regional.panel_initial_projection import (
    project_regional_panel_widget,
)
from tests.support.cutecanvas.input_document import InputDocumentFactory
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _image() -> QImage:
    """Return one opaque image fixture for a restored Input document."""

    image = QImage(160, 120, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("black"))
    return image


def test_restored_regional_mask_rows_bind_previews_when_first_projected(
    tmp_path: Path,
    input_document_factory: InputDocumentFactory,
) -> None:
    """Restored ordered masks must mount live previews without selection input."""

    archive = tmp_path / "regional-input.ccanvas"
    image_id = uuid4()
    source = input_document_factory()
    source.ensure_image_cached(image_id, _image(), None)
    first_mask_id = source.create_blank_mask(image_id, QSize(160, 120))
    second_mask_id = source.create_blank_mask(image_id, QSize(160, 120))
    assert first_mask_id is not None
    assert second_mask_id is not None
    source.editable_persistence.save_editable_document(archive)
    source.close()

    restored = input_document_factory()
    panel = QWidget()
    editor = RegionalMaskBatchEditor(
        cube_alias="Region",
        node_name="masks",
        values=[],
        parent=panel,
    )
    workflow = WorkflowState()
    try:
        assert restored.editable_persistence.restore_editable_document(archive) == (
            image_id,
        )
        collection = workflow.canvas.ensure_regional_mask_collection(
            ("Region", "masks")
        )
        first = collection.add_region(image_id, mask_id=first_mask_id)
        collection.add_region(image_id, mask_id=second_mask_id)
        collection.select(first.region_id)
        coordinator = InputNodePreviewCoordinator(bindings=restored.preview_bindings)
        panel.mainwindow = SimpleNamespace(  # type: ignore[attr-defined]
            editor_panels={"workflow": panel},
            workflow_session_service=SimpleNamespace(workflows={"workflow": workflow}),
            input_node_preview_coordinator=coordinator,
        )

        assert project_regional_panel_widget(
            editor,
            panel,
            cube_alias="Region",
            node_name="masks",
        )
        first_preview = editor.live_preview(0)
        second_preview = editor.live_preview(1)
        assert isinstance(first_preview, InputNodePreviewWidget)
        assert isinstance(second_preview, InputNodePreviewWidget)
        first_binding = restored.preview_bindings.mask(image_id, first_mask_id)
        second_binding = restored.preview_bindings.mask(image_id, second_mask_id)
        assert first_binding is not None
        assert second_binding is not None
        assert first_preview.binding.identity == first_binding.identity
        assert second_preview.binding.identity == second_binding.identity
    finally:
        panel.close()
        destroy_qt_object(panel)
        restored.close()


def test_late_editor_rebuild_rebinds_restored_mask_previews(
    tmp_path: Path,
    input_document_factory: InputDocumentFactory,
) -> None:
    """Replacing provisional rows must not hide or detach restored masks."""

    archive = tmp_path / "late-regional-input.ccanvas"
    image_id = uuid4()
    source = input_document_factory()
    source.ensure_image_cached(image_id, _image(), None)
    first_mask_id = source.create_blank_mask(image_id, QSize(160, 120))
    second_mask_id = source.create_blank_mask(image_id, QSize(160, 120))
    assert first_mask_id is not None
    assert second_mask_id is not None
    source.editable_persistence.save_editable_document(archive)
    source.close()

    restored = input_document_factory()
    panel = QWidget()
    workflow = WorkflowState()
    try:
        assert restored.editable_persistence.restore_editable_document(archive) == (
            image_id,
        )
        collection = workflow.canvas.ensure_regional_mask_collection(
            ("Region", "masks")
        )
        first = collection.add_region(image_id, mask_id=first_mask_id)
        collection.add_region(image_id, mask_id=second_mask_id)
        collection.select(first.region_id)
        coordinator = InputNodePreviewCoordinator(bindings=restored.preview_bindings)
        panel.mainwindow = SimpleNamespace(  # type: ignore[attr-defined]
            editor_panels={"workflow": panel},
            workflow_session_service=SimpleNamespace(workflows={"workflow": workflow}),
            input_node_preview_coordinator=coordinator,
        )
        provisional = RegionalMaskBatchEditor(
            cube_alias="Region",
            node_name="masks",
            values=[],
            parent=panel,
        )
        assert project_regional_panel_widget(
            provisional,
            panel,
            cube_alias="Region",
            node_name="masks",
        )
        assert isinstance(provisional.live_preview(0), InputNodePreviewWidget)
        destroy_qt_object(provisional)

        canonical = RegionalMaskBatchEditor(
            cube_alias="Region",
            node_name="masks",
            values=[],
            parent=panel,
        )
        assert project_regional_panel_widget(
            canonical,
            panel,
            cube_alias="Region",
            node_name="masks",
        )

        assert isinstance(canonical.live_preview(0), InputNodePreviewWidget)
        assert isinstance(canonical.live_preview(1), InputNodePreviewWidget)
        assert tuple(entry.mask_id for entry in collection.entries) == (
            first_mask_id,
            second_mask_id,
        )
        assert restored.preview_bindings.mask(image_id, first_mask_id) is not None
        assert restored.preview_bindings.mask(image_id, second_mask_id) is not None
    finally:
        panel.close()
        destroy_qt_object(panel)
        restored.close()


def test_preview_binding_cannot_cross_workflow_panel_ownership(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Hostile panel switching must preserve each workflow's exact mask pixels."""

    document = input_document_factory()
    source_panel = QWidget()
    source_editor = RegionalMaskBatchEditor(
        cube_alias="Region",
        node_name="masks",
        values=["source.png"],
        parent=source_panel,
    )
    foreign_panel = QWidget()
    foreign_editor = RegionalMaskBatchEditor(
        cube_alias="Region",
        node_name="masks",
        values=["foreign.png"],
        parent=foreign_panel,
    )
    source_workflow = WorkflowState()
    foreign_workflow = WorkflowState()
    image_id = uuid4()
    try:
        assert document.ensure_image_cached(image_id, _image(), None)
        source_mask_id = document.create_blank_mask(image_id, QSize(160, 120))
        foreign_mask_id = document.create_blank_mask(image_id, QSize(160, 120))
        assert source_mask_id is not None
        assert foreign_mask_id is not None
        assert document.set_current_image_id(image_id)
        assert document.set_active_mask_id(source_mask_id)
        assert (
            document.canvas.addCoverageShape(
                VectorShapeKind.RECTANGLE,
                QRectF(0.0, 0.0, 80.0, 120.0),
                PixelSelectionMode.ADD,
            )
            is not None
        )
        assert document.set_active_mask_id(foreign_mask_id)
        assert (
            document.canvas.addCoverageShape(
                VectorShapeKind.RECTANGLE,
                QRectF(80.0, 0.0, 80.0, 120.0),
                PixelSelectionMode.ADD,
            )
            is not None
        )
        source_workflow.canvas.ensure_regional_mask_collection(
            ("Region", "masks")
        ).add_region(image_id, mask_id=source_mask_id)
        foreign_workflow.canvas.ensure_regional_mask_collection(
            ("Region", "masks")
        ).add_region(image_id, mask_id=foreign_mask_id)
        source_panel.mainwindow = SimpleNamespace(  # type: ignore[attr-defined]
            editor_panels={"source": source_panel},
            workflow_session_service=SimpleNamespace(
                workflows={"source": source_workflow}
            ),
        )
        foreign_panel.mainwindow = SimpleNamespace(  # type: ignore[attr-defined]
            editor_panels={"foreign": foreign_panel},
            workflow_session_service=SimpleNamespace(
                workflows={"foreign": foreign_workflow}
            ),
        )
        coordinator = InputNodePreviewCoordinator(bindings=document.preview_bindings)

        for _ in range(20):
            assert coordinator.bind_panel(source_panel) == frozenset(
                {("Region", "masks")}
            )
            assert coordinator.bind_panel(foreign_panel) == frozenset(
                {("Region", "masks")}
            )
        source_preview = source_editor.live_preview(0)
        foreign_preview = foreign_editor.live_preview(0)
        assert isinstance(source_preview, InputNodePreviewWidget)
        assert isinstance(foreign_preview, InputNodePreviewWidget)
        source_binding = document.preview_bindings.mask(image_id, source_mask_id)
        foreign_binding = document.preview_bindings.mask(image_id, foreign_mask_id)
        assert source_binding is not None
        assert foreign_binding is not None
        assert source_preview.binding.identity == source_binding.identity
        assert foreign_preview.binding.identity == foreign_binding.identity
        source_panel.show()
        foreign_panel.show()

        def preview_sample_values() -> tuple[int, int, int, int]:
            """Return left/right luminance from both workflow-owned previews."""

            source_pixels = source_preview.canvas.grab().toImage()
            foreign_pixels = foreign_preview.canvas.grab().toImage()
            y = source_pixels.height() // 2
            source_left = source_pixels.pixelColor(source_pixels.width() // 4, y)
            source_right = source_pixels.pixelColor(source_pixels.width() * 3 // 4, y)
            y = foreign_pixels.height() // 2
            foreign_left = foreign_pixels.pixelColor(foreign_pixels.width() // 4, y)
            foreign_right = foreign_pixels.pixelColor(
                foreign_pixels.width() * 3 // 4,
                y,
            )
            return (
                source_left.value(),
                source_right.value(),
                foreign_left.value(),
                foreign_right.value(),
            )

        def previews_match_owned_masks() -> bool:
            """Return whether both rendered thumbnails match their owner masks."""

            source_left, source_right, foreign_left, foreign_right = (
                preview_sample_values()
            )
            return source_left > source_right + 10 and foreign_right > foreign_left + 10

        wait_for_qt_condition(
            previews_match_owned_masks,
            state=preview_sample_values,
        )
    finally:
        source_panel.close()
        destroy_qt_object(source_panel)
        foreign_panel.close()
        destroy_qt_object(foreign_panel)
        document.close()


def test_materialization_refuses_a_panel_owned_by_another_workflow() -> None:
    """A late route change must not project materialized masks across workflows."""

    source_workflow = WorkflowState()
    foreign_workflow = WorkflowState()
    foreign_panel = QWidget()
    foreign_panel.mainwindow = SimpleNamespace(  # type: ignore[attr-defined]
        editor_panels={"foreign": foreign_panel},
        workflow_session_service=SimpleNamespace(
            workflows={"foreign": foreign_workflow}
        ),
    )
    bound_panels: list[QWidget] = []

    def bind_materialization(_result: object, *, panel: QWidget) -> frozenset[str]:
        """Record materialization attempts made against the foreign panel."""
        bound_panels.append(panel)
        return frozenset()

    preview_coordinator = SimpleNamespace(bind_materialization=bind_materialization)
    presenter = InputMaterializationPresenter(
        input_document=SimpleNamespace(),
        active_workflow=lambda: source_workflow,
        active_panel=lambda: foreign_panel,
        mask_color=lambda _index, _total: QColor("red"),
        refresh_scalar_mask=lambda *_args: None,
        refresh_ordered_mask=lambda _association_key: None,
        activate_mask=lambda _workflow, _mask_id: True,
        preview_coordinator=cast(Any, preview_coordinator),
    )

    presenter.apply(SimpleNamespace(mask_results=()))

    assert bound_panels == []
    destroy_qt_object(foreign_panel)
