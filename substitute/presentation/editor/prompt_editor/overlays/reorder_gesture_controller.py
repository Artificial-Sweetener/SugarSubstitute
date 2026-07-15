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

"""Own transient prompt reorder gesture state without painting or layout work."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF

from substitute.application.prompt_editor import PromptReorderDropTarget

from ..models import PromptReorderCancelIntent, PromptReorderCommitIntent
from ..projection.reorder_state import (
    PromptReorderKeyboardState,
    PromptReorderPointerState,
)


PromptReorderDragPhase = Literal["start", "move", "end"]


@dataclass(frozen=True, slots=True)
class PromptReorderDragIntent:
    """Describe one pointer drag gesture emitted by the reorder overlay."""

    phase: PromptReorderDragPhase
    segment_index: int
    global_position: QPoint


@dataclass(frozen=True, slots=True)
class PromptReorderGestureSnapshot:
    """Expose the current gesture state as an immutable diagnostic snapshot."""

    active_segment_index: int | None
    hovered_segment_index: int | None
    pressed_segment_index: int | None
    base_drag_segment_index: int | None
    dragged_segment_index: int | None
    committed_dragged_segment_index: int | None
    active_drop_target: PromptReorderDropTarget | None
    keyboard_preferred_x: float | None
    last_drag_global_position: QPoint | None
    drag_grab_offset: QPointF | None
    drag_intent_size: QSizeF | None
    last_drag_intent_rect: QRectF | None


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyPlacementContext:
    """Describe geometry needed to position the drag proxy near the pointer."""

    pointer_global_position: QPoint
    pointer_host_position: QPoint
    proxy_size: QSize
    editor_rect_in_host: QRect
    host_rect: QRect


class PromptReorderGestureStateView:
    """Expose cheap read-only access to current reorder gesture state."""

    def __init__(self, controller: PromptReorderGestureController) -> None:
        """Bind the view to its authoritative gesture controller."""

        self._controller = controller

    @property
    def active_segment_index(self) -> int | None:
        """Return the segment currently active for keyboard reorder."""

        return self._controller._active_segment_index

    @property
    def hovered_segment_index(self) -> int | None:
        """Return the segment currently hovered by the pointer."""

        return self._controller._hovered_segment_index

    @property
    def pressed_segment_index(self) -> int | None:
        """Return the segment currently held by pointer press."""

        return self._controller._pressed_segment_index

    @property
    def base_drag_segment_index(self) -> int | None:
        """Return the segment used to build the current base drag layout."""

        return self._controller._base_drag_segment_index

    @property
    def dragged_segment_index(self) -> int | None:
        """Return the segment currently being pointer-dragged."""

        return self._controller._dragged_segment_index

    @property
    def committed_dragged_segment_index(self) -> int | None:
        """Return the segment most recently dropped into the preview layout."""

        return self._controller._committed_dragged_segment_index

    @property
    def active_drop_target(self) -> PromptReorderDropTarget | None:
        """Return the active prepared drop target selected by the overlay."""

        return self._controller._active_drop_target

    @property
    def keyboard_preferred_x(self) -> float | None:
        """Return the x-coordinate preserved during vertical keyboard movement."""

        return self._controller._keyboard_preferred_x

    @property
    def last_drag_global_position(self) -> QPoint | None:
        """Return the last global pointer position observed during dragging."""

        return self._controller._last_drag_global_position

    @property
    def drag_grab_offset(self) -> QPointF | None:
        """Return the pointer offset inside the source chip at drag start."""

        return self._controller._drag_grab_offset

    @property
    def drag_intent_size(self) -> QSizeF | None:
        """Return the logical source chip size captured at drag start."""

        return self._controller._drag_intent_size

    @property
    def last_drag_intent_rect(self) -> QRectF | None:
        """Return the most recent logical held-chip rect used for target selection."""

        return self._controller._last_drag_intent_rect

    def pointer_state(self) -> PromptReorderPointerState:
        """Return pointer reorder state without exposing controller internals."""

        return self._controller.pointer_state()

    def keyboard_state(self) -> PromptReorderKeyboardState:
        """Return keyboard reorder state without exposing controller internals."""

        return self._controller.keyboard_state()


class PromptReorderGestureController:
    """Own pointer, keyboard, and target state for prompt segment reordering."""

    def __init__(self) -> None:
        """Initialize an empty reorder gesture state."""

        self._active_segment_index: int | None = None
        self._hovered_segment_index: int | None = None
        self._pressed_segment_index: int | None = None
        self._base_drag_segment_index: int | None = None
        self._dragged_segment_index: int | None = None
        self._committed_dragged_segment_index: int | None = None
        self._active_drop_target: PromptReorderDropTarget | None = None
        self._keyboard_preferred_x: float | None = None
        self._last_drag_global_position: QPoint | None = None
        self._drag_grab_offset: QPointF | None = None
        self._drag_intent_size: QSizeF | None = None
        self._last_drag_intent_rect: QRectF | None = None
        self.state = PromptReorderGestureStateView(self)

    def snapshot(self) -> PromptReorderGestureSnapshot:
        """Return an immutable copy of the current gesture state."""

        return PromptReorderGestureSnapshot(
            active_segment_index=self._active_segment_index,
            hovered_segment_index=self._hovered_segment_index,
            pressed_segment_index=self._pressed_segment_index,
            base_drag_segment_index=self._base_drag_segment_index,
            dragged_segment_index=self._dragged_segment_index,
            committed_dragged_segment_index=self._committed_dragged_segment_index,
            active_drop_target=self._active_drop_target,
            keyboard_preferred_x=self._keyboard_preferred_x,
            last_drag_global_position=self._last_drag_global_position,
            drag_grab_offset=self._drag_grab_offset,
            drag_intent_size=self._drag_intent_size,
            last_drag_intent_rect=self._last_drag_intent_rect,
        )

    def pointer_state(self) -> PromptReorderPointerState:
        """Return the current pointer state as a non-widget projection value."""

        return PromptReorderPointerState(
            hovered_segment_index=self._hovered_segment_index,
            pressed_segment_index=self._pressed_segment_index,
            base_drag_segment_index=self._base_drag_segment_index,
            dragged_segment_index=self._dragged_segment_index,
            committed_dragged_segment_index=self._committed_dragged_segment_index,
            active_drop_target=self._active_drop_target,
            last_drag_global_position=self._last_drag_global_position,
            drag_grab_offset=self._drag_grab_offset,
            drag_intent_size=self._drag_intent_size,
            last_drag_intent_rect=self._last_drag_intent_rect,
        )

    def keyboard_state(self) -> PromptReorderKeyboardState:
        """Return the current keyboard state as a non-widget projection value."""

        return PromptReorderKeyboardState(
            active_segment_index=self._active_segment_index,
            base_drag_segment_index=self._base_drag_segment_index,
            active_drop_target=self._active_drop_target,
            keyboard_preferred_x=self._keyboard_preferred_x,
        )

    def reset_all(self) -> None:
        """Clear all reorder gesture state when a new segment set is loaded."""

        self._active_segment_index = None
        self._hovered_segment_index = None
        self._pressed_segment_index = None
        self._base_drag_segment_index = None
        self._dragged_segment_index = None
        self._committed_dragged_segment_index = None
        self._active_drop_target = None
        self._keyboard_preferred_x = None
        self.clear_pointer_drag()
        self.clear_drag_intent_context()

    def set_hovered_segment(self, segment_index: int | None) -> bool:
        """Update pointer hover state and report whether it changed."""

        if self._dragged_segment_index is not None and segment_index is None:
            return False
        if self._hovered_segment_index == segment_index:
            return False
        self._hovered_segment_index = segment_index
        return True

    def activate_segment(self, segment_index: int) -> None:
        """Set the segment that should retain focus for keyboard reorder."""

        self._active_segment_index = segment_index

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Set the pointer-pressed segment state."""

        self._pressed_segment_index = segment_index

    def begin_pointer_drag(
        self,
        *,
        segment_index: int,
        global_position: QPoint,
    ) -> bool:
        """Start a pointer drag if no other pointer drag is active."""

        if self._dragged_segment_index is not None:
            return False
        self._active_segment_index = segment_index
        self._hovered_segment_index = segment_index
        self._base_drag_segment_index = segment_index
        self._dragged_segment_index = segment_index
        self._committed_dragged_segment_index = None
        self._active_drop_target = None
        self._last_drag_global_position = global_position
        return True

    def update_pointer_drag_position(self, global_position: QPoint) -> None:
        """Record the latest pointer position for drag and autoscroll consumers."""

        self._last_drag_global_position = global_position

    def finish_pointer_drag(
        self,
        *,
        committed_segment_index: int | None,
        clear_target: bool,
    ) -> None:
        """Clear active pointer drag state after release."""

        self._pressed_segment_index = None
        self._dragged_segment_index = None
        self._last_drag_global_position = None
        if committed_segment_index is not None:
            self._committed_dragged_segment_index = committed_segment_index
        if clear_target:
            self._active_drop_target = None

    def cancel_drag(self) -> None:
        """Clear active drag, target, and commit state after cancellation."""

        self._pressed_segment_index = None
        self._dragged_segment_index = None
        self._committed_dragged_segment_index = None
        self._active_drop_target = None
        self._last_drag_global_position = None
        self.clear_drag_intent_context()

    def clear_pointer_drag(self) -> None:
        """Clear transient pointer drag state without changing keyboard focus."""

        self._pressed_segment_index = None
        self._dragged_segment_index = None
        self._last_drag_global_position = None

    def set_base_drag_segment(self, segment_index: int | None) -> None:
        """Set the segment index used for the current base-drag layout."""

        self._base_drag_segment_index = segment_index

    def clear_base_drag_segment(self) -> None:
        """Clear the base-drag segment owner state."""

        self._base_drag_segment_index = None

    def set_active_drop_target(
        self,
        target: PromptReorderDropTarget | None,
    ) -> bool:
        """Store the selected prepared drop target and report whether it changed."""

        if self._active_drop_target == target:
            return False
        self._active_drop_target = target
        return True

    def set_committed_dragged_segment(self, segment_index: int | None) -> None:
        """Set the most recently committed dragged segment."""

        self._committed_dragged_segment_index = segment_index

    def set_keyboard_preferred_x(self, preferred_x: float | None) -> None:
        """Set the horizontal anchor used by vertical keyboard reorder."""

        self._keyboard_preferred_x = preferred_x

    def clear_keyboard_preferred_x(self) -> None:
        """Clear vertical keyboard reorder horizontal anchoring."""

        self._keyboard_preferred_x = None

    def capture_drag_intent_context(
        self,
        *,
        chip_rect: QRectF,
        local_pointer: QPointF,
    ) -> None:
        """Capture logical held-chip geometry for pointer target resolution."""

        self._drag_grab_offset = local_pointer - chip_rect.topLeft()
        self._drag_intent_size = chip_rect.size()
        self._last_drag_intent_rect = None

    def set_last_drag_intent_rect(self, intent_rect: QRectF | None) -> None:
        """Store the latest logical held-chip rect used by target selection."""

        self._last_drag_intent_rect = intent_rect

    def clear_drag_intent_context(self) -> None:
        """Clear logical held-chip geometry captured for pointer target resolution."""

        self._drag_grab_offset = None
        self._drag_intent_size = None
        self._last_drag_intent_rect = None


class PromptReorderDragProxyPlacementController:
    """Calculate drag-proxy placement from pointer and host geometry only."""

    def __init__(
        self,
        *,
        escape_margin: int = 16,
        pointer_overlap: int = 4,
        host_margin: int = 8,
        timing_hook: Callable[[str, PromptReorderDragProxyPlacementContext], None]
        | None = None,
    ) -> None:
        """Initialize proxy placement policy with bounded host margins."""

        self._escape_margin = escape_margin
        self._pointer_overlap = pointer_overlap
        self._host_margin = host_margin
        self._timing_hook = timing_hook

    def proxy_rect_for_pointer(
        self,
        context: PromptReorderDragProxyPlacementContext,
    ) -> QRect:
        """Return one host-local drag-proxy rect that stays close to the pointer."""

        if self._timing_hook is not None:
            self._timing_hook("drag_proxy.rect_for_pointer", context)
        available_rect = context.editor_rect_in_host.adjusted(
            -self._escape_margin,
            -self._escape_margin,
            self._escape_margin,
            self._escape_margin,
        )
        host_safe_rect = context.host_rect.adjusted(
            self._host_margin,
            self._host_margin,
            -self._host_margin,
            -self._host_margin,
        )
        available_rect = available_rect.intersected(host_safe_rect)
        if available_rect.width() <= 0 or available_rect.height() <= 0:
            return QRect(context.pointer_host_position, context.proxy_size)

        left = context.pointer_host_position.x() - (context.proxy_size.width() // 2)
        top = (
            context.pointer_host_position.y()
            - context.proxy_size.height()
            + self._pointer_overlap
        )
        if top < available_rect.top():
            top = context.pointer_host_position.y() - self._pointer_overlap

        clamped_left = max(
            available_rect.left(),
            min(left, available_rect.right() - context.proxy_size.width()),
        )
        clamped_top = max(
            available_rect.top(),
            min(top, available_rect.bottom() - context.proxy_size.height()),
        )
        return QRect(QPoint(clamped_left, clamped_top), context.proxy_size)


__all__ = [
    "PromptReorderCancelIntent",
    "PromptReorderCommitIntent",
    "PromptReorderDragIntent",
    "PromptReorderDragPhase",
    "PromptReorderDragProxyPlacementContext",
    "PromptReorderDragProxyPlacementController",
    "PromptReorderGestureController",
    "PromptReorderGestureSnapshot",
    "PromptReorderGestureStateView",
]
