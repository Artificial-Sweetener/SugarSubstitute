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

"""Verify Input node-preview materialization through production shell wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QSignalSpy, QTest

from substitute.domain.workspace_snapshot import (
    WorkflowSnapshot,
    WorkspaceSnapshot,
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
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
