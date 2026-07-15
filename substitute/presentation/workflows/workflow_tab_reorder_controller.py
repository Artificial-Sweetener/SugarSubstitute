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

"""Compute workflow-tab reorder targets and commit commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPoint, QRect


class WorkflowTabReorderGeometry(Protocol):
    """Expose workflow-tab geometry without coupling to the concrete widget."""

    def workflow_ids_in_order(self) -> list[str]:
        """Return workflow ids in current rendered order."""

    def workflow_tab_rect_by_id(self, workflow_id: str) -> QRect | None:
        """Return the current tab rect for workflow_id."""


@dataclass(frozen=True)
class WorkflowTabReorderPreview:
    """Describe one drag preview position for a workflow tab."""

    workflow_id: str
    origin_index: int
    target_index: int
    pointer_pos: QPoint
    preview_order: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowTabMoveCommand:
    """Command one authoritative workflow-tab order mutation."""

    workflow_id: str
    target_index: int
    preview_order: tuple[str, ...]


class WorkflowTabReorderController:
    """Resolve drag positions into workflow-tab reorder commands."""

    def __init__(self, geometry: WorkflowTabReorderGeometry) -> None:
        """Create a reorder controller with tab geometry access."""

        self._geometry = geometry
        self._preview: WorkflowTabReorderPreview | None = None

    def preview(
        self,
        *,
        workflow_id: str,
        origin_index: int,
        pointer_pos: QPoint,
    ) -> WorkflowTabReorderPreview:
        """Return and store the current reorder preview target."""

        target_index = self.target_index_for_pointer(workflow_id, pointer_pos)
        preview_order = self.preview_order(
            workflow_id=workflow_id,
            target_index=target_index,
        )
        self._preview = WorkflowTabReorderPreview(
            workflow_id=workflow_id,
            origin_index=origin_index,
            target_index=target_index,
            pointer_pos=QPoint(pointer_pos),
            preview_order=preview_order,
        )
        return self._preview

    def finish(
        self,
        *,
        workflow_id: str,
        origin_index: int,
        pointer_pos: QPoint,
    ) -> WorkflowTabMoveCommand | None:
        """Return the final move command for a completed drag."""

        preview = self.preview(
            workflow_id=workflow_id,
            origin_index=origin_index,
            pointer_pos=pointer_pos,
        )
        self.clear_preview()
        if preview.target_index == self._current_index(workflow_id):
            return None
        return WorkflowTabMoveCommand(
            workflow_id=workflow_id,
            target_index=preview.target_index,
            preview_order=preview.preview_order,
        )

    def clear_preview(self) -> None:
        """Forget any stored drag preview."""

        self._preview = None

    def preview_order(self, *, workflow_id: str, target_index: int) -> tuple[str, ...]:
        """Return a transient order with workflow_id moved to target_index."""

        workflow_ids = self._geometry.workflow_ids_in_order()
        if workflow_id not in workflow_ids:
            return tuple(workflow_ids)
        reordered = [current for current in workflow_ids if current != workflow_id]
        clamped_index = max(0, min(target_index, len(reordered)))
        reordered.insert(clamped_index, workflow_id)
        return tuple(reordered)

    def target_index_for_pointer(self, workflow_id: str, pointer_pos: QPoint) -> int:
        """Return the target workflow index nearest to pointer_pos."""

        workflow_ids = self._geometry.workflow_ids_in_order()
        if not workflow_ids:
            return -1

        current_index = self._current_index(workflow_id)
        if current_index < 0:
            return -1

        centers: list[tuple[int, int]] = []
        for index, current_workflow_id in enumerate(workflow_ids):
            rect = self._geometry.workflow_tab_rect_by_id(current_workflow_id)
            if rect is not None:
                centers.append((index, rect.center().x()))

        if not centers:
            return current_index

        pointer_x = pointer_pos.x()
        for index, center_x in centers:
            if pointer_x < center_x:
                return index
        return centers[-1][0]

    def _current_index(self, workflow_id: str) -> int:
        """Return the current workflow index or -1 when absent."""

        try:
            return self._geometry.workflow_ids_in_order().index(workflow_id)
        except ValueError:
            return -1


__all__ = [
    "WorkflowTabMoveCommand",
    "WorkflowTabReorderController",
    "WorkflowTabReorderGeometry",
    "WorkflowTabReorderPreview",
]
