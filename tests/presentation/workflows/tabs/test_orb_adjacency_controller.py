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

"""Contract tests for workflow-tab orb adjacency ownership policy."""

from __future__ import annotations

from substitute.presentation.workflows.workflow_tab_orb_adjacency_controller import (
    WorkflowTabOrbAdjacencyController,
)


class _Item:
    """Fake tab item recording orb cutout transitions."""

    def __init__(
        self,
        route_key: str,
        *,
        hidden: bool = False,
        progress: float = 0.0,
    ) -> None:
        """Create a fake tab item."""

        self._route_key = route_key
        self._hidden = hidden
        self._progress = progress
        self.calls: list[tuple[bool, bool]] = []

    def routeKey(self) -> str:
        """Return the route key."""

        return self._route_key

    def isHidden(self) -> bool:
        """Return whether this item is hidden."""

        return self._hidden

    def orb_cutout_progress(self) -> float:
        """Return current fake cutout progress."""

        return self._progress

    def set_orb_cutout_active(self, active: bool, *, animated: bool = True) -> None:
        """Record one cutout transition."""

        self.calls.append((active, animated))
        if not animated:
            self._progress = 1.0 if active else 0.0


def test_sync_committed_selects_first_visible_workflow_immediately() -> None:
    """Committed sync should ignore settings and hidden tabs."""

    settings = _Item("settings")
    hidden = _Item("wf-hidden", hidden=True, progress=1.0)
    first = _Item("wf-a")
    second = _Item("wf-b")
    controller = WorkflowTabOrbAdjacencyController(settings_route_key="settings")

    result = controller.sync_committed(
        items=(settings, hidden, first, second),
        previous_route_key=None,
        initialized=True,
        animated=False,
    )

    assert result.route_key == "wf-a"
    assert result.owner_changed is True
    assert result.progress_changed is True
    assert settings.calls == [(False, False)]
    assert hidden.calls == [(False, False)]
    assert first.calls == [(True, False)]
    assert second.calls == [(False, False)]
    assert first.orb_cutout_progress() == 1.0
    assert hidden.orb_cutout_progress() == 0.0


def test_sync_preview_uses_preview_order_with_animation() -> None:
    """Preview sync should animate ownership toward the preview first tab."""

    first = _Item("wf-a", progress=1.0)
    dragged = _Item("wf-b")
    controller = WorkflowTabOrbAdjacencyController(settings_route_key="settings")

    result = controller.sync_preview(
        items_by_workflow_id={"wf-a": first, "wf-b": dragged},
        preview_order=("wf-b", "wf-a"),
        previous_route_key="wf-a",
        initialized=True,
        animated=True,
    )

    assert result.route_key == "wf-b"
    assert result.owner_changed is True
    assert dragged.calls == [(True, True)]
    assert first.calls == [(False, True)]


def test_sync_committed_reports_no_owner_when_all_items_filtered() -> None:
    """No visible workflow tabs should clear orb ownership."""

    settings = _Item("settings", progress=1.0)
    hidden = _Item("wf-hidden", hidden=True, progress=1.0)
    controller = WorkflowTabOrbAdjacencyController(settings_route_key="settings")

    result = controller.sync_committed(
        items=(settings, hidden),
        previous_route_key="wf-hidden",
        initialized=True,
        animated=False,
    )

    assert result.route_key is None
    assert result.owner_changed is True
    assert settings.orb_cutout_progress() == 0.0
    assert hidden.orb_cutout_progress() == 0.0
