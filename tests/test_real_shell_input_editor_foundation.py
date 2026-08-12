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

"""Abuse the complete Input editor foundation through production shell wiring."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.generation import ComfyAssetStagingService
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingPlanService,
)
from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    WorkflowSnapshot,
    WorkspaceSnapshot,
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from substitute.presentation.shell.restore_projection_controller import (
    restore_projection_controller_for,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    active_workflow_surface_refresher_for,
)
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)


class _RecordingAssetStager(ComfyAssetStager):
    """Record exact generation product paths crossing the Comfy boundary."""

    def __init__(self) -> None:
        """Initialize an empty staging call record."""
        self.paths: list[Path] = []

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Record one authorized source and return a deterministic execution value."""
        _ = content_hash, node_class
        self.paths.append(source_path)
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="authorized",
        )


def test_harness_close_finalizes_input_document_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness teardown must settle native document work before process exit."""

    harness = RealShellInputEditorHarness(tmp_path)
    runtime = harness.input_canvas.document.runtime
    original_close = runtime.close
    close_calls = 0

    def record_close() -> None:
        """Record and preserve the real runtime teardown."""

        nonlocal close_calls
        close_calls += 1
        original_close()

    monkeypatch.setattr(runtime, "close", record_close)
    harness.close()
    harness.close()

    assert close_calls == 1


def test_real_shell_input_editor_survives_erratic_full_lifecycle(
    tmp_path: Path,
) -> None:
    """Live previews, tools, persistence, and generation must share one authority."""
    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("magenta"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        image_preview = harness.image_picker.live_preview()
        mask_preview = harness.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)
        image_spec = image_preview.canvas.viewportSpec()
        mask_spec = mask_preview.canvas.viewportSpec()
        assert image_spec is not None
        assert mask_spec is not None
        assert image_spec.viewport_id != mask_spec.viewport_id

        palette = harness.shell.input_canvas_tool_controller.palette
        for tool_id in (
            InputCanvasToolId.PAN_ZOOM,
            InputCanvasToolId.BRUSH,
            InputCanvasToolId.MOVE,
            InputCanvasToolId.MASK_RECTANGLE,
        ) * 5:
            assert harness.shell.input_canvas_tool_controller.request_tool(tool_id)
        for width, height in (
            (18, 420),
            (640, 23),
            (91, 91),
            (720, 360),
            (31, 511),
        ) * 4:
            image_preview.resize(width, height)
            mask_preview.resize(height, width)
            harness.process_events(2)
        assert palette.active_tool_id == InputCanvasToolId.MASK_RECTANGLE

        harness.add_rectangle(QRectF(31.0, 27.0, 117.0, 89.0))
        before_generation = harness.input_canvas.document.export_mask_image(
            harness.mask_id
        )
        assert isinstance(before_generation, QImage)
        assert before_generation.pixelColor(64, 64).red() > 240
        assert before_generation.pixelColor(2, 2).red() == 0

        prepared = harness.prepare_generation()
        image_value = _node_image_value(prepared, harness.IMAGE_NODE)
        mask_value = _node_image_value(prepared, harness.MASK_NODE)
        image_product = tmp_path / "projects" / "Input Editor" / image_value
        mask_product = tmp_path / "projects" / "Input Editor" / "masks" / mask_value
        submitted_mask = QImage(str(mask_product))
        assert image_product.is_file()
        assert mask_product.is_file()
        assert submitted_mask == before_generation
        duplicate = harness.prepare_generation()
        assert _node_image_value(duplicate, harness.IMAGE_NODE) == image_value
        assert _node_image_value(duplicate, harness.MASK_NODE) == mask_value
        assert QImage(str(mask_product)) == submitted_mask

        harness.add_rectangle(QRectF(170.0, 140.0, 60.0, 45.0))
        assert QImage(str(mask_product)) == submitted_mask
        assert (
            harness.input_canvas.document.export_mask_image(harness.mask_id)
            != submitted_mask
        )

        archive = harness.save_editable_document()
        assert archive.is_file() and archive.stat().st_size > 0
        restored = InputCanvasDocument(features=("mask",))
        try:
            restored_ids = restored.editable_persistence.restore_editable_document(
                archive
            )
            assert harness.image_id in restored_ids
            assert restored.contains_mask(harness.image_id, harness.mask_id)
            assert restored.export_mask_image(harness.mask_id) == (
                harness.input_canvas.document.export_mask_image(harness.mask_id)
            )
        finally:
            restored.close()

        image_preview.close()
        mask_preview.close()
        harness.process_events(4)
        harness.add_rectangle(QRectF(5.0, 5.0, 8.0, 8.0))
        assert harness.input_canvas.document.contains_mask(
            harness.image_id,
            harness.mask_id,
        )
    finally:
        harness.close()


def test_brand_new_inpaint_workflow_renders_live_node_previews_immediately(
    tmp_path: Path,
) -> None:
    """Render selected image and painted mask pixels in the production node cards."""
    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        image_preview = harness.image_picker.live_preview()
        mask_preview = harness.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)
        expected_preview_size = image_preview.sizeHint()
        assert image_preview.size() == expected_preview_size
        assert mask_preview.size() == expected_preview_size
        image_pixels = image_preview.grab().toImage()
        image_center = image_pixels.pixelColor(image_pixels.rect().center())
        assert image_center.green() > image_center.red()
        assert image_center.blue() > image_center.red()

        harness.add_rectangle(QRectF(32.0, 24.0, 193.0, 145.0))
        harness.wait_until(
            lambda: (
                mask_preview.grab()
                .toImage()
                .pixelColor(mask_preview.rect().center())
                .alpha()
                > 0
            )
        )
        mask_pixels = mask_preview.grab().toImage()
        mask_center = mask_pixels.pixelColor(mask_pixels.rect().center())
        assert mask_center.alpha() > 0
        assert mask_center.value() > 0
        image_clicks = QSignalSpy(harness.image_picker.imageClicked)
        mask_clicks = QSignalSpy(harness.mask_picker.clicked)
        QTest.mouseClick(
            harness.image_picker.preview_surface,
            Qt.MouseButton.LeftButton,
        )
        QTest.mouseClick(
            harness.mask_picker.preview_surface,
            Qt.MouseButton.LeftButton,
        )
        assert image_clicks.count() == 1
        assert mask_clicks.count() == 1
    finally:
        harness.close()


def test_brand_new_inpaint_workflow_materializes_mask_for_long_source_name(
    tmp_path: Path,
) -> None:
    """Long legal source names must still produce a writable editable mask."""

    source_path = tmp_path / f"{'descriptive_source_' * 9}.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)

        mask_filename = _node_image_value(harness.workflow, harness.MASK_NODE)
        mask_path = tmp_path / "projects" / "Input Editor" / "masks" / mask_filename
        assert mask_path.is_file()
        assert len(mask_path.name) <= 224
        assert harness.input_canvas.document.contains_mask(
            harness.image_id,
            harness.mask_id,
        )

        harness.add_brush_dab(QPoint(200, 150), brush_size=80)
        mask = harness.input_canvas.document.export_mask_image(harness.mask_id)
        assert isinstance(mask, QImage)
        content_bounds = _nonzero_red_bounds(mask)
        assert content_bounds is not None
        assert abs(content_bounds.width() - content_bounds.height()) <= 1
    finally:
        harness.close()


def test_real_node_file_replacement_preserves_document_entry_identities(
    tmp_path: Path,
) -> None:
    """Replacing node pixels must retain its image and mask document entries."""

    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    make_source_image(first_path, QColor("cyan"), width=257, height=193)
    make_source_image(second_path, QColor("magenta"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(first_path)
        image_id = harness.image_id
        mask_id = harness.mask_id
        image_preview = harness.image_picker.live_preview()
        mask_preview = harness.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)

        harness.add_rectangle(QRectF(31.0, 27.0, 117.0, 89.0))
        mask_before = harness.input_canvas.document.export_mask_image(mask_id)
        assert isinstance(mask_before, QImage)

        harness.select_image(second_path)

        assert harness.image_id == image_id
        assert harness.mask_id == mask_id
        mask_entry = harness.workflow.canvas.mask_entry_for_id(mask_id)
        assert mask_entry is not None and mask_entry.image_id == image_id
        assert harness.input_canvas.document.contains_mask(image_id, mask_id)
        assert harness.input_canvas.document.export_mask_image(mask_id) == mask_before
        assert harness.image_picker.live_preview() is image_preview
        assert harness.mask_picker.live_preview() is mask_preview
        assert "second.png" in harness.image_picker.caption.text()

        harness.wait_until(
            lambda: (
                image_preview.grab()
                .toImage()
                .pixelColor(image_preview.rect().center())
                .red()
                > 180
            )
        )
        center = (
            image_preview.grab().toImage().pixelColor(image_preview.rect().center())
        )
        assert center.red() > center.green()
        assert center.blue() > center.green()
    finally:
        harness.close()


def test_real_mask_file_replacement_preserves_document_entry_identity(
    tmp_path: Path,
) -> None:
    """Loading a mask file must replace pixels on the node-owned mask entry."""

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    make_source_image(image_path, QColor("cyan"), width=257, height=193)
    mask = QImage(257, 193, QImage.Format.Format_Grayscale8)
    mask.fill(255)
    assert mask.save(str(mask_path))
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(image_path)
        image_id = harness.image_id
        mask_id = harness.mask_id
        preview = harness.mask_picker.live_preview()
        assert isinstance(preview, InputNodePreviewWidget)

        harness.mask_picker.set_mask_path(str(mask_path))
        harness.mask_picker.maskSelected.emit(
            harness.CUBE_ALIAS,
            harness.MASK_NODE,
            str(mask_path),
        )
        harness.process_events(12)

        assert harness.image_id == image_id
        assert harness.mask_id == mask_id
        assert harness.mask_picker.live_preview() is preview
        replaced = harness.input_canvas.document.export_mask_image(mask_id)
        assert isinstance(replaced, QImage)
        assert replaced.pixelColor(replaced.rect().center()).red() == 255
    finally:
        harness.close()


def test_empty_mask_entry_round_trip_mounts_real_node_preview_before_generation(
    tmp_path: Path,
) -> None:
    """Cache restore must present an existing empty mask entry without rebuilding it."""

    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    source = RealShellInputEditorHarness(tmp_path / "source")
    restored: RealShellInputEditorHarness | None = None
    try:
        source.select_image(source_path)
        image_id = source.image_id
        mask_id = source.mask_id
        archive = source.save_editable_document()
        snapshot = WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(
                WorkflowSnapshot(
                    workflow_id=source.WORKFLOW_ID,
                    tab_label="Input Editor",
                    workflow=source.workflow,
                ),
            ),
            tab_order=(source.WORKFLOW_ID,),
            active_route=source.WORKFLOW_ID,
            active_workflow_id=source.WORKFLOW_ID,
        )
        cached = workspace_snapshot_from_json(workspace_snapshot_to_json(snapshot))
        restored_workflow = cached.workflows[0].workflow

        source.close()
        restored = RealShellInputEditorHarness(
            tmp_path / "restored",
            workflow=restored_workflow,
        )
        restored_ids = restored.input_canvas.document.editable_persistence.restore_editable_document(
            archive
        )
        assert image_id in restored_ids
        assert restored.input_canvas.document.contains_mask(image_id, mask_id)

        projection_completed: list[bool] = []
        active_workflow_surface_refresher_for(restored.shell)
        restore_projection_controller_for(
            restored.shell
        ).reconcile_active_workflow_for_restore_projection(
            force_refresh=True,
            on_complete=lambda: projection_completed.append(True),
        )
        restored.wait_until(lambda: projection_completed == [True])

        image_preview = restored.image_picker.live_preview()
        mask_preview = restored.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)
        assert restored.image_id == image_id
        assert restored.mask_id == mask_id
        empty_mask = restored.input_canvas.document.export_mask_image(mask_id)
        assert isinstance(empty_mask, QImage)
        assert empty_mask.pixelColor(empty_mask.rect().center()).red() == 0
    finally:
        if restored is not None:
            restored.close()
        else:
            source.close()


def test_real_widgets_stage_exact_input_products_without_losing_live_preview(
    tmp_path: Path,
) -> None:
    """Real picker selection, capture, and staging must share project asset identity."""
    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        image_preview = harness.image_picker.live_preview()
        mask_preview = harness.mask_picker.live_preview()
        assert isinstance(image_preview, InputNodePreviewWidget)
        assert isinstance(mask_preview, InputNodePreviewWidget)

        prepared = harness.prepare_generation()
        image_value = _node_image_value(prepared, harness.IMAGE_NODE)
        mask_value = _node_image_value(prepared, harness.MASK_NODE)
        payload: JsonObject = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": str(image_value)},
                "_meta": {"title": f"{harness.CUBE_ALIAS}.{harness.IMAGE_NODE}"},
            },
            "2": {
                "class_type": "LoadImageMask",
                "inputs": {"image": str(mask_value), "channel": "alpha"},
                "_meta": {"title": f"{harness.CUBE_ALIAS}.{harness.MASK_NODE}"},
            },
        }
        stager = _RecordingAssetStager()
        staging_plan = InputAssetStagingPlanService(
            InputAssetEndpointService(
                WorkflowNodeDefinitionService(harness.shell.node_definition_gateway)
            ),
            harness.shell.graph_section_service,
        )
        staged = ComfyAssetStagingService.with_projects_dir(
            stager=stager,
            projects_dir=tmp_path / "projects",
            input_asset_staging_plan_service=staging_plan,
        ).stage_payload(
            workflow_payload=payload,
            workflow_id=harness.WORKFLOW_ID,
            workflow_name="Input Editor",
            workflow=prepared,
        )

        assert staged.failures == ()
        assert stager.paths == [
            tmp_path / "projects" / "Input Editor" / image_value,
            tmp_path / "projects" / "Input Editor" / "masks" / mask_value,
        ]
        assert harness.image_picker.live_preview() is image_preview
        assert harness.mask_picker.live_preview() is mask_preview
    finally:
        harness.close()


def test_real_picker_interactions_select_masks_without_changing_held_tool(
    tmp_path: Path,
) -> None:
    """Production picker signals must route editing to their authoritative subject."""

    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.shell.canvas_host.activate_canvas("Output", keyboard_focus=True)
        harness.select_image(source_path)

        assert harness.shell.canvas_host.is_canvas_visible("Input")
        image_preview = cast(
            InputNodePreviewWidget, harness.image_picker.live_preview()
        )
        mask_preview = cast(InputNodePreviewWidget, harness.mask_picker.live_preview())
        harness.shell.editor_panel.setFocus()
        QTest.mouseClick(
            harness.image_picker.preview_surface, Qt.MouseButton.LeftButton
        )
        harness.process_events(4)
        assert harness.workflow.canvas.input_image_uuid == harness.image_id
        assert _focus_belongs_to(harness.input_canvas)

        assert harness.shell.input_canvas_tool_controller.request_tool(
            InputCanvasToolId.MASK_RECTANGLE
        )
        harness.shell.editor_panel.setFocus()
        QTest.mouseClick(harness.mask_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.process_events(4)
        assert harness.workflow.canvas.input_image_uuid == harness.image_id
        assert harness.workflow.canvas.active_input_mask_uuid == harness.mask_id
        assert (
            harness.shell.input_canvas_tool_controller.palette.active_tool_id
            == InputCanvasToolId.MASK_RECTANGLE
        )
        assert _focus_belongs_to(harness.input_canvas)
        assert image_preview.binding.source != mask_preview.binding.source
    finally:
        harness.close()


def test_live_picker_preview_is_passive_to_editor_panel_wheel_scrolling(
    tmp_path: Path,
) -> None:
    """Wheel input over a live preview must remain owned by the editor scroll surface."""

    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("cyan"), width=257, height=193)
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        scroll = harness.shell.editor_panel.scroll
        assert isinstance(scroll, EditorPanelScrollSurface)
        scroll.resize(500, 320)
        scroll.refresh_metrics_now()
        harness.process_events(6)
        bar = scroll.verticalScrollBar()
        assert bar.maximum() > 0
        harness.add_rectangle(QRectF(24.0, 20.0, 80.0, 70.0))

        for picker in (harness.image_picker, harness.mask_picker):
            bar.setValue(0)
            preview = cast(InputNodePreviewWidget, picker.live_preview())
            before_spec = preview.canvas.viewportSpec()
            event = QWheelEvent(
                QPointF(20.0, 20.0),
                QPointF(picker.preview_surface.mapToGlobal(QPoint(20, 20))),
                QPoint(0, 0),
                QPoint(0, -120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.ScrollUpdate,
                False,
            )
            QApplication.sendEvent(picker.preview_surface, event)
            harness.process_events(4)

            assert bar.value() > 0
            assert preview.canvas.viewportSpec() == before_spec
    finally:
        harness.close()


def test_two_real_picker_pairs_route_exact_image_and_mask_identity(
    tmp_path: Path,
) -> None:
    """Each production picker must activate only its graph-owned editing subjects."""

    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    make_source_image(first_path, QColor("cyan"), width=257, height=193)
    make_source_image(second_path, QColor("magenta"), width=193, height=257)
    workflow = RealShellInputEditorHarness.two_pair_workflow()
    harness = RealShellInputEditorHarness(tmp_path, workflow=workflow)
    second_alias = "Face/Inpaint"
    try:
        harness.select_image_for(harness.CUBE_ALIAS, first_path)
        harness.select_image_for(second_alias, second_path)
        first_image_entry = workflow.canvas.image_entry(
            f"{harness.CUBE_ALIAS}:{harness.IMAGE_NODE}"
        )
        second_image_entry = workflow.canvas.image_entry(
            f"{second_alias}:{harness.IMAGE_NODE}"
        )
        first_mask_entry = workflow.canvas.mask_entry(
            (harness.CUBE_ALIAS, harness.MASK_NODE)
        )
        second_mask_entry = workflow.canvas.mask_entry(
            (second_alias, harness.MASK_NODE)
        )
        assert first_image_entry is not None
        assert second_image_entry is not None
        assert first_mask_entry is not None
        assert second_mask_entry is not None
        first_image_id = first_image_entry.image_id
        second_image_id = second_image_entry.image_id
        first_mask_id = first_mask_entry.mask_id
        second_mask_id = second_mask_entry.mask_id
        first_image_picker = cast(
            ImagePicker,
            harness.picker(ImagePicker, harness.CUBE_ALIAS, harness.IMAGE_NODE),
        )
        second_mask_picker = cast(
            MaskPicker,
            harness.picker(MaskPicker, second_alias, harness.MASK_NODE),
        )

        QTest.mouseClick(first_image_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.process_events(4)
        assert workflow.canvas.input_image_uuid == first_image_id
        assert workflow.canvas.active_input_mask_uuid == first_mask_id
        assert _focus_belongs_to(harness.input_canvas)

        assert harness.shell.input_canvas_tool_controller.request_tool(
            InputCanvasToolId.MOVE
        )
        QTest.mouseClick(second_mask_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.process_events(4)
        assert workflow.canvas.input_image_uuid == second_image_id
        assert workflow.canvas.active_input_mask_uuid == second_mask_id
        assert (
            harness.shell.input_canvas_tool_controller.palette.active_tool_id
            == InputCanvasToolId.MOVE
        )
        assert _focus_belongs_to(harness.input_canvas)
    finally:
        harness.close()


def _focus_belongs_to(widget: QWidget) -> bool:
    """Return whether Qt keyboard focus belongs to the widget subtree."""

    focus = QApplication.focusWidget()
    return focus is widget or (focus is not None and widget.isAncestorOf(focus))


def _nonzero_red_bounds(image: QImage) -> QRect | None:
    """Return exact occupied red-channel bounds for one exported coverage image."""

    occupied = [
        QPoint(x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).red() > 0
    ]
    if not occupied:
        return None
    left = min(point.x() for point in occupied)
    top = min(point.y() for point in occupied)
    right = max(point.x() for point in occupied)
    bottom = max(point.y() for point in occupied)
    return QRect(left, top, right - left + 1, bottom - top + 1)


def _node_image_value(workflow: WorkflowState, node_name: str) -> Path:
    """Return one generation product path from the execution-only graph copy."""
    nodes = cast(
        "dict[str, dict[str, dict[str, object]]]",
        workflow.cubes[RealShellInputEditorHarness.CUBE_ALIAS].buffer["nodes"],
    )
    value = nodes[node_name]["inputs"]["image"]
    if not isinstance(value, str):
        raise AssertionError(f"{node_name} did not receive a generation product")
    return Path(value)
