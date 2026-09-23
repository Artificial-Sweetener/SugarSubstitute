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

"""Project final and transient Output navigation groups for the current route."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_projection import (
    overlay_preview_scenes,
    overlay_preview_sources,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewRegistry,
)


@dataclass(frozen=True, slots=True)
class OutputNavigationProjection:
    """Own visible scene and source groups for one Output navigation host."""

    projection: Callable[[], OutputCanvasProjection | None]
    active_scene_overview: Callable[[], bool]
    active_scene_key: Callable[[], str | None]
    scene_count: Callable[[], int]
    output_session: Callable[[], OutputCanvasSession | None]
    preview_registry: Callable[[], OutputPreviewRegistry]

    def visible_sources(self) -> dict[str, OutputCanvasSourceGroup]:
        """Return sources valid for the current scene-level route."""

        projection = self.projection()
        if projection is None or self.active_scene_overview():
            return {}
        scene_groups = self.scene_groups()
        active_scene_key = self.active_scene_key()
        active_scene = scene_groups.get(active_scene_key) if active_scene_key else None
        if active_scene is not None:
            return {source.source_key: source for source in active_scene.sources}
        if self.scene_count() <= 1:
            sources = overlay_preview_sources(
                projection.sources,
                self._preview_lanes(),
                scene_key=None,
            )
            return {source.source_key: source for source in sources}
        return {}

    def scene_groups(self) -> dict[str, OutputCanvasSceneGroup]:
        """Return current final and transient scenes by stable workflow identity."""

        projection = self.projection()
        scenes = overlay_preview_scenes(
            () if projection is None else projection.scene_groups,
            self._preview_lanes(),
        )
        return {scene.scene_key: scene for scene in scenes}

    def _preview_lanes(self) -> tuple[OutputPreviewLane, ...]:
        """Return preview lanes belonging to the bound Output session."""

        session = self.output_session()
        if session is None:
            return ()
        return self.preview_registry().lanes_for_session(session)


__all__ = ["OutputNavigationProjection"]
