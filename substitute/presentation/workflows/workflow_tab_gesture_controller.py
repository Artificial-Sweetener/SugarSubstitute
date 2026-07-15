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

"""Own workflow-tab mouse gesture state and enforce drag invariants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


class WorkflowTabGestureKind(Enum):
    """Describe the current workflow-tab gesture state."""

    IDLE = "idle"
    LEFT_PRESSED = "left_pressed"
    DRAGGING = "dragging"
    CONTEXT_MENU_OPEN = "context_menu_open"


class WorkflowTabGestureResultKind(Enum):
    """Describe the semantic result of one mouse gesture transition."""

    NONE = "none"
    DRAG_STARTED = "drag_started"
    DRAG_UPDATED = "drag_updated"
    DRAG_FINISHED = "drag_finished"
    DRAG_CANCELLED = "drag_cancelled"


class WorkflowTabHitTester(Protocol):
    """Provide workflow-tab hit testing without coupling to the tab widget."""

    def workflow_tab_id_at(self, pos: QPoint) -> str | None:
        """Return the workflow id at pos, excluding non-tab zones."""

    def workflow_tab_index(self, workflow_id: str) -> int:
        """Return the current rendered index for workflow_id."""

    def is_draggable_workflow_tab(self, workflow_id: str) -> bool:
        """Return whether workflow_id may participate in drag reorder."""


@dataclass(frozen=True)
class WorkflowTabDragCandidate:
    """Store the left-button candidate that may become a reorder drag."""

    workflow_id: str
    origin_index: int
    press_pos: QPoint
    last_pos: QPoint


@dataclass(frozen=True)
class WorkflowTabGestureResult:
    """Describe one workflow-tab gesture transition for the owning widget."""

    kind: WorkflowTabGestureResultKind
    workflow_id: str | None = None
    origin_index: int | None = None
    press_pos: QPoint | None = None
    current_pos: QPoint | None = None

    @classmethod
    def none(cls) -> "WorkflowTabGestureResult":
        """Return a no-op gesture result."""

        return cls(WorkflowTabGestureResultKind.NONE)


class WorkflowTabGestureController:
    """Convert raw workflow-tab mouse events into safe semantic gestures."""

    def __init__(self, hit_tester: WorkflowTabHitTester) -> None:
        """Create a controller with widget-owned hit testing."""

        self._hit_tester = hit_tester
        self._kind = WorkflowTabGestureKind.IDLE
        self._candidate: WorkflowTabDragCandidate | None = None

    def is_idle(self) -> bool:
        """Return whether no workflow-tab gesture is active."""

        return self._kind == WorkflowTabGestureKind.IDLE and self._candidate is None

    def cancel(self) -> None:
        """Return to idle and discard any pending or active drag state."""

        self._kind = WorkflowTabGestureKind.IDLE
        self._candidate = None

    def open_context_menu(self) -> None:
        """Cancel pointer gestures before a context menu opens."""

        self.cancel()
        self._kind = WorkflowTabGestureKind.CONTEXT_MENU_OPEN
        self.cancel()

    def handle_mouse_press(self, event: QMouseEvent) -> WorkflowTabGestureResult:
        """Handle a tab-strip mouse press and arm valid left-drag candidates."""

        event_pos = self._event_pos(event)
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return WorkflowTabGestureResult(WorkflowTabGestureResultKind.DRAG_CANCELLED)

        if event.button() != Qt.MouseButton.LeftButton:
            self.cancel()
            return WorkflowTabGestureResult.none()

        workflow_id = self._hit_tester.workflow_tab_id_at(event_pos)
        if workflow_id is None or not self._hit_tester.is_draggable_workflow_tab(
            workflow_id
        ):
            self.cancel()
            return WorkflowTabGestureResult.none()

        origin_index = self._hit_tester.workflow_tab_index(workflow_id)
        if origin_index < 0:
            self.cancel()
            return WorkflowTabGestureResult.none()

        self._kind = WorkflowTabGestureKind.LEFT_PRESSED
        self._candidate = WorkflowTabDragCandidate(
            workflow_id=workflow_id,
            origin_index=origin_index,
            press_pos=QPoint(event_pos),
            last_pos=QPoint(event_pos),
        )
        return WorkflowTabGestureResult.none()

    def handle_mouse_move(self, event: QMouseEvent) -> WorkflowTabGestureResult:
        """Handle a tab-strip mouse move and update only valid left drags."""

        if self._candidate is None:
            return WorkflowTabGestureResult.none()

        event_pos = self._event_pos(event)
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self.cancel()
            return WorkflowTabGestureResult(WorkflowTabGestureResultKind.DRAG_CANCELLED)

        if self._kind == WorkflowTabGestureKind.LEFT_PRESSED:
            if not self._movement_reaches_drag_threshold(event_pos):
                return WorkflowTabGestureResult.none()
            self._kind = WorkflowTabGestureKind.DRAGGING
            self._candidate = self._candidate_with_last_pos(event_pos)
            return self._drag_result(WorkflowTabGestureResultKind.DRAG_STARTED)

        if self._kind != WorkflowTabGestureKind.DRAGGING:
            return WorkflowTabGestureResult.none()

        self._candidate = self._candidate_with_last_pos(event_pos)
        return self._drag_result(WorkflowTabGestureResultKind.DRAG_UPDATED)

    def handle_mouse_release(self, event: QMouseEvent) -> WorkflowTabGestureResult:
        """Handle mouse release and finalize only active left-button drags."""

        if self._candidate is None:
            self.cancel()
            return WorkflowTabGestureResult.none()

        event_pos = self._event_pos(event)
        if self._kind == WorkflowTabGestureKind.LEFT_PRESSED:
            self.cancel()
            return WorkflowTabGestureResult.none()

        if (
            self._kind != WorkflowTabGestureKind.DRAGGING
            or event.button() != Qt.MouseButton.LeftButton
        ):
            self.cancel()
            return WorkflowTabGestureResult(WorkflowTabGestureResultKind.DRAG_CANCELLED)

        result = self._drag_result(
            WorkflowTabGestureResultKind.DRAG_FINISHED,
            current_pos=event_pos,
        )
        self.cancel()
        return result

    @staticmethod
    def _event_pos(event: QMouseEvent) -> QPoint:
        """Return a stable integer position for one Qt mouse event."""

        return event.position().toPoint()

    def _movement_reaches_drag_threshold(self, pos: QPoint) -> bool:
        """Return whether pointer movement should become a drag."""

        if self._candidate is None:
            return False
        return (
            pos - self._candidate.press_pos
        ).manhattanLength() >= QApplication.startDragDistance()

    def _candidate_with_last_pos(self, pos: QPoint) -> WorkflowTabDragCandidate:
        """Return the current candidate with an updated pointer position."""

        if self._candidate is None:
            raise RuntimeError("Cannot update missing workflow tab drag candidate.")
        return WorkflowTabDragCandidate(
            workflow_id=self._candidate.workflow_id,
            origin_index=self._candidate.origin_index,
            press_pos=self._candidate.press_pos,
            last_pos=QPoint(pos),
        )

    def _drag_result(
        self,
        kind: WorkflowTabGestureResultKind,
        *,
        current_pos: QPoint | None = None,
    ) -> WorkflowTabGestureResult:
        """Return a drag result from the active candidate."""

        if self._candidate is None:
            return WorkflowTabGestureResult.none()
        result_pos = (
            current_pos if current_pos is not None else self._candidate.last_pos
        )
        return WorkflowTabGestureResult(
            kind=kind,
            workflow_id=self._candidate.workflow_id,
            origin_index=self._candidate.origin_index,
            press_pos=self._candidate.press_pos,
            current_pos=QPoint(result_pos),
        )


__all__ = [
    "WorkflowTabDragCandidate",
    "WorkflowTabGestureController",
    "WorkflowTabGestureKind",
    "WorkflowTabGestureResult",
    "WorkflowTabGestureResultKind",
    "WorkflowTabHitTester",
]
