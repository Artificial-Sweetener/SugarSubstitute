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

"""Cube stack scroll and indicator-lifecycle contracts."""

from __future__ import annotations

import importlib
from typing import Protocol

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget
from tests.presentation.workflows.qt_support import (
    _ensure_qapp,
    _wheel_event,
)
from tests.support.qt.lifecycle import destroy_qt_object, destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _IndicatorAlignedStack(Protocol):
    """Expose the cube-stack state used by the alignment contract."""

    _indicator_realign_pending: bool

    def _getIndicatorY(self) -> int:
        """Return the selected indicator's vertical coordinate."""

    def currentTab(self) -> QWidget | None:
        """Return the currently selected cube tab."""


def _selected_indicator_is_aligned(stack: _IndicatorAlignedStack) -> bool:
    """Return whether the current tab and scheduled indicator share one position."""

    selected = stack.currentTab()
    return (
        selected is not None
        and not stack._indicator_realign_pending
        and stack._getIndicatorY() == selected.y() + selected.height() // 2 - 8
    )


def test_cubestack_wheel_reroutes_when_stack_has_no_scroll_range() -> None:
    """CubeStack should yield wheel input when its content does not need scrolling."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.resize(200, 220)
    stack.addTab("a", "A")
    stack.show()
    app.processEvents()
    rerouted: list[QWheelEvent] = []
    stack.cubeStackWheelRerouteRequested.connect(rerouted.append)

    event = _wheel_event(stack.viewport(), angle_delta_y=-120)
    stack.wheelEvent(event)

    assert stack.verticalScrollBar().maximum() == 0
    assert rerouted == [event]
    assert event.isAccepted()

    destroy_widget_roots([stack])


def test_cubestack_indicator_realign_timer_is_destroyed_with_stack() -> None:
    """Deferred indicator work must not outlive a replaced cube-stack surface."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    import shiboken6

    stack = mod.CubeStack(None)
    stack.addTab("a", "A")
    timer = stack._indicator_realign_timer

    assert timer.parent() is stack
    assert timer.isSingleShot()
    assert timer.isActive()

    destroy_widget_roots([stack])

    assert not shiboken6.isValid(timer)


def test_cubestack_owned_layout_changes_realign_selected_indicator() -> None:
    """Cube-stack geometry owners must explicitly settle the selected indicator."""

    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    try:
        for index in range(3):
            stack.addTab(str(index), f"Cube {index}")
        stack.show()
        app.processEvents()
        stack.setCurrentIndex(2)

        stack.finishCompactTransition(True)
        wait_for_qt_condition(lambda: _selected_indicator_is_aligned(stack))

        selected = stack.currentTab()
        assert selected is not None
        assert stack._getIndicatorY() == selected.y() + selected.height() // 2 - 8

        stack.reorder_by_route_keys(["2", "0", "1"])
        wait_for_qt_condition(lambda: _selected_indicator_is_aligned(stack))

        selected = stack.currentTab()
        assert selected is not None
        assert stack._getIndicatorY() == selected.y() + selected.height() // 2 - 8
    finally:
        destroy_widget_roots([stack])


def test_cubestack_indicator_realign_ignores_deleted_content_view() -> None:
    """A stale layout tick must stop when its owned content view was deleted."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    import shiboken6

    stack = mod.CubeStack(None)
    stack._indicator_realign_timer.stop()
    detached_view = stack.takeWidget()
    assert detached_view is stack.view
    destroy_qt_object(detached_view)
    assert not shiboken6.isValid(detached_view)

    stack._complete_indicator_realign()

    destroy_widget_roots([stack])


def test_cubestack_wheel_stays_owned_when_stack_can_scroll_at_boundary() -> None:
    """Scrollable CubeStack should not reroute, even when currently at a boundary."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.resize(200, 80)
    for index in range(20):
        stack.addTab(str(index), f"Cube {index}")
    stack.show()
    app.processEvents()
    rerouted: list[QWheelEvent] = []
    stack.cubeStackWheelRerouteRequested.connect(rerouted.append)
    stack.verticalScrollBar().setValue(stack.verticalScrollBar().maximum())

    event = _wheel_event(stack.viewport(), angle_delta_y=-120)
    stack.wheelEvent(event)

    assert stack.verticalScrollBar().maximum() > 0
    assert rerouted == []
    assert event.isAccepted()

    destroy_widget_roots([stack])
