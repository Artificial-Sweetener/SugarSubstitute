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

"""Verify Input selection translation remains responsive to presentation churn."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect
from PySide6.QtTest import QSignalSpy
from cutecanvas import ExecutionRuntime
import pytest

from tests.support.input_canvas import InputSelectionTranslationHarness
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_selection_drag_does_not_publish_mask_layer_projection_state(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep mask-layer inventory stable throughout selection-only movement."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    harness = InputSelectionTranslationHarness(execution_runtime)
    try:
        tool_options = harness.input_canvas.document.tool_options
        mask_layer_changes = QSignalSpy(tool_options.maskLayersChanged)
        brush_context_changes = QSignalSpy(tool_options.brushContextChanged)
        editor_context_changes = QSignalSpy(tool_options.editorContextChanged)
        harness.install_selection(QRect(120, 120, 160, 160))
        assert mask_layer_changes.count() == 0
        assert brush_context_changes.count() == 0
        assert editor_context_changes.count() == 0
        selection_changes = QSignalSpy(harness.canvas.pixelSelectionChanged)
        tool_context_changes = QSignalSpy(
            harness.input_canvas.document.tool_context.changed
        )
        context_rect_updates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def record_context_rect(*args: Any, **kwargs: Any) -> None:
            """Record placement work attempted during the active drag."""

            context_rect_updates.append((args, kwargs))

        monkeypatch.setattr(
            harness.input_canvas.contextual_toolbar,
            "set_context_rect",
            record_context_rect,
        )

        harness.drag_selection(
            start_scene=QPoint(180, 180),
            delta=QPoint(50, 0),
            steps=50,
        )

        state = harness.canvas.pixelSelectionState()
        assert state is not None
        assert state.bounds == QRect(170, 120, 160, 160)
        assert selection_changes.count() == 50
        assert tool_context_changes.count() == 0
        assert mask_layer_changes.count() == 0
        assert brush_context_changes.count() == 0
        assert editor_context_changes.count() == 0
        assert context_rect_updates == []
    finally:
        harness.close()


def test_tool_context_publishes_selection_capability_transitions_once(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Publish selection availability changes without geometry-frame noise."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    harness = InputSelectionTranslationHarness(execution_runtime)
    try:
        changes = QSignalSpy(harness.input_canvas.document.tool_context.changed)

        harness.install_selection(QRect(120, 120, 160, 160))

        wait_for_qt_condition(lambda: changes.count() == 1)
        assert harness.canvas.clearPixelSelection()
        wait_for_qt_condition(lambda: changes.count() == 2)
    finally:
        harness.close()
