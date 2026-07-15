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

"""Verify Output canvas pointer interaction coordination."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    OutputCanvasHitValidation,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    ActivateFinalOutputGridCommand,
    ActivateFinalOutputItemGridCommand,
    ActivateSceneGridCommand,
    GridPoint,
    OutputCanvasInteractionController,
)


def test_grid_mouse_press_records_left_button_position() -> None:
    """Left-button grid presses should store the click start position."""

    state = _InteractionState()
    controller = state.controller()
    point = _Point(4, 5)

    handled = controller.record_grid_mouse_press(
        is_left_button=True,
        position=point,
    )

    assert handled is False
    assert state.press_position is point


def test_grid_event_filter_enabled_requires_pane_mouse_and_grid_route() -> None:
    """Grid event filtering should only arm for pane mouse events in grid routes."""

    assert (
        OutputCanvasInteractionController.grid_event_filter_enabled(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=0,
            is_mouse_event=True,
        )
        is True
    )
    assert (
        OutputCanvasInteractionController.grid_event_filter_enabled(
            watched_is_pane=False,
            active_scene_overview=False,
            active_set_index=0,
            is_mouse_event=True,
        )
        is False
    )
    assert (
        OutputCanvasInteractionController.grid_event_filter_enabled(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=1,
            is_mouse_event=True,
        )
        is False
    )
    assert (
        OutputCanvasInteractionController.grid_event_filter_enabled(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=0,
            is_mouse_event=False,
        )
        is False
    )


def test_grid_event_filter_enabled_allows_scene_overview_for_non_grid_set() -> None:
    """Scene overview clicks should remain eligible outside set-zero grid mode."""

    assert (
        OutputCanvasInteractionController.grid_event_filter_enabled(
            watched_is_pane=True,
            active_scene_overview=True,
            active_set_index=3,
            is_mouse_event=True,
        )
        is True
    )


def test_grid_pointer_event_kind_maps_supported_press_and_release_types() -> None:
    """Only press and release event types should route to grid handlers."""

    assert (
        OutputCanvasInteractionController.grid_pointer_event_kind(
            event_type="press",
            press_type="press",
            release_type="release",
        )
        == "press"
    )
    assert (
        OutputCanvasInteractionController.grid_pointer_event_kind(
            event_type="release",
            press_type="press",
            release_type="release",
        )
        == "release"
    )
    assert (
        OutputCanvasInteractionController.grid_pointer_event_kind(
            event_type="move",
            press_type="press",
            release_type="release",
        )
        is None
    )


def test_grid_event_filter_action_returns_supported_grid_event_kind() -> None:
    """Eligible grid events should return the pointer action for the event type."""

    assert (
        OutputCanvasInteractionController.grid_event_filter_action(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=0,
            is_mouse_event=True,
            event_type="press",
            press_type="press",
            release_type="release",
        )
        == "press"
    )


def test_grid_event_filter_action_rejects_ineligible_events() -> None:
    """Ineligible grid events should not request press/release adaptation."""

    assert (
        OutputCanvasInteractionController.grid_event_filter_action(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=1,
            is_mouse_event=True,
            event_type="press",
            press_type="press",
            release_type="release",
        )
        is None
    )
    assert (
        OutputCanvasInteractionController.grid_event_filter_action(
            watched_is_pane=True,
            active_scene_overview=False,
            active_set_index=0,
            is_mouse_event=False,
            event_type=None,
            press_type="press",
            release_type="release",
        )
        is None
    )


def test_grid_mouse_press_ignores_non_left_button() -> None:
    """Non-left grid presses should not overwrite the stored click start."""

    state = _InteractionState(press_position=_Point(1, 1))
    controller = state.controller()

    controller.record_grid_mouse_press(
        is_left_button=False,
        position=_Point(9, 9),
    )

    assert state.press_position == _Point(1, 1)


def test_grid_mouse_release_rejects_non_left_button_without_clearing_press() -> None:
    """Non-left releases should not consume the pending left-button press."""

    press = _Point(2, 2)
    state = _InteractionState(press_position=press)
    controller = state.controller()

    release = controller.grid_mouse_release_position(
        is_left_button=False,
        position=_Point(2, 2),
        drag_distance=4,
    )

    assert release is None
    assert state.press_position is press


def test_grid_mouse_release_rejects_drag_and_clears_press() -> None:
    """Release movement beyond the drag threshold should not activate a hit test."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()

    release = controller.grid_mouse_release_position(
        is_left_button=True,
        position=_Point(8, 0),
        drag_distance=4,
    )

    assert release is None
    assert state.press_position is None


def test_grid_mouse_release_returns_click_position_within_drag_threshold() -> None:
    """Release movement inside the drag threshold should activate hit testing."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()
    release_point = _Point(2, 1)

    release = controller.grid_mouse_release_position(
        is_left_button=True,
        position=release_point,
        drag_distance=4,
    )

    assert release is release_point
    assert state.press_position is None


def test_grid_mouse_release_command_skips_hit_test_for_drag() -> None:
    """Rejected releases should not ask the route projector for a scene hit."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()
    hit_points: list[GridPoint] = []

    def _unexpected_hit_test(point: GridPoint) -> OutputCanvasHitValidation:
        hit_points.append(point)
        return OutputCanvasHitValidation.rejected("unexpected_hit_test")

    command = controller.grid_mouse_release_command(
        is_left_button=True,
        position=_Point(8, 0),
        drag_distance=4,
        hit_at=_unexpected_hit_test,
        active_scene_overview=False,
    )

    assert command is None
    assert hit_points == []


def test_grid_mouse_release_command_returns_hit_activation_command() -> None:
    """Accepted releases should hit-test and convert the result into a command."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()
    release_point = _Point(1, 1)
    image_id = uuid4()
    hit_points: list[GridPoint] = []

    def _hit_test(point: GridPoint) -> OutputCanvasHitValidation:
        hit_points.append(point)
        return OutputCanvasHitValidation.final_output(
            image_id=image_id,
            source_key="source-a",
            set_index=2,
            scene_key=None,
        )

    command = controller.grid_mouse_release_command(
        is_left_button=True,
        position=release_point,
        drag_distance=4,
        hit_at=_hit_test,
        active_scene_overview=False,
    )

    assert hit_points == [release_point]
    assert command == ActivateFinalOutputGridCommand(
        source_key="source-a",
        set_index=2,
        image_id=image_id,
    )


def test_grid_mouse_release_activation_resolves_final_output_item() -> None:
    """Final-output releases should resolve to the concrete output item."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()
    release_point = _Point(1, 1)
    image_id = uuid4()
    item = OutputCanvasImageItem(
        image_id,
        _meta(source_key="source-a"),
        2,
    )

    def _hit_test(point: GridPoint) -> OutputCanvasHitValidation:
        assert point is release_point
        return OutputCanvasHitValidation.final_output(
            image_id=image_id,
            source_key="source-a",
            set_index=2,
            scene_key=None,
        )

    command = controller.grid_mouse_release_activation(
        is_left_button=True,
        position=release_point,
        drag_distance=4,
        hit_at=_hit_test,
        active_scene_overview=False,
        source_groups_by_key={
            "source-a": OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={2: item},
            )
        },
    )

    assert command == ActivateFinalOutputItemGridCommand(
        source_key="source-a",
        item=item,
    )


def test_grid_mouse_release_activation_returns_scene_command() -> None:
    """Scene overview releases should pass through scene activation commands."""

    state = _InteractionState(press_position=_Point(0, 0))
    controller = state.controller()

    command = controller.grid_mouse_release_activation(
        is_left_button=True,
        position=_Point(1, 1),
        drag_distance=4,
        hit_at=lambda _point: OutputCanvasHitValidation.scene(scene_key="cafe"),
        active_scene_overview=True,
        source_groups_by_key={},
    )

    assert command == ActivateSceneGridCommand(scene_key="cafe")


def test_grid_activation_command_returns_scene_command_in_overview() -> None:
    """Accepted scene hits should become scene activation commands in overview mode."""

    command = OutputCanvasInteractionController.grid_activation_command(
        OutputCanvasHitValidation.scene(scene_key="cafe"),
        active_scene_overview=True,
    )

    assert command == ActivateSceneGridCommand(scene_key="cafe")


def test_grid_activation_command_returns_final_output_command() -> None:
    """Accepted final-output hits should become final-output activation commands."""

    image_id = uuid4()

    command = OutputCanvasInteractionController.grid_activation_command(
        OutputCanvasHitValidation.final_output(
            image_id=image_id,
            source_key="source-a",
            set_index=2,
            scene_key=None,
        ),
        active_scene_overview=False,
    )

    assert command == ActivateFinalOutputGridCommand(
        source_key="source-a",
        set_index=2,
        image_id=image_id,
    )


def test_grid_activation_command_rejects_mismatched_or_rejected_hits() -> None:
    """Rejected hits and wrong-mode hits should not produce activation commands."""

    assert (
        OutputCanvasInteractionController.grid_activation_command(
            OutputCanvasHitValidation.rejected("missing_hit"),
            active_scene_overview=False,
        )
        is None
    )
    assert (
        OutputCanvasInteractionController.grid_activation_command(
            OutputCanvasHitValidation.scene(scene_key="cafe"),
            active_scene_overview=False,
        )
        is None
    )


def test_final_output_item_for_command_prefers_source_set_item() -> None:
    """Final-output commands should resolve the clicked source/set item first."""

    image_id = uuid4()
    item = OutputCanvasImageItem(
        image_id,
        _meta(source_key="source-a"),
        2,
    )
    command = ActivateFinalOutputGridCommand(
        source_key="source-a",
        set_index=2,
        image_id=uuid4(),
    )

    resolved = OutputCanvasInteractionController.final_output_item_for_command(
        command,
        {
            "source-a": OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={2: item},
            )
        },
    )

    assert resolved == ("source-a", item)


def test_final_output_item_for_command_falls_back_to_image_id() -> None:
    """Final-output commands should recover by image id when set metadata is stale."""

    image_id = uuid4()
    item = OutputCanvasImageItem(
        image_id,
        _meta(source_key="source-b"),
        4,
    )
    command = ActivateFinalOutputGridCommand(
        source_key="source-a",
        set_index=2,
        image_id=image_id,
    )

    resolved = OutputCanvasInteractionController.final_output_item_for_command(
        command,
        {
            "source-b": OutputCanvasSourceGroup(
                source_key="source-b",
                label="Source B",
                images_by_set={4: item},
            )
        },
    )

    assert resolved == ("source-b", item)


def test_set_grid_interaction_locked_selects_qpane_control_mode() -> None:
    """Grid interaction lock should select cursor mode and unlock should pan/zoom."""

    state = _InteractionState()
    controller = state.controller()

    controller.set_grid_interaction_locked(True)
    controller.set_grid_interaction_locked(False)

    assert state.control_modes == ["cursor", "panzoom"]


@dataclass(frozen=True, slots=True)
class _Point:
    """Small point double with Qt-like subtraction behavior."""

    x: int
    y: int

    def __sub__(self, other: GridPoint) -> _PointDelta:
        """Return the absolute delta from another point."""

        other_point = other
        if not isinstance(other_point, _Point):
            raise TypeError(type(other).__name__)
        return _PointDelta(
            abs(self.x - other_point.x),
            abs(self.y - other_point.y),
        )


@dataclass(frozen=True, slots=True)
class _PointDelta:
    """Small point delta double with a Qt-like Manhattan length."""

    x: int
    y: int

    def manhattanLength(self) -> int:  # noqa: N802
        """Return the Manhattan distance."""

        return self.x + self.y


@dataclass(slots=True)
class _InteractionState:
    """Mutable state backing an interaction controller double."""

    press_position: GridPoint | None = None
    control_modes: list[object] | None = None

    def controller(self) -> OutputCanvasInteractionController:
        """Return a controller wired to this state."""

        if self.control_modes is None:
            self.control_modes = []
        return OutputCanvasInteractionController(
            press_position=lambda: self.press_position,
            set_press_position=self._set_press_position,
            set_control_mode=self.control_modes.append,
            cursor_control_mode="cursor",
            panzoom_control_mode="panzoom",
        )

    def _set_press_position(self, position: GridPoint | None) -> None:
        """Record the current press position."""

        self.press_position = position


def _meta(*, source_key: str) -> ImageMeta:
    """Return minimal output metadata for interaction-controller tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label="Output",
    )
