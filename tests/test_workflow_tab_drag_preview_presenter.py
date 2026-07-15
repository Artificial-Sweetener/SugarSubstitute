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

"""Contract tests for workflow-tab drag preview presentation."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect

from substitute.presentation.workflows.workflow_tab_drag_preview_presenter import (
    WorkflowTabDragPreviewPresenter,
)


class _Item:
    """Fake preview item recording movement and slide calls."""

    def __init__(self, route_key: str, *, x: int, y: int = 0) -> None:
        """Create one fake item."""

        self._route_key = route_key
        self._x = x
        self._y = y
        self.moves: list[tuple[int, int]] = []
        self.slides: list[tuple[int, int]] = []
        self.preview_progresses: list[float] = []
        self.raise_count = 0

    def routeKey(self) -> str:
        """Return the route key."""

        return self._route_key

    def x(self) -> int:
        """Return current x."""

        return self._x

    def y(self) -> int:
        """Return current y."""

        return self._y

    def move(self, x: int, y: int) -> None:
        """Record immediate movement."""

        self._x = x
        self._y = y
        self.moves.append((x, y))

    def raise_(self) -> None:
        """Record raise calls."""

        self.raise_count += 1

    def slideTo(self, x: int, duration: int = 250) -> None:
        """Record animated horizontal movement."""

        self._x = x
        self.slides.append((x, duration))

    def set_orb_cutout_preview_progress(self, progress: float) -> None:
        """Record direct drag-preview cutout progress."""

        self.preview_progresses.append(progress)


def test_preview_moves_dragged_tab_and_displaces_siblings() -> None:
    """Drag preview should move the dragged tab and slide displaced siblings."""

    items = {
        "wf-a": _Item("wf-a", x=0),
        "wf-b": _Item("wf-b", x=100),
        "wf-c": _Item("wf-c", x=200),
    }
    slots = (QRect(0, 0, 80, 32), QRect(100, 0, 80, 32), QRect(200, 0, 80, 32))
    presenter = WorkflowTabDragPreviewPresenter()

    state = presenter.preview(
        items_by_workflow_id=items,
        committed_order=("wf-a", "wf-b", "wf-c"),
        preview_order=("wf-b", "wf-a", "wf-c"),
        dragged_workflow_id="wf-b",
        pointer_pos=QPoint(20, 0),
        press_pos=QPoint(140, 0),
        slot_rects=slots,
    )

    assert items["wf-b"].moves == [(0, 0)]
    assert items["wf-b"].raise_count == 1
    assert items["wf-a"].slides == [(100, 250)]
    assert items["wf-c"].slides == [(200, 250)]
    assert items["wf-a"].preview_progresses == [0.0]
    assert items["wf-b"].preview_progresses == [1.0]
    assert items["wf-c"].preview_progresses == [0.0]
    assert state.orb_adjacent_route_key == "wf-b"


def test_preview_sets_partial_cutout_progress_from_drag_geometry() -> None:
    """Drag preview should morph cutout progress continuously, not by endpoint."""

    items = {
        "wf-a": _Item("wf-a", x=0),
        "wf-b": _Item("wf-b", x=100),
    }
    slots = (QRect(0, 0, 80, 32), QRect(100, 0, 80, 32))
    presenter = WorkflowTabDragPreviewPresenter()

    state = presenter.preview(
        items_by_workflow_id=items,
        committed_order=("wf-a", "wf-b"),
        preview_order=("wf-b", "wf-a"),
        dragged_workflow_id="wf-b",
        pointer_pos=QPoint(90, 0),
        press_pos=QPoint(140, 0),
        slot_rects=slots,
    )

    assert items["wf-b"].moves == [(50, 0)]
    assert items["wf-b"].preview_progresses == [0.5]
    assert items["wf-a"].preview_progresses == [0.5]
    assert state.orb_adjacent_route_key == "wf-a"


def test_cancel_settles_items_to_committed_slots() -> None:
    """Cancel should return every item to its committed slot."""

    items = {
        "wf-a": _Item("wf-a", x=100),
        "wf-b": _Item("wf-b", x=0),
    }
    slots = (QRect(0, 0, 80, 32), QRect(100, 0, 80, 32))
    presenter = WorkflowTabDragPreviewPresenter()

    presenter.cancel(
        items_by_workflow_id=items,
        committed_order=("wf-a", "wf-b"),
        slot_rects=slots,
    )

    assert items["wf-a"].slides == [(0, 250)]
    assert items["wf-b"].slides == [(100, 250)]
