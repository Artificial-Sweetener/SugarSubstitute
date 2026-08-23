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

"""Verify Input picker interactions through production shell wiring."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_node_preview_widget import (
    InputNodePreviewWidget,
)
from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from substitute.presentation.editor.panel.widgets.fields.load_image import ImagePicker
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)


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
        harness.wait_until(
            lambda: harness.workflow.canvas.input_image_uuid == harness.image_id
        )
        assert harness.workflow.canvas.input_image_uuid == harness.image_id
        harness.wait_until(lambda: _focus_belongs_to(harness.input_canvas))
        assert _focus_belongs_to(harness.input_canvas)

        assert harness.shell.input_canvas_tool_controller.request_tool(
            InputCanvasToolId.MASK_RECTANGLE
        )
        harness.shell.editor_panel.setFocus()
        QTest.mouseClick(harness.mask_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.wait_until(
            lambda: (
                harness.workflow.canvas.input_image_uuid == harness.image_id
                and harness.workflow.canvas.active_input_mask_uuid == harness.mask_id
                and harness.shell.input_canvas_tool_controller.palette.active_tool_id
                == InputCanvasToolId.MASK_RECTANGLE
            )
        )
        assert harness.workflow.canvas.input_image_uuid == harness.image_id
        assert harness.workflow.canvas.active_input_mask_uuid == harness.mask_id
        assert (
            harness.shell.input_canvas_tool_controller.palette.active_tool_id
            == InputCanvasToolId.MASK_RECTANGLE
        )
        harness.wait_until(lambda: _focus_belongs_to(harness.input_canvas))
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
        harness.shell.editor_panel.setFocus()
        QTest.mouseClick(first_image_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.wait_until(
            lambda: (
                workflow.canvas.input_image_uuid == first_image_id
                and workflow.canvas.active_input_mask_uuid == first_mask_id
            )
        )
        assert workflow.canvas.input_image_uuid == first_image_id
        assert workflow.canvas.active_input_mask_uuid == first_mask_id
        harness.wait_until(lambda: _focus_belongs_to(harness.input_canvas))
        assert _focus_belongs_to(harness.input_canvas)

        assert harness.shell.input_canvas_tool_controller.request_tool(
            InputCanvasToolId.MOVE
        )
        second_mask_picker = cast(
            MaskPicker,
            harness.picker(MaskPicker, second_alias, harness.MASK_NODE),
        )
        harness.shell.editor_panel.setFocus()
        QTest.mouseClick(second_mask_picker.preview_surface, Qt.MouseButton.LeftButton)
        harness.wait_until(
            lambda: (
                workflow.canvas.input_image_uuid == second_image_id
                and workflow.canvas.active_input_mask_uuid == second_mask_id
                and harness.shell.input_canvas_tool_controller.palette.active_tool_id
                == InputCanvasToolId.MOVE
            )
        )
        assert workflow.canvas.input_image_uuid == second_image_id
        assert workflow.canvas.active_input_mask_uuid == second_mask_id
        assert (
            harness.shell.input_canvas_tool_controller.palette.active_tool_id
            == InputCanvasToolId.MOVE
        )
        harness.wait_until(lambda: _focus_belongs_to(harness.input_canvas))
        assert _focus_belongs_to(harness.input_canvas)
    finally:
        harness.close()


def _focus_belongs_to(widget: QWidget) -> bool:
    """Return whether Qt keyboard focus belongs to the widget subtree."""

    focus = QApplication.focusWidget()
    return focus is widget or (focus is not None and widget.isAncestorOf(focus))
