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

"""Qt-backed workflow-tab interaction contract tests."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "workflow tab interaction tests require non-xdist execution",
        allow_module_level=True,
    )


def _ensure_qapp() -> QApplication:
    """Return the active QApplication, creating one for Qt-backed tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _clear_gui_stubs() -> None:
    """Remove lightweight GUI stubs so real Qt widgets can import."""

    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "QCoreApplication"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is not None and not hasattr(qfw, "MenuAnimationType"):
        for name in list(sys.modules):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("substitute.presentation.widgets.cursor_tooltip_filter", None)


def _workflow_tabs_module() -> Any:
    """Import the real workflow tab module for interaction tests."""

    _clear_gui_stubs()
    return importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )


def _tabbar() -> Any:
    """Build a visible movable workflow tab bar with three tabs."""

    app = _ensure_qapp()
    mod = _workflow_tabs_module()
    tabbar = mod.TabBar(None)
    tabbar.resize(520, 44)
    tabbar.addTab("wf-a", "A")
    tabbar.addTab("wf-b", "B")
    tabbar.addTab("wf-c", "C")
    tabbar.setMovable(True)
    tabbar.show()
    app.processEvents()
    return tabbar


def _mouse_event(
    event_type: QEvent.Type,
    pos: QPoint,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    """Create a mouse event at one tab-bar-local position."""

    return QMouseEvent(
        event_type,
        QPointF(pos),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _tab_center(tabbar: Any, index: int) -> QPoint:
    """Return the center point for a workflow tab slot."""

    rect = tabbar.tabRect(index)
    assert rect is not None
    return cast(QPoint, rect.center())


def _empty_tab_bar_pos(tabbar: Any) -> QPoint:
    """Return a stable point in empty workflow tab-row space."""

    return QPoint(max(0, tabbar.width() - 8), tabbar.height() // 2)


def _install_context_menu_probe(monkeypatch: pytest.MonkeyPatch) -> "_MenuProbe":
    """Patch workflow tab menus with a non-rendering capture probe."""

    probe = _MenuProbe()
    mod = _workflow_tabs_module()
    monkeypatch.setattr(
        mod,
        "QFluentMenuRenderer",
        lambda *args, **kwargs: _MenuProbeRenderer(probe),
    )
    return probe


class _MenuProbe:
    """Capture workflow-tab context menu actions without showing a popup."""

    def __init__(self) -> None:
        """Initialize empty captured menu state."""

        self.labels: list[str] = []
        self.actions: list[Any] = []
        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def addAction(self, action: Any) -> None:
        """Record one menu action."""

        self.actions.append(action)
        self.labels.append(str(action.text()))

    def addSeparator(self) -> None:
        """Record a separator in action order."""

        self.labels.append("---")

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record menu execution without rendering."""

        self.exec_calls.append((args, kwargs))

    def action(self, text: str) -> Any:
        """Return the captured action matching text."""

        for action in self.actions:
            if action.text() == text:
                return action
        raise AssertionError(f"Missing action: {text}")


class _ProbeAction:
    """Record one rendered menu item for workflow tab interaction tests."""

    def __init__(self, item: MenuItem) -> None:
        """Store item state for assertions and callback dispatch."""

        self._item = item

    def text(self) -> str:
        """Return the action label."""

        return self._item.label

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the rendered action is enabled."""

        return self._item.enabled

    def trigger(self) -> None:
        """Dispatch the rendered item callback when enabled."""

        if self._item.enabled and self._item.callback is not None:
            self._item.callback()


class _MenuProbeRenderer:
    """Render shared menu models into a workflow tab menu probe."""

    def __init__(self, probe: _MenuProbe) -> None:
        """Store the probe that receives rendered rows."""

        self._probe = probe

    def render(self, model: MenuModel) -> _MenuProbe:
        """Populate and return the probe menu."""

        for entry in model.entries:
            if isinstance(entry, MenuItem):
                self._probe.addAction(_ProbeAction(entry))
            elif isinstance(entry, MenuSeparator):
                self._probe.addSeparator()
        return self._probe


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
