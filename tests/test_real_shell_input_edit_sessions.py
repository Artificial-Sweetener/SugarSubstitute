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

"""Prove provisional Input edit sessions through the complete shell wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QSignalSpy, QTest
from cutecanvas import CuteCanvas, EditSessionKind, SceneSnapshot

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_edit_session_contextual_toolbar import (
    InputEditSessionContextualToolbarPage,
)
from tests.support.real_input_editor.harness import (
    RealShellInputEditorHarness,
    make_source_image,
)


def test_real_shell_shared_edge_session_owns_history_settlement_and_lifecycle(
    tmp_path: Path,
) -> None:
    """Edge previews must remain provisional until one visible resolution command."""

    source_path = tmp_path / "source.png"
    make_source_image(source_path, QColor("magenta"), width=200, height=100)
    left_path = _save_mask(tmp_path / "left.png", QRect(40, 20, 60, 60))
    right_path = _save_mask(tmp_path / "right.png", QRect(100, 20, 60, 60))
    harness = RealShellInputEditorHarness(tmp_path)
    try:
        harness.select_image(source_path)
        document = harness.input_canvas.document
        canvas = document.canvas
        left_id = document.load_mask_from_file(harness.image_id, left_path)
        right_id = document.load_mask_from_file(harness.image_id, right_path)
        assert left_id is not None and right_id is not None
        harness.input_canvas.resize(900, 620)
        harness.input_canvas.show()
        harness.process_events(12)

        tools = harness.shell.input_canvas_tool_controller
        assert tools.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
        harness.process_events(8)
        armed_page = harness.input_canvas.contextual_toolbar.page
        assert isinstance(armed_page, InputEditSessionContextualToolbarPage)
        assert armed_page.history_controls.undo_button.text() == ""
        assert armed_page.history_controls.redo_button.text() == ""
        assert armed_page.history_controls.undo_button.toolTip() == "Undo"
        assert armed_page.history_controls.redo_button.toolTip() == "Redo"
        assert armed_page.history_controls.undo_button.accessibleName() == "Undo"
        assert armed_page.history_controls.redo_button.accessibleName() == "Redo"
        assert not armed_page.history_controls.undo_button.icon().isNull()
        assert not armed_page.history_controls.redo_button.icon().isNull()
        assert (
            armed_page.history_controls.undo_button.width()
            == armed_page.history_controls.undo_button.height()
        )
        assert (
            armed_page.history_controls.redo_button.width()
            == armed_page.history_controls.redo_button.height()
        )
        assert not armed_page.history_controls.undo_button.isEnabled()
        assert not armed_page.history_controls.redo_button.isEnabled()
        assert not armed_page.apply_button.isEnabled()
        assert armed_page.cancel_button.isEnabled()
        scene = canvas.currentScene()
        assert scene is not None
        projected_scene = canvas.sceneToPanelRect(scene.bounds)
        assert projected_scene is not None
        assert (
            harness.input_canvas.contextual_toolbar.geometry().top()
            > projected_scene.toAlignedRect().bottom()
        )
        QTest.mouseClick(armed_page.cancel_button, Qt.MouseButton.LeftButton)
        harness.process_events(10)
        assert harness.input_canvas.edit_sessions.snapshot is None
        assert tools.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM
        assert tools.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
        harness.process_events(8)
        durable_changes = QSignalSpy(harness.shell.input_scene_mapping_changes.changed)
        original_mappings = _scene_mappings(canvas.currentScene())

        _drag_shared_edge(canvas, start_x=100.0, finish_x=120.0)
        harness.process_events(12)

        session = harness.input_canvas.edit_sessions.snapshot
        assert session is not None
        assert session.kind is EditSessionKind.SHARED_EDGE_RESIZE
        assert session.undo_depth == 1 and session.redo_depth == 0
        assert session.can_apply and session.can_cancel
        assert durable_changes.count() == 0
        assert _scene_mappings(canvas.currentScene()) == original_mappings
        page = harness.input_canvas.contextual_toolbar.page
        assert isinstance(page, InputEditSessionContextualToolbarPage)
        assert page.label is not None
        assert page.label.text() == "Resize shared edges"
        assert page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()
        assert page.apply_button.isEnabled() and page.cancel_button.isEnabled()
        assert (
            harness.input_canvas.contextual_toolbar.geometry().top()
            > projected_scene.toAlignedRect().bottom()
        )

        pan = tools.palette.presentation_for(InputCanvasToolId.PAN_ZOOM)
        edge = tools.palette.presentation_for(InputCanvasToolId.SHARED_EDGE_RESIZE)
        assert pan is not None and not pan.enabled
        assert edge is not None and edge.enabled and edge.active
        assert not tools.request_tool(InputCanvasToolId.PAN_ZOOM)

        QTest.mouseClick(
            page.history_controls.undo_button,
            Qt.MouseButton.LeftButton,
        )
        harness.process_events(8)
        session = harness.input_canvas.edit_sessions.snapshot
        assert session is not None
        assert session.undo_depth == 0 and session.redo_depth == 1
        assert durable_changes.count() == 0
        page = harness.input_canvas.contextual_toolbar.page
        assert isinstance(page, InputEditSessionContextualToolbarPage)
        assert not page.history_controls.undo_button.isEnabled()
        assert page.history_controls.redo_button.isEnabled()

        QTest.mouseClick(
            page.history_controls.redo_button,
            Qt.MouseButton.LeftButton,
        )
        harness.process_events(8)
        session = harness.input_canvas.edit_sessions.snapshot
        assert session is not None and session.undo_depth == 1
        page = harness.input_canvas.contextual_toolbar.page
        assert isinstance(page, InputEditSessionContextualToolbarPage)
        QTest.mouseClick(page.apply_button, Qt.MouseButton.LeftButton)
        harness.process_events(12)

        assert harness.input_canvas.edit_sessions.snapshot is None
        assert durable_changes.count() == 1
        applied_mappings = _scene_mappings(canvas.currentScene())
        assert applied_mappings != original_mappings
        assert tools.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM
        assert canvas.undoSceneEdit()
        harness.process_events(8)
        assert durable_changes.count() == 2
        assert _scene_mappings(canvas.currentScene()) == original_mappings

        assert tools.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
        harness.process_events(8)
        _drag_shared_edge(canvas, start_x=100.0, finish_x=116.0)
        harness.process_events(10)
        page = harness.input_canvas.contextual_toolbar.page
        assert isinstance(page, InputEditSessionContextualToolbarPage)
        QTest.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)
        harness.process_events(10)
        assert harness.input_canvas.edit_sessions.snapshot is None
        assert durable_changes.count() == 2
        assert _scene_mappings(canvas.currentScene()) == original_mappings
        assert tools.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM

        assert tools.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
        harness.process_events(8)
        _drag_shared_edge(canvas, start_x=100.0, finish_x=112.0)
        harness.process_events(10)
        assert harness.input_canvas.edit_sessions.snapshot is not None
        harness.input_canvas.set_available(False)
        harness.process_events(10)
        assert harness.input_canvas.edit_sessions.snapshot is None
        assert durable_changes.count() == 2
        assert _scene_mappings(canvas.currentScene()) == original_mappings
    finally:
        harness.close()


def _save_mask(path: Path, coverage: QRect) -> Path:
    """Persist one deterministic grayscale mask for the mounted document."""

    image = QImage(200, 100, QImage.Format.Format_Grayscale8)
    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(coverage, QColor("white"))
    painter.end()
    assert image.save(str(path))
    return path


def _drag_shared_edge(
    canvas: CuteCanvas,
    *,
    start_x: float,
    finish_x: float,
) -> None:
    """Complete one shared-edge gesture through the mounted CuteCanvas widget."""

    start = _panel_point(canvas, start_x, 50.0)
    finish = _panel_point(canvas, finish_x, 50.0)
    QTest.mouseMove(canvas, start)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, finish)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=finish)


def _panel_point(canvas: CuteCanvas, x: float, y: float) -> QPoint:
    """Map one scene point through the public panel projection."""

    panel_rect = canvas.sceneToPanelRect(QRectF(x, y, 1.0, 1.0))
    assert panel_rect is not None
    return panel_rect.center().toPoint()


def _scene_mappings(
    scene: SceneSnapshot | None,
) -> tuple[tuple[object, object], ...]:
    """Return stable public layer mappings from one detached scene snapshot."""

    assert scene is not None
    return tuple((layer.layer_id, layer.transform) for layer in scene.layers)
