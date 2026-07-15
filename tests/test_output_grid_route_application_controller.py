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

"""Verify prepared Output grid route application delegation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridRouteApplicationController,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridScenePlan,
)


@dataclass(frozen=True, slots=True)
class _ScenePlan:
    """Carry a prepared route, request, and signature for application tests."""

    route: CanvasRouteIdentity
    request: object
    layout_signature: object


def test_source_grid_plan_applies_route_and_returns_composition() -> None:
    """Prepared source-grid plans should apply through the guarded projector."""

    composition_id = uuid4()
    route = CanvasRouteIdentity("source_grid", "source:source-a;set:0")
    request = object()
    signature = object()
    projector = _RouteProjector(composition_id)
    result = _controller(projector).apply(
        _plan(route, request, signature),
        activate=True,
    )

    assert result.accepted is True
    assert result.composition_id == composition_id
    assert result.layout_signature is signature
    assert projector.source_grid_calls == ((route, request, True),)


def test_scene_overview_plan_requires_cached_images() -> None:
    """Prepared scene plans should not apply until catalog assets are ready."""

    route = CanvasRouteIdentity("scene_overview", "scene:scene-a")
    projector = _RouteProjector(uuid4())
    result = _controller(projector, images_cached=False).apply(
        _plan(route, object(), object()),
        activate=True,
    )

    assert result.accepted is False
    assert projector.scene_overview_calls == ()


def test_scene_overview_plan_applies_route_and_returns_composition() -> None:
    """Prepared scene plans should apply through the guarded projector."""

    composition_id = uuid4()
    route = CanvasRouteIdentity("scene_overview", "scene:scene-a")
    request = object()
    projector = _RouteProjector(composition_id)
    result = _controller(projector).apply(
        _plan(route, request, object()),
        activate=False,
    )

    assert result.accepted is True
    assert result.composition_id == composition_id
    assert projector.scene_overview_calls == ((route, request, False),)


def test_unknown_grid_route_is_rejected() -> None:
    """Prepared plans outside the two grid route kinds should fail closed."""

    projector = _RouteProjector(uuid4())
    result = _controller(projector).apply(
        _plan(CanvasRouteIdentity.empty(), object(), object()),
        activate=True,
    )

    assert result.accepted is False
    assert projector.source_grid_calls == ()
    assert projector.scene_overview_calls == ()


@dataclass(slots=True)
class _RouteProjector:
    """Record prepared grid applications."""

    composition_id: UUID
    source_grid_calls: tuple[tuple[CanvasRouteIdentity, object, bool], ...] = ()
    scene_overview_calls: tuple[tuple[CanvasRouteIdentity, object, bool], ...] = ()

    def apply_source_grid_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Record one source-grid application."""

        self.source_grid_calls = (*self.source_grid_calls, (route, request, activate))
        return True

    def apply_scene_overview_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Record one scene-overview application."""

        self.scene_overview_calls = (
            *self.scene_overview_calls,
            (route, request, activate),
        )
        return True

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Return the fixed authorized composition identity."""

        _ = route
        return self.composition_id


def _controller(
    projector: _RouteProjector,
    *,
    images_cached: bool = True,
) -> OutputGridRouteApplicationController:
    """Build a prepared route application controller."""

    return OutputGridRouteApplicationController(
        route_projector=projector,
        ensure_scene_request_images_cached=lambda _request: images_cached,
    )


def _plan(
    route: CanvasRouteIdentity,
    request: object,
    signature: object,
) -> OutputGridScenePlan:
    """Cast a minimal structural plan for focused application tests."""

    return cast(
        OutputGridScenePlan,
        cast(Any, _ScenePlan(route, request, signature)),
    )
