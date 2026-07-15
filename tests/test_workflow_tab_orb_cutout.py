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

"""Contract tests for orb-adjacent workflow tab cutout behavior."""

from __future__ import annotations

import os
import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.chrome_style import WORKFLOW_TAB_BODY_TOP_RADIUS
from substitute.presentation.workflows.workflow_tabs_view import TabBar, TabItem

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "workflow tab Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_tab_item_cutout_progress_clamps_and_toggles_without_animation() -> None:
    """Tab cutout progress should stay normalized and support immediate toggles."""

    _app()
    tab = TabItem("Workflow")

    tab._set_orb_cutout_progress(2.0)
    assert tab.orb_cutout_progress() == 1.0

    tab._set_orb_cutout_progress(-1.0)
    assert tab.orb_cutout_progress() == 0.0

    tab.set_orb_cutout_active(True, animated=False)
    assert tab.orb_cutout_progress() == 1.0

    tab.set_orb_cutout_active(False, animated=False)
    assert tab.orb_cutout_progress() == 0.0


def test_tab_item_cutout_animation_starts_from_current_progress() -> None:
    """Retargeted cutout animations should start from the current tween value."""

    _app()
    tab = TabItem("Workflow")

    tab._set_orb_cutout_progress(0.25)
    tab.set_orb_cutout_active(True, animated=True)

    assert tab._orb_cutout_animation.startValue() == 0.25
    assert tab._orb_cutout_animation.endValue() == 1.0

    tab._set_orb_cutout_progress(0.6)
    tab.set_orb_cutout_active(False, animated=True)

    assert tab._orb_cutout_animation.startValue() == 0.6
    assert tab._orb_cutout_animation.endValue() == 0.0
    tab._orb_cutout_animation.stop()


def test_tab_item_cutout_path_removes_orb_adjacent_bite() -> None:
    """Full cutout progress should subtract the orb bite from the normal shape."""

    _app()
    tab = TabItem("Workflow")
    tab.resize(140, 30)
    rect = QRectF(tab.rect().adjusted(1, 1, -1, 0))
    rect.setBottom(rect.bottom() + 1.0)
    bite_point = QPointF(rect.left() + 6.0, tab._orb_cutout_center().y())

    tab.set_orb_cutout_active(False, animated=False)
    normal_path = tab._top_rounded_orb_cutout_path(
        rect,
        WORKFLOW_TAB_BODY_TOP_RADIUS,
    )

    tab.set_orb_cutout_active(True, animated=False)
    cutout_path = tab._top_rounded_orb_cutout_path(
        rect,
        WORKFLOW_TAB_BODY_TOP_RADIUS,
    )

    assert normal_path.contains(bite_point)
    assert not cutout_path.contains(bite_point)


def test_tabbar_assigns_cutout_to_first_workflow_tab_without_initial_animation() -> (
    None
):
    """The first created workflow tab should immediately own the orb cutout."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")
        third = _add_tab(tabbar, "wf-c", "Third")

        assert tabbar._orb_cutout_sync_initialized is True
        assert tabbar._orb_adjacent_tab_route_key == "wf-a"
        assert first.orb_cutout_progress() == 1.0
        assert second.orb_cutout_progress() == 0.0
        assert third.orb_cutout_progress() == 0.0
    finally:
        tabbar.close()


def test_visible_tabbar_assigns_cutout_after_first_workflow_tab_show() -> None:
    """A first tab added after the tabbar is visible should own the orb cutout."""

    app = _app()
    tabbar = TabBar()
    tabbar.resize(500, 40)
    tabbar.show()
    app.processEvents()
    try:
        first = _add_tab(tabbar, "wf-a", "First")

        app.processEvents()

        assert tabbar._orb_cutout_sync_initialized is True
        assert tabbar._orb_adjacent_tab_route_key == "wf-a"
        assert first.orb_cutout_progress() == 1.0
    finally:
        tabbar.close()
        tabbar.deleteLater()
        app.processEvents()


def test_workflow_tab_rect_includes_layout_margin() -> None:
    """Workflow tab slot geometry should include the tab layout's left margin."""

    tabbar = _tabbar()
    try:
        _add_tab(tabbar, "wf-a", "First")

        rect = tabbar.tabRect(0)

        assert rect is not None
        assert rect.x() == tabbar.itemLayout.contentsMargins().left()
    finally:
        tabbar.close()


def test_insert_first_workflow_tab_enforces_orb_cutout_immediately() -> None:
    """A newly inserted first workflow tab should immediately own the cutout."""

    tabbar = _tabbar()
    try:
        old_first = _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")

        inserted = tabbar.insertTab(0, "wf-reopened", "Reopened")

        assert isinstance(inserted, TabItem)
        assert tabbar.workflow_ids_in_order() == ["wf-reopened", "wf-a", "wf-b"]
        assert tabbar._orb_adjacent_tab_route_key == "wf-reopened"
        assert inserted.orb_cutout_progress() == 1.0
        assert old_first.orb_cutout_progress() == 0.0
        assert second.orb_cutout_progress() == 0.0
    finally:
        tabbar.close()


def test_append_workflow_tab_keeps_first_tab_cutout_immediate() -> None:
    """Appending workflows should not disturb the first tab's cutout ownership."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")

        assert tabbar.workflow_ids_in_order() == ["wf-a", "wf-b"]
        assert tabbar._orb_adjacent_tab_route_key == "wf-a"
        assert first.orb_cutout_progress() == 1.0
        assert second.orb_cutout_progress() == 0.0
    finally:
        tabbar.close()


def test_remove_first_workflow_tab_enforces_next_cutout_immediately() -> None:
    """Removing the first workflow should immediately shape the next first tab."""

    tabbar = _tabbar()
    try:
        _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")

        tabbar.remove_workflow_tab("wf-a")

        assert tabbar.workflow_ids_in_order() == ["wf-b"]
        assert tabbar._orb_adjacent_tab_route_key == "wf-b"
        assert second.orb_cutout_progress() == 1.0
    finally:
        tabbar.close()


def test_hidden_first_workflow_tab_does_not_own_orb_cutout() -> None:
    """Hiding the first workflow should immediately move cutout ownership."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")

        tabbar.setTabVisible(0, False)

        assert tabbar._orb_adjacent_tab_route_key == "wf-b"
        assert first.orb_cutout_progress() == 0.0
        assert second.orb_cutout_progress() == 1.0
    finally:
        tabbar.close()


def test_first_workflow_tab_left_drag_clamps_to_layout_slot() -> None:
    """Dragging the first workflow tab left should not push it inside its slot."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        _add_tab(tabbar, "wf-b", "Second")
        tabbar.setMovable(True)
        slot = tabbar.tabRect(0)
        assert slot is not None
        first.move(slot.x(), first.y())
        setattr(tabbar, "dragPos", QPoint(slot.x() + 40, 10))
        setattr(tabbar, "isDraging", True)

        tabbar.mouseMoveEvent(
            _mouse_event(
                QMouseEvent.Type.MouseMove,
                QPoint(slot.x() + 20, 10),
                button=Qt.MouseButton.NoButton,
                buttons=Qt.MouseButton.LeftButton,
            )
        )

        assert first.x() == slot.x()
    finally:
        tabbar.close()


def test_zero_distance_workflow_tab_move_still_rebuilds_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Move command cleanup should run even when the tab stays in its slot."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        tabbar.setMovable(True)
        slot = tabbar.tabRect(0)
        assert slot is not None
        first.move(slot.x(), first.y())
        rebuilds: list[str] = []

        def fake_adjust_layout() -> None:
            """Record release cleanup."""

            rebuilds.append("adjusted")

        monkeypatch.setattr(tabbar, "_adjustLayout", fake_adjust_layout)

        tabbar.move_workflow_tab("wf-a", 0)

        assert rebuilds == ["adjusted"]
        assert first.x() == slot.x()
    finally:
        tabbar.close()


def test_tabbar_reorder_moves_cutout_target_to_new_first_tab() -> None:
    """Dragging a tab across the first slot should retarget the cutout animation."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")
        _add_tab(tabbar, "wf-c", "Third")

        tabbar._swapItem(1)

        assert tabbar.workflow_ids_in_order() == ["wf-b", "wf-a", "wf-c"]
        assert tabbar._orb_adjacent_tab_route_key == "wf-b"
        assert second._orb_cutout_animation.endValue() == 1.0
        assert first._orb_cutout_animation.endValue() == 0.0
        second._orb_cutout_animation.stop()
        first._orb_cutout_animation.stop()
    finally:
        tabbar.close()


def test_tabbar_removal_moves_cutout_target_to_next_first_tab() -> None:
    """Removing the first workflow tab should immediately shape the next tab."""

    tabbar = _tabbar()
    try:
        _add_tab(tabbar, "wf-a", "First")
        second = _add_tab(tabbar, "wf-b", "Second")

        tabbar.remove_workflow_tab("wf-a")

        assert tabbar.workflow_ids_in_order() == ["wf-b"]
        assert tabbar._orb_adjacent_tab_route_key == "wf-b"
        assert second.orb_cutout_progress() == 1.0
    finally:
        tabbar.close()


def test_selected_tab_progress_invalidates_corner_overlay_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected-tab tween steps should clear stale overlay signatures before sync."""

    tabbar = _tabbar()
    try:
        first = _add_tab(tabbar, "wf-a", "First")
        snapshots: list[tuple[object | None, object | None]] = []

        def fake_sync_corner_overlay() -> None:
            """Record cache state observed by the sync call."""

            snapshots.append(
                (
                    getattr(tabbar, "_corner_overlay_sync_signature"),
                    tabbar.cornerOverlay._corner_path_cache_signature,
                )
            )

        setattr(tabbar, "_corner_overlay_sync_signature", ("stale",))
        tabbar.cornerOverlay._corner_path_cache_signature = ("stale",)
        monkeypatch.setattr(tabbar, "_syncCornerOverlay", fake_sync_corner_overlay)

        first._set_orb_cutout_progress(0.5)

        assert snapshots == [(None, None)]
    finally:
        tabbar.close()


def _tabbar() -> TabBar:
    """Create a workflow tabbar for cutout contract tests."""

    _app()
    return TabBar()


def _add_tab(tabbar: TabBar, route_key: str, text: str) -> TabItem:
    """Add one workflow tab and return it as the concrete tab item."""

    tab = tabbar.addTab(route_key, text)
    assert isinstance(tab, TabItem)
    return tab


def _mouse_event(
    event_type: QMouseEvent.Type,
    pos: QPoint,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    """Create a mouse event for workflow tab drag contract tests."""

    return QMouseEvent(
        event_type,
        pos,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
