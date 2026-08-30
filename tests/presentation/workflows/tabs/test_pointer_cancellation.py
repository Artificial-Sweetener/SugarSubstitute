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

"""Workflow-tab close-button and stale-drag cancellation contracts."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt

from tests.presentation.workflows.tabs.interaction_support import (
    _mouse_event,
    _tab_center,
    _tabbar,
)


def test_close_button_click_does_not_arm_workflow_tab_drag() -> None:
    """Tab close-button interaction is isolated from drag state."""

    tabbar = _tabbar()
    close_requests: list[int] = []
    tabbar.tabCloseRequested.connect(lambda index: close_requests.append(index))

    try:
        first = tabbar.tabItem(0)
        assert first is not None

        first.closeButton.click()

        assert close_requests == [0]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_mouse_move_without_pressed_button_does_not_reorder_after_prior_drag() -> None:
    """A completed drag cannot leave stale state for later mouse movement."""

    tabbar = _tabbar()
    try:
        start = _tab_center(tabbar, 1)
        end = _tab_center(tabbar, 0) - QPoint(40, 0)

        tabbar.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                start,
                button=Qt.MouseButton.LeftButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        tabbar.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                end,
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        tabbar.mouseReleaseEvent(
            _mouse_event(
                QEvent.Type.MouseButtonRelease,
                end,
                button=Qt.MouseButton.LeftButton,
                buttons=Qt.MouseButton.NoButton,
            )
        )
        order_after_drag = tabbar.workflow_ids_in_order()

        tabbar.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                _tab_center(tabbar, 2),
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.NoButton,
            )
        )

        assert order_after_drag == ["wf-b", "wf-a", "wf-c"]
        assert tabbar.workflow_ids_in_order() == order_after_drag
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()
