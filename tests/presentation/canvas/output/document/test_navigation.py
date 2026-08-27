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

"""Verify Output workspace activation and navigation interactions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4
from pytest import approx
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from cutecanvas import (
    ComparisonOrientation,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from cutecanvas import ExecutionRuntime
from .comparison_support import _NativeComparisonProbe
from .support import _app, _destroy_output_canvas, _image, _projection, _session


def test_output_workspace_activation_forwards_document_image_identity() -> None:
    """Forward a known CuteCanvas composition through the Output navigation owner."""

    composition_id = uuid4()
    image_id = uuid4()
    activated: list[object] = []
    host = SimpleNamespace(
        document=SimpleNamespace(
            image_id_for_composition=lambda candidate: (
                image_id if candidate == composition_id else None
            )
        ),
        _document_navigation=SimpleNamespace(
            activate_grid_target=lambda candidate: activated.append(candidate)
        ),
    )

    OutputCanvas._activate_workspace_target(cast(OutputCanvas, host), composition_id)

    assert activated == [image_id]


def test_output_workspace_activation_ignores_unknown_composition() -> None:
    """Keep an unknown CuteCanvas composition outside product navigation."""

    activated: list[object] = []
    host = SimpleNamespace(
        document=SimpleNamespace(image_id_for_composition=lambda _candidate: None),
        _document_navigation=SimpleNamespace(
            activate_grid_target=lambda candidate: activated.append(candidate)
        ),
    )

    OutputCanvas._activate_workspace_target(cast(OutputCanvas, host), uuid4())

    assert activated == []


def test_output_grid_reselects_target_after_returning_from_detail(
    execution_runtime: ExecutionRuntime,
) -> None:
    """A grid click must navigate even when that image remains session-active."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    selected: list[str] = []
    canvas.activeOutputChanged.connect(selected.append)

    try:
        canvas.resize(900, 600)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        composition = canvas.document.composition_id_for(second_id)
        assert composition is not None
        target = canvas.workspace.canvasFor(composition)
        assert target is not None

        QTest.mouseClick(target, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert selected == [str(second_id)]

        canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        returned_target = canvas.workspace.canvasFor(composition)
        assert returned_target is not None
        QTest.mouseClick(returned_target, Qt.MouseButton.LeftButton)
        app.processEvents()

        assert selected == [str(second_id), str(second_id)]
    finally:
        _destroy_output_canvas(canvas)


def test_output_workspace_middle_mouse_divider_updates_compare_state(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Persist a native middle-button divider summon and drag without feedback."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    base = OutputCompareSelection(scene_key=None, source_key="source", set_index=1)
    comparison = OutputCompareSelection(
        scene_key=None,
        source_key="source",
        set_index=2,
    )
    projection = _projection(
        first_id,
        second_id,
        compare_state=OutputCompareState(
            enabled=True,
            base=base,
            comparison=comparison,
            split_position=0.25,
            orientation="vertical",
        ),
    )
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    states: list[OutputCompareState] = []
    canvas.activeOutputCompareChanged.connect(states.append)

    try:
        canvas.resize(900, 600)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(_session(boundary, projection))
        assert states == []
        reprojected: list[OutputCompareState] = []

        def reproject_compare_state(state: OutputCompareState) -> None:
            """Replay persisted compare state through the production projection sink."""

            reprojected.append(state)
            canvas.bind_projection_session(
                _session(
                    boundary,
                    _projection(first_id, second_id, compare_state=state),
                )
            )

        canvas.activeOutputCompareChanged.connect(reproject_compare_state)
        first_composition = canvas.document.composition_id_for(first_id)
        second_composition = canvas.document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None

        app.processEvents()
        pane_widget = canvas.workspace.currentCanvas()
        assert pane_widget is not None
        pane = cast(_NativeComparisonProbe, pane_widget)
        called_position = QPoint(
            pane_widget.width() * 2 // 3,
            pane_widget.height() // 2,
        )
        destination = QPoint(
            min(pane_widget.width() - 2, called_position.x() + 80),
            called_position.y(),
        )
        QTest.mousePress(
            pane_widget,
            Qt.MouseButton.MiddleButton,
            pos=called_position,
        )
        app.processEvents()
        called_divider = pane.comparisonDividerState()
        assert called_divider.dragging is True
        assert called_divider.visible_segment is not None
        assert called_divider.visible_segment.x1() == approx(
            called_position.x(),
            abs=1.0,
        )
        QTest.mouseMove(pane_widget, destination)
        QTest.mouseRelease(
            pane_widget,
            Qt.MouseButton.MiddleButton,
            pos=destination,
        )
        app.processEvents()

        indicator = canvas._zoom_indicators._comparison_indicator
        assert indicator.opacity >= 0.0

        assert states[-1].split_position > 0.5
        assert states[-1].orientation == "vertical"
        assert canvas.visible_compare_state == states[-1]
        assert reprojected == states
        assert pane.comparisonDividerState().dragging is False

        canvas.workspace.setComparisonPresentation(
            first_composition,
            second_composition,
            split_position=states[-1].split_position,
            orientation=ComparisonOrientation.HORIZONTAL,
        )
        app.processEvents()
        assert states[-1].split_position == pane.comparisonState().split_position
        assert states[-1].orientation == "horizontal"
        assert canvas.visible_compare_state == states[-1]
        assert reprojected == states
    finally:
        _destroy_output_canvas(canvas)
