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

"""Verify Output canvas compare rendering orchestration outside the widget."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_canvas_compare_rendering_controller import (
    OutputCanvasCompareRenderingController,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresentation,
)


def test_sync_compare_rendering_clears_when_projection_missing() -> None:
    """Missing projection should clear QPane compare rendering through route scope."""

    route = CanvasRouteIdentity.empty()
    projector = _Projector()
    bound_routes: list[CanvasRouteIdentity] = []
    controller = _controller(
        projector=projector,
        projection=None,
        clear_route=route,
        bind_routes=bound_routes,
    )

    controller.sync_compare_rendering()

    assert bound_routes == [route]
    assert projector.cleared_routes == (route,)


def test_sync_compare_rendering_applies_without_emitting_unchanged_state() -> None:
    """Unchanged compare presentations should not emit workflow state changes."""

    state = OutputCompareState(enabled=True)
    presenter = _Presenter(
        presentation=OutputComparePresentation(state=state, applied=True)
    )
    emitted: list[OutputCompareState] = []
    stored: list[OutputCompareState] = []
    controller = _controller(
        presenter=presenter,
        state=state,
        projection=_projection(),
        emitted=emitted,
        stored=stored,
        route_blocked=True,
    )

    controller.sync_compare_rendering()

    assert presenter.calls == ((_projection(), state, True),)
    assert stored == []
    assert emitted == []


def test_sync_compare_rendering_stores_and_emits_reconciled_state() -> None:
    """Changed compare presentations should update visible state and notify UI."""

    initial = OutputCompareState(enabled=True)
    reconciled = OutputCompareState(enabled=False)
    presenter = _Presenter(
        presentation=OutputComparePresentation(
            state=reconciled,
            applied=True,
            state_changed=True,
        )
    )
    emitted: list[OutputCompareState] = []
    stored: list[OutputCompareState] = []
    controller = _controller(
        presenter=presenter,
        state=initial,
        projection=_projection(),
        emitted=emitted,
        stored=stored,
    )

    controller.sync_compare_rendering()

    assert stored == [reconciled]
    assert emitted == [reconciled]


@dataclass(slots=True)
class _Projector:
    """Record compare clear calls."""

    cleared_routes: tuple[CanvasRouteIdentity, ...] = ()

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Record one compare clear command."""

        self.cleared_routes = (*self.cleared_routes, route)
        return True


@dataclass(slots=True)
class _Presenter:
    """Return a fixed compare presentation and record calls."""

    presentation: OutputComparePresentation
    calls: tuple[
        tuple[OutputCanvasProjection, OutputCompareState, bool],
        ...,
    ] = ()

    def present(
        self,
        *,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
        route_blocked: bool = False,
    ) -> OutputComparePresentation:
        """Return the configured compare presentation."""

        self.calls = (*self.calls, (projection, state, route_blocked))
        return self.presentation


def _controller(
    *,
    projector: _Projector | None = None,
    presenter: _Presenter | None = None,
    state: OutputCompareState | None = None,
    projection: OutputCanvasProjection | None = None,
    route_blocked: bool = False,
    clear_route: CanvasRouteIdentity | None = None,
    bind_routes: list[CanvasRouteIdentity] | None = None,
    stored: list[OutputCompareState] | None = None,
    emitted: list[OutputCompareState] | None = None,
) -> OutputCanvasCompareRenderingController:
    """Return a compare rendering controller with deterministic collaborators."""

    active_projector = projector or _Projector()
    active_presenter = presenter or _Presenter(
        OutputComparePresentation(
            state=state or OutputCompareState(),
            applied=True,
        )
    )
    active_state = state or OutputCompareState()
    active_clear_route = clear_route or CanvasRouteIdentity.empty()
    active_bind_routes = bind_routes if bind_routes is not None else []
    active_stored = stored if stored is not None else []
    active_emitted = emitted if emitted is not None else []
    return OutputCanvasCompareRenderingController(
        visible_compare_state=lambda: active_state,
        output_projection=lambda: projection,
        output_compare_presenter=lambda: active_presenter,
        route_blocked=lambda: route_blocked,
        set_visible_compare_state=active_stored.append,
        emit_compare_changed=active_emitted.append,
        clear_route_identity=lambda: active_clear_route,
        bind_output_route_projector=active_bind_routes.append,
        route_projector=lambda: active_projector,
    )


def _projection() -> OutputCanvasProjection:
    """Return an empty projection sufficient for controller collaborator calls."""

    return OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
    )
