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

"""Verify Input editor runtime lifecycle through production shell wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)
from tests.support.cutecanvas.input_document import InputDocumentFactory
from tests.support.real_input_editor.generation import node_image_value


def test_harness_close_finalizes_input_document_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness teardown must settle native document work before process exit."""

    harness = RealShellInputEditorHarness(tmp_path)
    input_runtime = harness.input_canvas.document.runtime
    output_runtime = harness.shell.output_canvas.document.runtime
    original_input_close = input_runtime.close
    original_output_close = output_runtime.close
    runtime_owner = harness._base.canvas_execution_runtime_owner
    original_owner_shutdown = runtime_owner.shutdown
    close_calls = {"input": 0, "output": 0}
    shutdown_waits: list[bool] = []

    def record_input_close() -> None:
        """Record and preserve the real Input runtime teardown."""

        close_calls["input"] += 1
        original_input_close()

    def record_output_close() -> None:
        """Record and preserve the real Output runtime teardown."""

        close_calls["output"] += 1
        original_output_close()

    def record_owner_shutdown(*, wait: bool) -> None:
        """Record and preserve physical host execution teardown."""

        shutdown_waits.append(wait)
        original_owner_shutdown(wait=wait)

    monkeypatch.setattr(input_runtime, "close", record_input_close)
    monkeypatch.setattr(output_runtime, "close", record_output_close)
    monkeypatch.setattr(runtime_owner, "shutdown", record_owner_shutdown)
    harness.close()
    harness.close()

    assert close_calls == {"input": 1, "output": 1}
    assert input_runtime.execution_runtime is output_runtime.execution_runtime
    assert shutdown_waits == [True]


def test_harness_defers_unrelated_sam_native_runtime(tmp_path: Path) -> None:
    """Input-editor foundation tests must not start the unrelated SAM runtime."""

    harness = RealShellInputEditorHarness(tmp_path)
    try:
        assert cast(Any, harness.input_canvas.canvas).samManager() is None
    finally:
        harness.close()


def test_real_shell_input_editor_survives_erratic_full_lifecycle(
    tmp_path: Path,
    input_document_factory: InputDocumentFactory,
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
        image_value = node_image_value(prepared, harness.IMAGE_NODE)
        mask_value = node_image_value(prepared, harness.MASK_NODE)
        image_product = tmp_path / "projects" / "Input Editor" / image_value
        mask_product = tmp_path / "projects" / "Input Editor" / "masks" / mask_value
        submitted_mask = QImage(str(mask_product))
        assert image_product.is_file()
        assert mask_product.is_file()
        assert submitted_mask == before_generation
        duplicate = harness.prepare_generation()
        assert node_image_value(duplicate, harness.IMAGE_NODE) == image_value
        assert node_image_value(duplicate, harness.MASK_NODE) == mask_value
        assert QImage(str(mask_product)) == submitted_mask

        harness.add_rectangle(QRectF(170.0, 140.0, 60.0, 45.0))
        assert QImage(str(mask_product)) == submitted_mask
        assert (
            harness.input_canvas.document.export_mask_image(harness.mask_id)
            != submitted_mask
        )

        archive = harness.save_editable_document()
        assert archive.is_file() and archive.stat().st_size > 0
        restored = input_document_factory()
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
