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

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)


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
        image_product = (
            tmp_path / "projects" / "Input Editor" / "input_images" / image_value
        )
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
