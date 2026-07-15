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

"""Verify Output canvas grid event adaptation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
from substitute.presentation.canvas.output.output_canvas_grid_event_controller import (
    OutputCanvasGridEventController,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    GridPoint,
    OutputCanvasInteractionController,
)


def test_grid_event_controller_activates_final_output_release() -> None:
    """Final-output grid releases should activate the resolved output item."""

    state = _GridEventState(active_set_index=0)
    item_id = uuid4()
    item = OutputCanvasImageItem(
        item_id,
        _meta(source_key="source-a"),
        2,
    )
    controller = state.controller(
        hit_at=lambda point: OutputCanvasHitValidation.final_output(
            image_id=item_id,
            source_key="source-a",
            set_index=2,
            scene_key=None,
        ),
        source_groups_by_key=lambda: {
            "source-a": OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={2: item},
            )
        },
    )

    assert controller.handle_event_filter("pane", _MouseEvent("press", 0, 0)) is False
    assert controller.handle_event_filter("pane", _MouseEvent("release", 1, 1)) is False

    assert state.activated_items == [("source-a", item)]


def test_grid_event_controller_emits_scene_and_grid_after_scene_activation() -> None:
    """Scene-grid releases should emit scene and grid changes after activation."""

    state = _GridEventState(
        active_scene_overview=True,
        active_set_index=1,
        active_source_key=None,
    )

    def _activate_scene(scene_key: str) -> bool:
        activated_scenes = state.activated_scenes
        assert activated_scenes is not None
        activated_scenes.append(scene_key)
        state.active_set_index = 0
        state.active_source_key = "source-a"
        return True

    controller = state.controller(
        hit_at=lambda point: OutputCanvasHitValidation.scene(scene_key="cafe"),
        activate_scene=_activate_scene,
    )

    controller.handle_event_filter("pane", _MouseEvent("press", 0, 0))
    controller.handle_event_filter("pane", _MouseEvent("release", 1, 1))

    assert state.activated_scenes == ["cafe"]
    assert state.scene_changed == [("cafe", False)]
    assert state.grid_changed == ["source-a"]


def test_grid_event_controller_ignores_non_mouse_events_without_type_lookup() -> None:
    """Non-mouse events should not ask the Qt event adapter for event details."""

    state = _GridEventState(active_set_index=0)
    event_type_calls: list[object] = []
    controller = state.controller(
        is_mouse_event=lambda _event: False,
        event_type=lambda event: event_type_calls.append(event),
    )

    assert controller.handle_event_filter("pane", object()) is False

    assert event_type_calls == []
    assert state.activated_items == []


@dataclass(frozen=True, slots=True)
class _Point:
    """Small point double with Qt-like subtraction behavior."""

    x: int
    y: int

    def __sub__(self, other: GridPoint) -> _PointDelta:
        """Return the absolute delta from another point."""

        if not isinstance(other, _Point):
            raise TypeError(type(other).__name__)
        return _PointDelta(abs(self.x - other.x), abs(self.y - other.y))


@dataclass(frozen=True, slots=True)
class _PointDelta:
    """Small point delta double with Qt-like Manhattan length."""

    x: int
    y: int

    def manhattanLength(self) -> int:  # noqa: N802
        """Return the Manhattan distance."""

        return self.x + self.y


@dataclass(frozen=True, slots=True)
class _MouseEvent:
    """Small mouse-event double for grid event controller tests."""

    event_type: object
    x: int
    y: int
    left_button: bool = True


@dataclass(slots=True)
class _GridEventState:
    """Mutable state backing a grid event controller under test."""

    active_scene_overview: bool = False
    active_set_index: int = 0
    active_source_key: str | None = "source-a"
    press_position: GridPoint | None = None
    activated_items: list[tuple[str, OutputCanvasImageItem]] | None = None
    activated_scenes: list[str] | None = None
    scene_changed: list[tuple[str, bool]] | None = None
    grid_changed: list[str] | None = None

    def controller(
        self,
        *,
        hit_at: Callable[[GridPoint], OutputCanvasHitValidation] | None = None,
        source_groups_by_key: (
            Callable[[], Mapping[str, OutputCanvasSourceGroup]] | None
        ) = None,
        activate_scene: Callable[[str], bool] | None = None,
        is_mouse_event: Callable[[object], bool] | None = None,
        event_type: Callable[[object], object] | None = None,
    ) -> OutputCanvasGridEventController:
        """Return a grid event controller wired to this state."""

        self.activated_items = []
        self.activated_scenes = []
        self.scene_changed = []
        self.grid_changed = []
        interaction_controller = OutputCanvasInteractionController(
            press_position=lambda: self.press_position,
            set_press_position=self._set_press_position,
            set_control_mode=lambda _mode: None,
            cursor_control_mode="cursor",
            panzoom_control_mode="panzoom",
        )
        return OutputCanvasGridEventController(
            interaction_controller=interaction_controller,
            watched_is_pane=lambda watched: watched == "pane",
            is_mouse_event=(
                is_mouse_event if is_mouse_event is not None else _event_is_mouse_event
            ),
            event_type=event_type if event_type is not None else _mouse_event_type,
            event_is_left_button=_mouse_event_is_left_button,
            event_position=_mouse_event_position,
            drag_distance=lambda: 4,
            hit_at=(
                hit_at
                if hit_at is not None
                else lambda _point: OutputCanvasHitValidation.rejected("missing_hit")
            ),
            active_scene_overview=lambda: self.active_scene_overview,
            active_set_index=lambda: self.active_set_index,
            active_source_key=lambda: self.active_source_key,
            source_groups_by_key=(
                source_groups_by_key if source_groups_by_key is not None else lambda: {}
            ),
            activate_scene=(
                activate_scene if activate_scene is not None else self._activate_scene
            ),
            activate_item=self._activate_item,
            emit_scene_changed=self._emit_scene_changed,
            emit_grid_changed=self._emit_grid_changed,
            press_type="press",
            release_type="release",
        )

    def _set_press_position(self, position: GridPoint | None) -> None:
        """Record the current press position."""

        self.press_position = position

    def _activate_scene(self, scene_key: str) -> bool:
        """Record scene activation."""

        assert self.activated_scenes is not None
        self.activated_scenes.append(scene_key)
        return True

    def _activate_item(
        self,
        source_key: str,
        item: OutputCanvasImageItem,
    ) -> None:
        """Record item activation."""

        assert self.activated_items is not None
        self.activated_items.append((source_key, item))

    def _emit_scene_changed(self, scene_key: str, overview: bool) -> None:
        """Record scene change signals."""

        assert self.scene_changed is not None
        self.scene_changed.append((scene_key, overview))

    def _emit_grid_changed(self, source_key: str) -> None:
        """Record grid change signals."""

        assert self.grid_changed is not None
        self.grid_changed.append(source_key)


def _meta(*, source_key: str) -> ImageMeta:
    """Return minimal output metadata for grid event tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label="Output",
    )


def _event_is_mouse_event(event: object) -> bool:
    """Return whether the event is the mouse-event test double."""

    return isinstance(event, _MouseEvent)


def _mouse_event_type(event: object) -> object:
    """Return the event type from a mouse-event test double."""

    if not isinstance(event, _MouseEvent):
        raise TypeError(type(event).__name__)
    return event.event_type


def _mouse_event_is_left_button(event: object) -> bool:
    """Return whether the mouse-event test double used the left button."""

    if not isinstance(event, _MouseEvent):
        raise TypeError(type(event).__name__)
    return event.left_button


def _mouse_event_position(event: object) -> GridPoint:
    """Return the point from a mouse-event test double."""

    if not isinstance(event, _MouseEvent):
        raise TypeError(type(event).__name__)
    return _Point(event.x, event.y)
