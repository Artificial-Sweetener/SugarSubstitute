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

"""Workflow-tab pointer selection, preview, and reorder contracts."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt

from tests.presentation.workflows.tabs.interaction_support import (
    _mouse_event,
    _tab_center,
    _tabbar,
)


def test_right_button_move_does_not_reorder_workflow_tabs() -> None:
    """Right-button movement cannot start workflow tab reorder."""

    tabbar = _tabbar()
    try:
        tabbar.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                _tab_center(tabbar, 1),
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.RightButton,
            )
        )

        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_right_click_then_right_click_another_tab_does_not_reorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated workflow tab context clicks cannot leak into reorder state."""

    tabbar = _tabbar()
    shown: list[str | None] = []
    monkeypatch.setattr(
        tabbar,
        "_show_tab_context_menu",
        lambda tab_item: shown.append(tab_item.routeKey()),
    )

    try:
        first = tabbar.tabItem(0)
        second = tabbar.tabItem(1)
        assert first is not None
        assert second is not None

        first.customContextMenuRequested.emit(QPoint(4, 4))
        second.customContextMenuRequested.emit(QPoint(4, 4))

        assert shown == ["wf-a", "wf-b"]
        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_left_press_below_drag_threshold_selects_without_reorder() -> None:
    """Small left-button movement remains a click/selection, not reorder."""

    tabbar = _tabbar()
    try:
        start = _tab_center(tabbar, 1)
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
                start + QPoint(1, 0),
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        tabbar.mouseReleaseEvent(
            _mouse_event(
                QEvent.Type.MouseButtonRelease,
                start + QPoint(1, 0),
                button=Qt.MouseButton.LeftButton,
                buttons=Qt.MouseButton.NoButton,
            )
        )

        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert tabbar.currentTab().routeKey() == "wf-b"
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_left_drag_past_threshold_reorders_once_on_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid left drag finalizes through the named move command."""

    tabbar = _tabbar()
    moved: list[tuple[str, int]] = []
    original_move = tabbar.move_workflow_tab

    def record_move(
        workflow_id: str,
        target_index: int,
        *,
        animated: bool = False,
    ) -> None:
        """Record the authoritative reorder command and delegate it."""

        moved.append((workflow_id, target_index))
        original_move(workflow_id, target_index, animated=animated)

    monkeypatch.setattr(tabbar, "move_workflow_tab", record_move)

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

        assert moved == [("wf-b", 0)]
        assert tabbar.workflow_ids_in_order() == ["wf-b", "wf-a", "wf-c"]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_left_drag_preview_displaces_siblings_and_morphs_orb_cutout() -> None:
    """Drag preview should animate displacement and preview orb ownership."""

    tabbar = _tabbar()
    try:
        first = tabbar.itemMap["wf-a"]
        dragged = tabbar.itemMap["wf-b"]
        third = tabbar.itemMap["wf-c"]
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

        first_preview_slot = tabbar.tabRect(1)
        third_preview_slot = tabbar.tabRect(2)
        first_slot = tabbar.tabRect(0)
        assert first_preview_slot is not None
        assert third_preview_slot is not None
        assert first_slot is not None
        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert first.slideAni.endValue().x() == first_preview_slot.x()
        assert third.slideAni.endValue().x() == third_preview_slot.x()
        assert dragged.x() == first_slot.x()
        assert tabbar._orb_adjacent_tab_route_key == "wf-b"
        assert dragged.orb_cutout_progress() == 1.0
        assert first.orb_cutout_progress() == 0.0
        first.slideAni.stop()
        third.slideAni.stop()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_left_drag_preview_morphs_cutout_progress_continuously() -> None:
    """Real tab drag preview should set partial cutout progress from geometry."""

    tabbar = _tabbar()
    try:
        first = tabbar.itemMap["wf-a"]
        dragged = tabbar.itemMap["wf-b"]
        first_slot = tabbar.tabRect(0)
        second_slot = tabbar.tabRect(1)
        assert first_slot is not None
        assert second_slot is not None
        start = _tab_center(tabbar, 1)
        target_x = first_slot.x() + ((second_slot.x() - first_slot.x()) // 2)
        pointer = QPoint(start.x() + target_x - second_slot.x(), start.y())

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
                pointer,
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )

        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert dragged.x() == target_x
        assert dragged.orb_cutout_progress() == pytest.approx(0.5)
        assert first.orb_cutout_progress() == pytest.approx(0.5)
    finally:
        tabbar.close()
        tabbar.deleteLater()
