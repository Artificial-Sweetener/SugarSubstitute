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

"""Coordinate Output canvas pointer gestures without owning QPane hit testing."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    OutputCanvasHitKind,
    OutputCanvasHitValidation,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)

GridPointerEventKind = Literal["press", "release"]


class GridPointDelta(Protocol):
    """Expose the distance API used by Qt point deltas."""

    def manhattanLength(self) -> int:  # noqa: N802
        """Return the Manhattan length for a pointer delta."""


class GridPoint(Protocol):
    """Expose the subtraction API used by Qt points."""

    def __sub__(self, other: GridPoint) -> GridPointDelta:
        """Return the point delta."""


@dataclass(frozen=True, slots=True)
class OutputCanvasInteractionController:
    """Own Output canvas click gesture state and interaction mode writes."""

    press_position: Callable[[], GridPoint | None]
    set_press_position: Callable[[GridPoint | None], None]
    set_control_mode: Callable[[object], None]
    cursor_control_mode: object
    panzoom_control_mode: object

    @staticmethod
    def grid_event_filter_enabled(
        *,
        watched_is_pane: bool,
        active_scene_overview: bool,
        active_set_index: int,
        is_mouse_event: bool,
    ) -> bool:
        """Return whether an event is eligible for output-grid click handling."""

        return bool(
            watched_is_pane
            and is_mouse_event
            and (active_scene_overview or active_set_index == 0)
        )

    @staticmethod
    def grid_pointer_event_kind(
        *,
        event_type: object,
        press_type: object,
        release_type: object,
    ) -> GridPointerEventKind | None:
        """Return the supported pointer event kind for a Qt event type."""

        if event_type == press_type:
            return "press"
        if event_type == release_type:
            return "release"
        return None

    @classmethod
    def grid_event_filter_action(
        cls,
        *,
        watched_is_pane: bool,
        active_scene_overview: bool,
        active_set_index: int,
        is_mouse_event: bool,
        event_type: object,
        press_type: object,
        release_type: object,
    ) -> GridPointerEventKind | None:
        """Return the grid event action eligible for widget-side adaptation."""

        if not cls.grid_event_filter_enabled(
            watched_is_pane=watched_is_pane,
            active_scene_overview=active_scene_overview,
            active_set_index=active_set_index,
            is_mouse_event=is_mouse_event,
        ):
            return None
        return cls.grid_pointer_event_kind(
            event_type=event_type,
            press_type=press_type,
            release_type=release_type,
        )

    def record_grid_mouse_press(
        self,
        *,
        is_left_button: bool,
        position: GridPoint,
    ) -> bool:
        """Remember an eligible grid click start without consuming the event."""

        if is_left_button:
            self.set_press_position(position)
        return False

    def grid_mouse_release_position(
        self,
        *,
        is_left_button: bool,
        position: GridPoint,
        drag_distance: int,
    ) -> GridPoint | None:
        """Return a release position only when the stored press forms a click."""

        if not is_left_button:
            return None
        press_position = self.press_position()
        self.set_press_position(None)
        if press_position is None:
            return None
        if (position - press_position).manhattanLength() > drag_distance:
            return None
        return position

    def grid_mouse_release_command(
        self,
        *,
        is_left_button: bool,
        position: GridPoint,
        drag_distance: int,
        hit_at: Callable[[GridPoint], OutputCanvasHitValidation],
        active_scene_overview: bool,
    ) -> GridActivationCommand | None:
        """Return the activation command for a qualifying grid click release."""

        release_position = self.grid_mouse_release_position(
            is_left_button=is_left_button,
            position=position,
            drag_distance=drag_distance,
        )
        if release_position is None:
            return None
        return self.grid_activation_command(
            hit_at(release_position),
            active_scene_overview=active_scene_overview,
        )

    def grid_mouse_release_activation(
        self,
        *,
        is_left_button: bool,
        position: GridPoint,
        drag_distance: int,
        hit_at: Callable[[GridPoint], OutputCanvasHitValidation],
        active_scene_overview: bool,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> GridResolvedActivationCommand | None:
        """Return the resolved activation represented by a grid click release."""

        command = self.grid_mouse_release_command(
            is_left_button=is_left_button,
            position=position,
            drag_distance=drag_distance,
            hit_at=hit_at,
            active_scene_overview=active_scene_overview,
        )
        if command is None:
            return None
        if isinstance(command, ActivateSceneGridCommand):
            return command
        resolved_item = self.final_output_item_for_command(
            command,
            source_groups_by_key,
        )
        if resolved_item is None:
            return None
        source_key, item = resolved_item
        return ActivateFinalOutputItemGridCommand(source_key=source_key, item=item)

    @staticmethod
    def grid_activation_command(
        hit: OutputCanvasHitValidation,
        *,
        active_scene_overview: bool,
    ) -> GridActivationCommand | None:
        """Return the activation command represented by one validated grid hit."""

        if active_scene_overview:
            if (
                hit.accepted
                and hit.kind is OutputCanvasHitKind.SCENE
                and hit.scene_key is not None
            ):
                return ActivateSceneGridCommand(scene_key=hit.scene_key)
            return None
        if (
            hit.accepted
            and hit.kind is OutputCanvasHitKind.FINAL_OUTPUT
            and hit.source_key is not None
            and hit.set_index is not None
        ):
            return ActivateFinalOutputGridCommand(
                source_key=hit.source_key,
                set_index=hit.set_index,
                image_id=hit.image_id,
            )
        return None

    @staticmethod
    def final_output_item_for_command(
        command: ActivateFinalOutputGridCommand,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> tuple[str, OutputCanvasImageItem] | None:
        """Return the concrete output item represented by a final-output click."""

        item = OutputCanvasRouteModel.item_for_source_and_set(
            source_groups_by_key,
            command.source_key,
            command.set_index,
        )
        if item is not None:
            return command.source_key, item
        if command.image_id is None:
            return None
        return OutputCanvasRouteModel.output_item_for_image_id(
            source_groups_by_key,
            command.image_id,
        )

    def set_grid_interaction_locked(self, locked: bool) -> None:
        """Apply the QPane control mode for grid interaction or inspection."""

        mode = self.cursor_control_mode if locked else self.panzoom_control_mode
        self.set_control_mode(mode)


@dataclass(frozen=True, slots=True)
class ActivateSceneGridCommand:
    """Request activation of one scene-overview tile."""

    scene_key: str


@dataclass(frozen=True, slots=True)
class ActivateFinalOutputGridCommand:
    """Request activation of one final-output grid tile."""

    source_key: str
    set_index: int
    image_id: UUID | None


@dataclass(frozen=True, slots=True)
class ActivateFinalOutputItemGridCommand:
    """Request activation of one concrete final-output grid item."""

    source_key: str
    item: OutputCanvasImageItem


GridActivationCommand = ActivateSceneGridCommand | ActivateFinalOutputGridCommand
GridResolvedActivationCommand = (
    ActivateSceneGridCommand | ActivateFinalOutputItemGridCommand
)


__all__ = [
    "ActivateFinalOutputGridCommand",
    "ActivateFinalOutputItemGridCommand",
    "ActivateSceneGridCommand",
    "GridActivationCommand",
    "GridPoint",
    "GridPointDelta",
    "GridPointerEventKind",
    "GridResolvedActivationCommand",
    "OutputCanvasInteractionController",
]
