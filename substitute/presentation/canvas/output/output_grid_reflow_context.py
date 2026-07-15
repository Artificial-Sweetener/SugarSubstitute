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

"""Resolve the authoritative current Output grid presentation context."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_route_scope import (
    scene_overview_route_identity,
    source_grid_route_identity,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.domain.workflow import CanvasRouteIdentity, CanvasSessionToken


@dataclass(frozen=True, slots=True)
class OutputSceneOverviewGridContext:
    """Describe an authorized current scene-overview grid target."""

    session_token: CanvasSessionToken
    route: CanvasRouteIdentity
    scenes: tuple[OutputCanvasSceneGroup, ...]


@dataclass(frozen=True, slots=True)
class OutputSourceGridContext:
    """Describe an authorized current source-batch grid target."""

    session_token: CanvasSessionToken
    route: CanvasRouteIdentity
    source: OutputCanvasSourceGroup
    scene_key: str | None


OutputGridReflowContext: TypeAlias = (
    OutputSceneOverviewGridContext | OutputSourceGridContext
)


@dataclass(frozen=True, slots=True)
class OutputGridReflowContextResolver:
    """Resolve grid presentation only from current authorized host state."""

    output_session: Callable[[], OutputCanvasSession | None]
    scene_groups: Callable[[], Mapping[str, OutputCanvasSceneGroup]]
    source_groups: Callable[[], Mapping[str, OutputCanvasSourceGroup]]
    compare_enabled: Callable[[], bool]
    scene_overview_active: Callable[[], bool]
    active_scene_key: Callable[[], str | None]
    active_source_key: Callable[[], str | None]
    active_set_index: Callable[[], int]

    def current_context(self) -> OutputGridReflowContext | None:
        """Return the current valid source/scene grid target, if any."""

        session = self.output_session()
        if session is None or self.compare_enabled():
            return None
        scene_key = self.active_scene_key()
        scenes = self.scene_groups()
        if self.scene_overview_active() and session.projection.scene_count > 1:
            route = scene_overview_route_identity(active_scene_key=scene_key)
            if route != session.active_route:
                return None
            return OutputSceneOverviewGridContext(
                session.token(),
                route,
                tuple(
                    sorted(
                        scenes.values(),
                        key=lambda scene: (scene.order, scene.scene_key),
                    )
                ),
            )
        if self.active_set_index() != 0 or self.scene_overview_active():
            return None
        source_key = self.active_source_key()
        source = (
            self.source_groups().get(source_key) if source_key is not None else None
        )
        if source is None:
            return None
        route = source_grid_route_identity(
            source_key=source.source_key, active_scene_key=scene_key
        )
        if route != session.active_route:
            return None
        return OutputSourceGridContext(session.token(), route, source, scene_key)


__all__ = [
    "OutputGridReflowContext",
    "OutputGridReflowContextResolver",
    "OutputSceneOverviewGridContext",
    "OutputSourceGridContext",
]
