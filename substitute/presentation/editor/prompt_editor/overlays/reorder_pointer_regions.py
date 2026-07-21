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

"""Own logical pointer regions and gesture ingress for prompt reorder chips."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor import PromptReorderChipView


@dataclass(slots=True)
class PromptReorderPointerRegion:
    """Represent one visible chip hotspot without allocating a child widget."""

    segment: PromptReorderChipView
    rect: QRect = field(default_factory=QRect)
    visible: bool = False
    active: bool = False
    dragging: bool = False
    hovered: bool = False
    cursor_shape: Qt.CursorShape = Qt.CursorShape.OpenHandCursor

    @property
    def segment_index(self) -> int:
        """Return the stable semantic index represented by this region."""

        return self.segment.index

    def drag_proxy_text(self) -> str:
        """Return the complete label rendered by the floating drag proxy."""

        if self.segment.has_separator_after:
            return f"{self.segment.display_text},"
        return self.segment.display_text

    def set_visual_state(self, *, active: bool, dragging: bool, hovered: bool) -> None:
        """Store interaction state consumed by diagnostics and paint planning."""

        self.active = active
        self.dragging = dragging
        self.hovered = hovered

    def set_cursor_shape(self, cursor_shape: Qt.CursorShape) -> None:
        """Store the cursor required while this region owns pointer input."""

        self.cursor_shape = cursor_shape

    def set_geometry(self, rect: QRect) -> None:
        """Replace the overlay-local interactive bounds."""

        self.rect = QRect(rect)

    def set_visible(self, visible: bool) -> None:
        """Set whether the region can receive pointer interaction."""

        self.visible = visible

    def size(self) -> QSize:
        """Return the current region size for held-chip capture."""

        return self.rect.size()


class PromptReorderPointerRegions:
    """Maintain viewport-bounded logical chip regions and resolve hit tests."""

    def __init__(self) -> None:
        """Initialize an empty region collection."""

        self._segments_by_index: dict[int, PromptReorderChipView] = {}
        self._regions_by_index: dict[int, PromptReorderPointerRegion] = {}

    @property
    def regions_by_index(self) -> dict[int, PromptReorderPointerRegion]:
        """Return the stable mutable region map used by overlay presenters."""

        return self._regions_by_index

    def set_segments(self, segments: tuple[PromptReorderChipView, ...]) -> None:
        """Replace semantic segment metadata for the current reorder session."""

        self.clear()
        self._segments_by_index = {segment.index: segment for segment in segments}

    def sync(self, required_indices: set[int]) -> None:
        """Match logical regions to chips with interactive viewport geometry."""

        valid_indices = required_indices & self._segments_by_index.keys()
        for segment_index in tuple(self._regions_by_index.keys() - valid_indices):
            del self._regions_by_index[segment_index]
        for segment_index in sorted(valid_indices - self._regions_by_index.keys()):
            self._regions_by_index[segment_index] = PromptReorderPointerRegion(
                self._segments_by_index[segment_index]
            )

    def hit_test(
        self,
        position: QPointF,
        *,
        ordered_indices: tuple[int, ...],
    ) -> PromptReorderPointerRegion | None:
        """Return the topmost visible region containing an overlay-local point."""

        for segment_index in reversed(ordered_indices):
            region = self._regions_by_index.get(segment_index)
            if (
                region is not None
                and region.visible
                and region.rect.contains(position.toPoint())
            ):
                return region
        return None

    def clear(self) -> None:
        """Discard all materialized regions from the current session."""

        self._regions_by_index.clear()


class PromptReorderPointerController(Protocol):
    """Receive semantic pointer gestures from the single overlay input surface."""

    def set_hovered_segment(self, segment_index: int | None) -> None:
        """Track the segment currently under the pointer."""

    def activate_segment(self, segment_index: int) -> None:
        """Track the segment that should retain selection after commit."""

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Track the segment whose pointer press is currently held."""

    def prepare_drag(self, segment_index: int) -> None:
        """Prepare immutable drag state before threshold crossing."""

    def start_drag(
        self,
        segment_index: int,
        *,
        global_pos: QPoint,
        press_global_pos: QPoint,
    ) -> None:
        """Begin dragging one semantic segment."""

    def drag_move(self, segment_index: int, global_pos: QPoint) -> None:
        """Update an active semantic drag."""

    def end_drag(self, segment_index: int) -> None:
        """Finish an active semantic drag."""

    def retain_editor_focus(self) -> None:
        """Keep keyboard focus on the underlying editor."""

    def set_pointer_cursor(self, cursor_shape: Qt.CursorShape) -> None:
        """Apply the cursor selected by the logical pointer owner."""

    def log_interaction_event(self, event: str, **context: object) -> None:
        """Record prompt-safe pointer telemetry."""


class PromptReorderPointerInput:
    """Translate mouse events on one overlay into semantic chip gestures."""

    def __init__(
        self,
        *,
        regions: PromptReorderPointerRegions,
        controller: PromptReorderPointerController,
    ) -> None:
        """Initialize pointer state for one reorder overlay."""

        self._regions = regions
        self._controller = controller
        self._pressed_segment_index: int | None = None
        self._press_global_pos: QPoint | None = None
        self._drag_started = False
        self._last_mouse_event_at: float | None = None

    def press(
        self,
        event: QMouseEvent,
        *,
        ordered_indices: tuple[int, ...],
    ) -> None:
        """Prime a semantic drag when a left press lands inside a chip region."""

        self._log_mouse_event("mouse.press", event)
        self._controller.retain_editor_focus()
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()
            return
        region = self._regions.hit_test(
            event.position(), ordered_indices=ordered_indices
        )
        if region is None:
            self._clear_press()
            self._controller.set_hovered_segment(None)
            self._controller.set_pointer_cursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        segment_index = region.segment_index
        self._pressed_segment_index = segment_index
        self._press_global_pos = event.globalPosition().toPoint()
        self._drag_started = False
        self._controller.activate_segment(segment_index)
        self._controller.set_pressed_segment(segment_index)
        self._controller.prepare_drag(segment_index)
        self._controller.set_pointer_cursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def move(
        self,
        event: QMouseEvent,
        *,
        ordered_indices: tuple[int, ...],
    ) -> None:
        """Update hover or the active semantic drag for one pointer move."""

        self._log_mouse_event("mouse.move", event)
        pressed_segment_index = self._pressed_segment_index
        if (
            not (event.buttons() & Qt.MouseButton.LeftButton)
            or pressed_segment_index is None
        ):
            region = self._regions.hit_test(
                event.position(), ordered_indices=ordered_indices
            )
            hovered_index = None if region is None else region.segment_index
            self._controller.set_hovered_segment(hovered_index)
            self._controller.set_pointer_cursor(
                Qt.CursorShape.ArrowCursor if region is None else region.cursor_shape
            )
            event.accept()
            return

        self._controller.retain_editor_focus()
        global_pos = event.globalPosition().toPoint()
        drag_distance = (
            0
            if self._press_global_pos is None
            else (global_pos - self._press_global_pos).manhattanLength()
        )
        if (
            not self._drag_started
            and self._press_global_pos is not None
            and drag_distance >= QApplication.startDragDistance()
        ):
            self._drag_started = True
            self._controller.log_interaction_event(
                "mouse.drag_threshold_crossed",
                segment_index=pressed_segment_index,
                global_x=global_pos.x(),
                global_y=global_pos.y(),
                drag_distance=drag_distance,
                threshold=QApplication.startDragDistance(),
            )
            self._controller.start_drag(
                pressed_segment_index,
                global_pos=global_pos,
                press_global_pos=self._press_global_pos,
            )
        elif self._drag_started:
            self._controller.drag_move(pressed_segment_index, global_pos)
        self._controller.set_pointer_cursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def release(self, event: QMouseEvent) -> None:
        """Finish a drag or clear its primed click state."""

        self._log_mouse_event("mouse.release", event)
        pressed_segment_index = self._pressed_segment_index
        if (
            event.button() == Qt.MouseButton.LeftButton
            and pressed_segment_index is not None
        ):
            self._controller.retain_editor_focus()
            if self._drag_started:
                self._controller.end_drag(pressed_segment_index)
            else:
                self._controller.set_pressed_segment(None)
            self._clear_press()
            self._controller.set_pointer_cursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

    def leave(self) -> None:
        """Clear hover when the pointer leaves and no drag owns the pointer."""

        if self._pressed_segment_index is not None:
            return
        self._controller.set_hovered_segment(None)
        self._controller.set_pointer_cursor(Qt.CursorShape.ArrowCursor)

    def reset(self) -> None:
        """Clear all pointer state when the reorder session ends."""

        self._clear_press()
        self._last_mouse_event_at = None

    def _clear_press(self) -> None:
        """Reset state that belongs to one mouse press."""

        self._pressed_segment_index = None
        self._press_global_pos = None
        self._drag_started = False

    def _log_mouse_event(self, event_name: str, event: QMouseEvent) -> None:
        """Record raw mouse ingress for drag performance attribution."""

        now = time.perf_counter()
        elapsed_since_previous_ms = (
            None
            if self._last_mouse_event_at is None
            else (now - self._last_mouse_event_at) * 1000.0
        )
        self._last_mouse_event_at = now
        global_pos = event.globalPosition().toPoint()
        drag_distance = (
            None
            if self._press_global_pos is None
            else (global_pos - self._press_global_pos).manhattanLength()
        )
        self._controller.log_interaction_event(
            event_name,
            segment_index=self._pressed_segment_index,
            button=str(event.button()),
            buttons=str(event.buttons()),
            global_x=global_pos.x(),
            global_y=global_pos.y(),
            drag_started=self._drag_started,
            drag_distance=drag_distance,
            elapsed_since_previous_ms=elapsed_since_previous_ms,
        )


__all__ = [
    "PromptReorderPointerInput",
    "PromptReorderPointerRegion",
    "PromptReorderPointerRegions",
]
