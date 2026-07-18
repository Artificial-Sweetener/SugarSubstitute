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

"""Adapt Output canvas grid mouse events into navigation activation commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.workflows.canvas_route_projector_port import (
    OutputCanvasHitValidation,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    ActivateFinalOutputItemGridCommand,
    ActivateSceneGridCommand,
    GridPoint,
    OutputCanvasInteractionController,
)


@dataclass(frozen=True, slots=True)
class OutputCanvasGridEventController:
    """Route grid mouse events through interaction and navigation owners."""

    interaction_controller: OutputCanvasInteractionController
    watched_is_pane: Callable[[object], bool]
    is_mouse_event: Callable[[object], bool]
    event_type: Callable[[object], object]
    event_is_left_button: Callable[[object], bool]
    event_position: Callable[[object], GridPoint]
    drag_distance: Callable[[], int]
    hit_at: Callable[[GridPoint], OutputCanvasHitValidation]
    active_scene_overview: Callable[[], bool]
    active_set_index: Callable[[], int]
    source_groups_by_key: Callable[[], Mapping[str, OutputCanvasSourceGroup]]
    activate_scene: Callable[[str], OutputSceneNavigationSelection | None]
    activate_item: Callable[[str, OutputCanvasImageItem], None]
    emit_scene_changed: Callable[[OutputSceneNavigationSelection], None]
    press_type: object
    release_type: object

    def handle_event_filter(self, watched: object, event: object) -> bool:
        """Handle eligible grid press/release events without consuming QPane events."""

        is_mouse_event = self.is_mouse_event(event)
        event_kind = self.interaction_controller.grid_event_filter_action(
            watched_is_pane=self.watched_is_pane(watched),
            active_scene_overview=self.active_scene_overview(),
            active_set_index=self.active_set_index(),
            is_mouse_event=is_mouse_event,
            event_type=self.event_type(event) if is_mouse_event else None,
            press_type=self.press_type,
            release_type=self.release_type,
        )
        if event_kind == "press":
            return self.interaction_controller.record_grid_mouse_press(
                is_left_button=self.event_is_left_button(event),
                position=self.event_position(event),
            )
        if event_kind == "release":
            self._handle_grid_release(event)
        return False

    def _handle_grid_release(self, event: object) -> None:
        """Apply a resolved grid-release command to Output navigation state."""

        command = self.interaction_controller.grid_mouse_release_activation(
            is_left_button=self.event_is_left_button(event),
            position=self.event_position(event),
            drag_distance=self.drag_distance(),
            hit_at=self.hit_at,
            active_scene_overview=self.active_scene_overview(),
            source_groups_by_key=self.source_groups_by_key(),
        )
        if isinstance(command, ActivateSceneGridCommand):
            self._activate_scene_grid_tile(command)
            return
        if isinstance(command, ActivateFinalOutputItemGridCommand):
            self.activate_item(command.source_key, command.item)

    def _activate_scene_grid_tile(self, command: ActivateSceneGridCommand) -> None:
        """Activate a scene-overview tile and emit host-facing route signals."""

        selection = self.activate_scene(command.scene_key)
        if selection is None:
            return
        self.emit_scene_changed(selection)


__all__ = ["OutputCanvasGridEventController"]
