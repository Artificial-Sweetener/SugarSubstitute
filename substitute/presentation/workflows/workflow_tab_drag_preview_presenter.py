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

"""Present animated workflow-tab drag previews without committing order."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPoint, QRect


class WorkflowTabPreviewItem(Protocol):
    """Describe tab-item operations needed for drag preview animation."""

    def routeKey(self) -> str | None:
        """Return the workflow route key."""

    def x(self) -> int:
        """Return current x-position."""

    def y(self) -> int:
        """Return current y-position."""

    def move(self, x: int, y: int) -> None:
        """Move the item immediately."""

    def raise_(self) -> None:
        """Raise the item above sibling tabs."""

    def slideTo(self, x: int, duration: int = 250) -> None:
        """Animate the item horizontally to x."""

    def set_orb_cutout_preview_progress(self, progress: float) -> None:
        """Set drag-preview cutout progress immediately from geometry."""


@dataclass(frozen=True, slots=True)
class WorkflowTabDragPreviewState:
    """Describe visual state produced by one drag preview frame."""

    orb_adjacent_route_key: str | None


class WorkflowTabDragPreviewPresenter:
    """Animate workflow tab drag previews using committed slot geometry."""

    def preview(
        self,
        *,
        items_by_workflow_id: Mapping[str, WorkflowTabPreviewItem],
        committed_order: Sequence[str],
        preview_order: Sequence[str],
        dragged_workflow_id: str,
        pointer_pos: QPoint,
        press_pos: QPoint,
        slot_rects: Sequence[QRect],
    ) -> WorkflowTabDragPreviewState:
        """Move dragged tab under pointer and displace siblings to preview slots."""

        dragged_item = items_by_workflow_id.get(dragged_workflow_id)
        if dragged_item is None or not slot_rects:
            return WorkflowTabDragPreviewState(orb_adjacent_route_key=None)
        try:
            origin_index = list(committed_order).index(dragged_workflow_id)
        except ValueError:
            return WorkflowTabDragPreviewState(orb_adjacent_route_key=None)
        if not 0 <= origin_index < len(slot_rects):
            return WorkflowTabDragPreviewState(orb_adjacent_route_key=None)

        origin_rect = slot_rects[origin_index]
        dx = pointer_pos.x() - press_pos.x()
        min_x = slot_rects[0].x()
        max_x = slot_rects[-1].x()
        next_x = max(min_x, min(max_x, origin_rect.x() + dx))
        dragged_item.move(next_x, dragged_item.y())
        dragged_item.raise_()

        for preview_index, workflow_id in enumerate(preview_order):
            if workflow_id == dragged_workflow_id:
                continue
            if not 0 <= preview_index < len(slot_rects):
                continue
            item = items_by_workflow_id.get(workflow_id)
            if item is None:
                continue
            item.slideTo(slot_rects[preview_index].x())
        owner = self._sync_cutout_preview_progress(
            items_by_workflow_id=items_by_workflow_id,
            committed_order=committed_order,
            preview_order=preview_order,
            dragged_workflow_id=dragged_workflow_id,
            dragged_x=next_x,
            slot_rects=slot_rects,
        )
        return WorkflowTabDragPreviewState(orb_adjacent_route_key=owner)

    def settle_to_committed_order(
        self,
        *,
        items_by_workflow_id: Mapping[str, WorkflowTabPreviewItem],
        committed_order: Sequence[str],
        slot_rects: Sequence[QRect],
    ) -> None:
        """Animate every tab back to its committed slot."""

        for index, workflow_id in enumerate(committed_order):
            if not 0 <= index < len(slot_rects):
                continue
            item = items_by_workflow_id.get(workflow_id)
            if item is None:
                continue
            item.slideTo(slot_rects[index].x())

    def cancel(
        self,
        *,
        items_by_workflow_id: Mapping[str, WorkflowTabPreviewItem],
        committed_order: Sequence[str],
        slot_rects: Sequence[QRect],
    ) -> None:
        """Cancel preview and settle all tabs to committed order."""

        self.settle_to_committed_order(
            items_by_workflow_id=items_by_workflow_id,
            committed_order=committed_order,
            slot_rects=slot_rects,
        )

    def _sync_cutout_preview_progress(
        self,
        *,
        items_by_workflow_id: Mapping[str, WorkflowTabPreviewItem],
        committed_order: Sequence[str],
        preview_order: Sequence[str],
        dragged_workflow_id: str,
        dragged_x: int,
        slot_rects: Sequence[QRect],
    ) -> str | None:
        """Set continuous drag-time cutout progress and return visual owner."""

        if not committed_order:
            return None

        progress_by_workflow_id = {
            workflow_id: 0.0 for workflow_id in items_by_workflow_id
        }
        if len(slot_rects) == 1:
            progress_by_workflow_id[committed_order[0]] = 1.0
        else:
            dragged_progress = self._first_slot_progress(dragged_x, slot_rects)
            committed_first = committed_order[0]
            if dragged_workflow_id == committed_first:
                progress_by_workflow_id[dragged_workflow_id] = dragged_progress
                successor_id = self._preview_successor(
                    dragged_workflow_id=dragged_workflow_id,
                    committed_order=committed_order,
                    preview_order=preview_order,
                )
                if successor_id is not None:
                    progress_by_workflow_id[successor_id] = 1.0 - dragged_progress
            else:
                progress_by_workflow_id[committed_first] = 1.0 - dragged_progress
                progress_by_workflow_id[dragged_workflow_id] = dragged_progress

        visual_owner: str | None = None
        visual_owner_progress = 0.0
        for workflow_id, item in items_by_workflow_id.items():
            progress = progress_by_workflow_id.get(workflow_id, 0.0)
            item.set_orb_cutout_preview_progress(progress)
            if progress > visual_owner_progress:
                visual_owner = workflow_id
                visual_owner_progress = progress
        return visual_owner

    def _first_slot_progress(self, x: int, slot_rects: Sequence[QRect]) -> float:
        """Return normalized first-slot occupancy for a tab at x."""

        first_x = slot_rects[0].x()
        second_x = slot_rects[1].x()
        span = max(1, second_x - first_x)
        return max(0.0, min(1.0, 1.0 - ((x - first_x) / span)))

    def _preview_successor(
        self,
        *,
        dragged_workflow_id: str,
        committed_order: Sequence[str],
        preview_order: Sequence[str],
    ) -> str | None:
        """Return the workflow that visually replaces a dragged first tab."""

        for workflow_id in preview_order:
            if workflow_id != dragged_workflow_id:
                return workflow_id
        return committed_order[1] if len(committed_order) > 1 else None


__all__ = [
    "WorkflowTabDragPreviewPresenter",
    "WorkflowTabDragPreviewState",
    "WorkflowTabPreviewItem",
]
