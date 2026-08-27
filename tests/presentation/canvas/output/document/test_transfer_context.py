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

"""Verify Output transfer gestures and context-menu routing."""

from __future__ import annotations

from uuid import uuid4
from pytest import MonkeyPatch
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QContextMenuEvent,
    QMouseEvent,
)
from cutecanvas import (
    DragSubject,
)
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_context_menu_composition import (
    compose_output_context_menu,
)
from substitute.presentation.canvas.output import (
    output_canvas_context_menu,
    output_grid_context_menu,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from cutecanvas import ExecutionRuntime
from tests.support.qt.lifecycle import destroy_qt_object

from .support import _image, _app, _DragProvider, _projection, _session


def test_output_grid_pointer_gesture_starts_transfer_for_its_tile(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Output's installed transfer policy must work from a fitted grid tile."""
    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    provider = _DragProvider()
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.install_transfer_drag_provider(provider)
        assert canvas.document.present_grid((first_id, second_id))
        app.processEvents()
        composition_id = canvas.document.composition_id_for(second_id)
        assert composition_id is not None
        target = canvas.workspace.canvasFor(composition_id)
        assert target is not None
        origin = QPointF(target.rect().center())
        destination = origin + QPointF(20.0, 0.0)

        target.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                origin,
                origin,
                origin,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        target.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                destination,
                destination,
                destination,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )

        assert provider.subjects
        assert getattr(provider.subjects[0], "target_id") == composition_id
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_output_canvas_forwards_captured_workspace_context_without_activation(
    execution_runtime: ExecutionRuntime,
) -> None:
    """A content context request should preserve the clicked document reference only."""

    _app()
    image_id = uuid4()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    contexts: list[tuple[object, object]] = []
    try:
        assert canvas.document.admit_image(image_id, _image("red"))
        reference = canvas.document.content_reference_for(image_id)
        assert reference is not None
        active_composition_id = canvas.document.session.active_composition_id
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )

        canvas.workspace.contentContextRequested.emit(reference, QPoint(12, 20))

        assert contexts == [(reference, QPoint(12, 20))]
        assert canvas.document.session.active_composition_id == active_composition_id
    finally:
        destroy_qt_object(canvas)


def test_output_grid_right_click_forwards_the_clicked_tile_context(
    execution_runtime: ExecutionRuntime,
) -> None:
    """A grid context gesture must address its tile without changing Output route."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    contexts: list[tuple[object, object]] = []
    try:
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        first_reference = canvas.document.content_reference_for(first_id)
        second_reference = canvas.document.content_reference_for(second_id)
        assert first_reference is not None
        assert second_reference is not None
        canvas.document.present_grid((first_id, second_id))
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )
        target = canvas.workspace.canvasFor(second_reference.composition_id)
        assert target is not None
        active_before = canvas.document.session.active_composition_id

        app.sendEvent(
            target,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                QPoint(4, 4),
                QPoint(24, 28),
            ),
        )

        assert len(contexts) == 1
        subject, position = contexts[0]
        assert isinstance(subject, DragSubject)
        assert subject.subject_id == second_reference
        assert subject.target_id == second_reference.composition_id
        assert position == QPoint(24, 28)
        assert canvas.document.session.active_composition_id == active_before
    finally:
        destroy_qt_object(canvas)


def test_output_comparison_right_click_forwards_the_established_output_context(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Native comparison must forward the primary Output content to its normal menu."""

    app = _app()
    first_id = uuid4()
    second_id = uuid4()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    contexts: list[tuple[object, object]] = []
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        first_reference = canvas.document.content_reference_for(first_id)
        assert first_reference is not None
        assert canvas.document.present_comparison(
            first_id,
            second_id,
            split_position=0.5,
            orientation="vertical",
        )
        app.processEvents()
        pane = canvas.workspace.currentCanvas()
        assert pane is not None
        canvas.install_transfer_context_handler(
            lambda subject, position: contexts.append((subject, position))
        )

        app.sendEvent(
            pane,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                QPoint(12, 20),
                QPoint(32, 40),
            ),
        )

        assert contexts == [(first_reference, QPoint(32, 40))]
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_composed_output_context_router_connects_to_workspace_signal(
    execution_runtime: ExecutionRuntime,
    monkeypatch: MonkeyPatch,
) -> None:
    """Compose addressed grid actions through the real CuteCanvas context signal."""

    _app()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    copied: list[object] = []
    rendered_models: list[MenuModel] = []

    class _Menu:
        """Accept the menu execution request without opening a native popup."""

        def exec(self, _position: object, **_kwargs: object) -> None:
            """Record no additional state for this offscreen menu execution."""

    class _Renderer:
        """Capture the model built by the production grid menu."""

        def __init__(self, *, parent: object) -> None:
            """Accept the production renderer constructor contract."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Capture one model instead of creating a native Qt menu."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(output_grid_context_menu, "QFluentMenuRenderer", _Renderer)
    image_id = uuid4()
    try:
        assert canvas.document.admit_image(image_id, _image("red"))
        reference = canvas.document.content_reference_for(image_id)
        assert reference is not None
        canvas.document.present_grid((image_id,))

        router = compose_output_context_menu(canvas, request_copy=copied.append)
        canvas.workspace.contentContextRequested.emit(reference, QPoint(24, 28))

        assert router.grid_menu.parent is canvas
        assert len(rendered_models) == 1
        entries = tuple(
            entry for entry in rendered_models[0].entries if isinstance(entry, MenuItem)
        )
        assert tuple(entry.action_id for entry in entries) == (
            "output_canvas.copy",
            "output_canvas.open_current_external",
            "output_canvas.reveal_current_asset",
            "output_canvas.dock_action",
        )
        assert entries[0].callback is not None
        entries[0].callback()
        assert copied == [reference]
    finally:
        destroy_qt_object(canvas)


def test_composed_output_context_router_uses_full_output_actions_for_detail(
    execution_runtime: ExecutionRuntime,
    monkeypatch: MonkeyPatch,
) -> None:
    """The production context signal must retain full Output actions in detail mode."""

    _app()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    rendered_models: list[MenuModel] = []

    class _Menu:
        """Accept the menu execution request without opening a native popup."""

        def exec(self, _position: object, **_kwargs: object) -> None:
            """Use the same execution contract without native window creation."""

    class _Renderer:
        """Capture one full Output action model from the production renderer."""

        def __init__(self, *, parent: object) -> None:
            """Accept the production renderer constructor contract."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Capture one menu model instead of creating a native popup."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(output_canvas_context_menu, "QFluentMenuRenderer", _Renderer)
    first_id = uuid4()
    second_id = uuid4()
    try:
        assert canvas.document.admit_image(first_id, _image("red"))
        assert canvas.document.admit_image(second_id, _image("blue"))
        canvas.bind_projection_session(
            _session(boundary, _projection(first_id, second_id))
        )
        reference = canvas.document.content_reference_for(first_id)
        assert reference is not None

        router = compose_output_context_menu(
            canvas, request_copy=lambda _reference: None
        )
        canvas.workspace.contentContextRequested.emit(reference, QPoint(24, 28))

        assert router.output_menu.parent is canvas
        assert len(rendered_models) == 1
        entries = tuple(
            entry for entry in rendered_models[0].entries if isinstance(entry, MenuItem)
        )
        assert tuple(entry.action_id for entry in entries) == (
            "output_canvas.compare_outputs",
            "output_canvas.copy",
            "output_canvas.open_current_external",
            "output_canvas.open_all_external",
            "output_canvas.reveal_current_asset",
            "output_canvas.dock_action",
        )
        assert entries[1].icon is FIF.COPY
        assert entries[2].icon is FIF.PHOTO
        assert entries[3].icon is AppIcon.IMAGE_MULTIPLE_20_REGULAR
        assert entries[4].icon is AppIcon.FOLDER_OPEN_20_REGULAR
        assert entries[5].icon is FIF.FULL_SCREEN
    finally:
        destroy_qt_object(canvas)
