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

"""Own workflow-tab orb-adjacent cutout selection and transition policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class OrbAdjacentTabItem(Protocol):
    """Describe tab-item behavior needed for orb-adjacent cutout control."""

    def routeKey(self) -> str | None:
        """Return the tab route key."""

    def isHidden(self) -> bool:
        """Return whether the tab item is hidden."""

    def orb_cutout_progress(self) -> float:
        """Return the current cutout progress."""

    def set_orb_cutout_active(self, active: bool, *, animated: bool = True) -> None:
        """Set whether the tab should render with the orb cutout."""


@dataclass(frozen=True, slots=True)
class OrbAdjacencyResult:
    """Describe the outcome of one orb-adjacent cutout synchronization."""

    route_key: str | None
    owner_changed: bool
    progress_changed: bool


class WorkflowTabOrbAdjacencyController:
    """Synchronize workflow tab cutout ownership for committed and preview order."""

    def __init__(self, *, settings_route_key: str) -> None:
        """Create a controller with the shell-owned settings route key."""

        self._settings_route_key = settings_route_key

    def sync_committed(
        self,
        *,
        items: Sequence[OrbAdjacentTabItem],
        previous_route_key: str | None,
        initialized: bool,
        animated: bool,
    ) -> OrbAdjacencyResult:
        """Synchronize cutout ownership from committed visual order."""

        candidate = self._first_visible_workflow_tab(items)
        candidate_route_key = candidate.routeKey() if candidate is not None else None
        return self._sync_items(
            items=items,
            candidate=candidate,
            candidate_route_key=candidate_route_key,
            previous_route_key=previous_route_key,
            initialized=initialized,
            animated=animated,
        )

    def sync_preview(
        self,
        *,
        items_by_workflow_id: Mapping[str, OrbAdjacentTabItem],
        preview_order: Sequence[str],
        previous_route_key: str | None,
        initialized: bool,
        animated: bool,
    ) -> OrbAdjacencyResult:
        """Synchronize cutout ownership from transient preview order."""

        candidate: OrbAdjacentTabItem | None = None
        candidate_route_key: str | None = None
        for workflow_id in preview_order:
            item = items_by_workflow_id.get(workflow_id)
            if item is None or not self._is_visible_workflow_tab(item):
                continue
            candidate = item
            candidate_route_key = workflow_id
            break
        return self._sync_items(
            items=tuple(items_by_workflow_id.values()),
            candidate=candidate,
            candidate_route_key=candidate_route_key,
            previous_route_key=previous_route_key,
            initialized=initialized,
            animated=animated,
        )

    def _first_visible_workflow_tab(
        self,
        items: Sequence[OrbAdjacentTabItem],
    ) -> OrbAdjacentTabItem | None:
        """Return the first visible non-settings workflow tab."""

        for item in items:
            if self._is_visible_workflow_tab(item):
                return item
        return None

    def _is_visible_workflow_tab(self, item: OrbAdjacentTabItem) -> bool:
        """Return whether item can own the orb-adjacent cutout."""

        route_key = item.routeKey()
        return (
            bool(route_key)
            and route_key != self._settings_route_key
            and not item.isHidden()
        )

    def _sync_items(
        self,
        *,
        items: Sequence[OrbAdjacentTabItem],
        candidate: OrbAdjacentTabItem | None,
        candidate_route_key: str | None,
        previous_route_key: str | None,
        initialized: bool,
        animated: bool,
    ) -> OrbAdjacencyResult:
        """Apply cutout state to every item and return synchronization details."""

        owner_changed = previous_route_key != candidate_route_key
        sync_animated = animated and initialized
        progress_changed = False
        for item in items:
            progress_before = item.orb_cutout_progress()
            item.set_orb_cutout_active(item is candidate, animated=sync_animated)
            if not sync_animated and item.orb_cutout_progress() != progress_before:
                progress_changed = True
        return OrbAdjacencyResult(
            route_key=candidate_route_key,
            owner_changed=owner_changed,
            progress_changed=progress_changed,
        )


__all__ = [
    "OrbAdjacentTabItem",
    "OrbAdjacencyResult",
    "WorkflowTabOrbAdjacencyController",
]
