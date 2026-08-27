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

"""Workflow-tab context-menu interaction contracts."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt

from tests.presentation.workflows.tabs.interaction_support import (
    _empty_tab_bar_pos,
    _install_context_menu_probe,
    _mouse_event,
    _tab_center,
    _tabbar,
)


def test_tab_context_menu_rename_starts_inline_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch the Rename menu action through the tab item's inline editor."""
    tabbar = _tabbar()
    menu = _install_context_menu_probe(monkeypatch)
    renames: list[str] = []

    try:
        second = tabbar.tabItem(1)
        assert second is not None
        monkeypatch.setattr(
            second,
            "_startRename",
            lambda: renames.append(second.routeKey()),
        )

        tabbar._show_tab_context_menu(second)
        menu.action("Rename").trigger()

        assert renames == ["wf-b"]
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_context_menu_request_clears_drag_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening the tab context menu cancels any pending drag candidate."""

    tabbar = _tabbar()
    menu = _install_context_menu_probe(monkeypatch)

    try:
        start = _tab_center(tabbar, 1)
        second = tabbar.tabItem(1)
        assert second is not None

        tabbar.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                start,
                button=Qt.MouseButton.LeftButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )
        tabbar._show_tab_context_menu(second)
        tabbar.mouseMoveEvent(
            _mouse_event(
                QEvent.Type.MouseMove,
                _tab_center(tabbar, 0) - QPoint(40, 0),
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )

        assert len(menu.exec_calls) == 1
        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_tab_context_menu_exposes_reopen_closed_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing-tab context menu should expose reopen as a tab-bar intent."""

    tabbar = _tabbar()
    menu = _install_context_menu_probe(monkeypatch)
    emitted: list[str] = []
    tabbar.workflowReopenClosedRequested.connect(lambda: emitted.append("reopen"))
    tabbar.set_reopen_closed_workflow_enabled(True)

    try:
        second = tabbar.tabItem(1)
        assert second is not None

        tabbar._show_tab_context_menu(second)

        assert menu.labels == ["Rename", "Duplicate", "---", "Reopen Closed Workflow"]
        menu.action("Reopen Closed Workflow").trigger()
        assert emitted == ["reopen"]
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_tab_context_menu_disables_reopen_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable reopen command should be visible but inert."""

    tabbar = _tabbar()
    menu = _install_context_menu_probe(monkeypatch)
    emitted: list[str] = []
    tabbar.workflowReopenClosedRequested.connect(lambda: emitted.append("reopen"))
    tabbar.set_reopen_closed_workflow_enabled(False)

    try:
        second = tabbar.tabItem(1)
        assert second is not None

        tabbar._show_tab_context_menu(second)

        reopen_action = menu.action("Reopen Closed Workflow")
        assert reopen_action.isEnabled() is False
        reopen_action.trigger()
        assert emitted == []
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_empty_tab_bar_context_menu_exposes_only_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty tab-row context menu should reopen without tab-specific actions."""

    tabbar = _tabbar()
    menu = _install_context_menu_probe(monkeypatch)
    emitted: list[str] = []
    selected: list[str] = []
    duplicated: list[str] = []
    closed: list[str] = []
    tabbar.workflowReopenClosedRequested.connect(lambda: emitted.append("reopen"))
    tabbar.workflowSelected.connect(selected.append)
    tabbar.workflowDuplicateRequested.connect(duplicated.append)
    tabbar.workflowCloseRequested.connect(closed.append)
    tabbar.set_reopen_closed_workflow_enabled(True)

    try:
        current_before = tabbar.currentTab().routeKey()
        tabbar.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                _empty_tab_bar_pos(tabbar),
                button=Qt.MouseButton.RightButton,
                buttons=Qt.MouseButton.RightButton,
            )
        )

        assert menu.labels == ["Reopen Closed Workflow"]
        assert tabbar.currentTab().routeKey() == current_before
        assert selected == []
        assert duplicated == []
        assert closed == []
        menu.action("Reopen Closed Workflow").trigger()
        assert emitted == ["reopen"]
    finally:
        tabbar.close()
        tabbar.deleteLater()


def test_empty_tab_bar_context_menu_cancels_drag_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty-space context menus should cancel pending workflow-tab drag state."""

    tabbar = _tabbar()
    _install_context_menu_probe(monkeypatch)

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
        tabbar.mousePressEvent(
            _mouse_event(
                QEvent.Type.MouseButtonPress,
                _empty_tab_bar_pos(tabbar),
                button=Qt.MouseButton.RightButton,
                buttons=Qt.MouseButton.RightButton,
            )
        )

        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
        assert tabbar.workflow_tab_gesture_is_idle()
    finally:
        tabbar.close()
        tabbar.deleteLater()
