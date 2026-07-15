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

"""Contract tests for session autosave debounce coordination."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveCoordinator,
    SessionAutosaveRequestCategory,
)


class _Timeout:
    """Signal double storing the connected timeout callback."""

    def __init__(self) -> None:
        """Initialize without a callback."""

        self.callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the timeout callback."""

        self.callback = callback


class _Timer:
    """QTimer double recording debounce starts."""

    def __init__(self, parent: object | None = None) -> None:
        """Store parent and initialize call logs."""

        self.parent = parent
        self.timeout = _Timeout()
        self.single_shot = False
        self.start_calls: list[int] = []

    def setSingleShot(self, single_shot: bool) -> None:
        """Record single-shot configuration."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record timer starts."""

        self.start_calls.append(delay_ms)


def test_tab_selection_requests_are_debounced_until_flushed() -> None:
    """Tab-selection autosave intent should restart its timer before saving."""

    saves: list[SessionAutosaveRequestCategory] = []
    coordinator = SessionAutosaveCoordinator(
        request_save=saves.append,
        timer_factory=lambda parent: _Timer(parent),
        tab_selection_debounce_ms=25,
        resize_debounce_ms=50,
    )

    coordinator.request(SessionAutosaveRequestCategory.TAB_SELECTION)
    coordinator.request(SessionAutosaveRequestCategory.TAB_SELECTION)

    assert isinstance(coordinator.tab_selection_timer, _Timer)
    assert coordinator.tab_selection_timer.start_calls == [25, 25]
    assert saves == []

    coordinator.flush_tab_selection()

    assert saves == [SessionAutosaveRequestCategory.TAB_SELECTION]


def test_resize_requests_are_debounced_separately() -> None:
    """Resize autosave intent should use the resize debounce timer."""

    saves: list[SessionAutosaveRequestCategory] = []
    coordinator = SessionAutosaveCoordinator(
        request_save=saves.append,
        timer_factory=lambda parent: _Timer(parent),
        tab_selection_debounce_ms=25,
        resize_debounce_ms=50,
    )

    coordinator.request(SessionAutosaveRequestCategory.LAYOUT_RESIZE)

    assert isinstance(coordinator.resize_timer, _Timer)
    assert coordinator.resize_timer.start_calls == [50]
    assert saves == []

    coordinator.flush_resize()

    assert saves == [SessionAutosaveRequestCategory.LAYOUT_RESIZE]


def test_structural_requests_are_debounced_by_category() -> None:
    """Lower-frequency structural requests should coalesce before saving."""

    saves: list[SessionAutosaveRequestCategory] = []
    coordinator = SessionAutosaveCoordinator(
        request_save=saves.append,
        timer_factory=lambda parent: _Timer(parent),
        tab_selection_debounce_ms=25,
        resize_debounce_ms=50,
    )

    coordinator.request(SessionAutosaveRequestCategory.TAB_STRUCTURE)
    coordinator.request(SessionAutosaveRequestCategory.TAB_STRUCTURE)

    assert saves == []

    coordinator.flush(SessionAutosaveRequestCategory.TAB_STRUCTURE)

    assert saves == [SessionAutosaveRequestCategory.TAB_STRUCTURE]


def test_canvas_selection_requests_are_debounced_by_category() -> None:
    """Canvas selection changes should persist only after the category settles."""

    saves: list[SessionAutosaveRequestCategory] = []
    coordinator = SessionAutosaveCoordinator(
        request_save=saves.append,
        timer_factory=lambda parent: _Timer(parent),
        tab_selection_debounce_ms=25,
        resize_debounce_ms=50,
    )

    coordinator.request(SessionAutosaveRequestCategory.CANVAS_SELECTION)

    assert saves == []

    coordinator.flush(SessionAutosaveRequestCategory.CANVAS_SELECTION)

    assert saves == [SessionAutosaveRequestCategory.CANVAS_SELECTION]
