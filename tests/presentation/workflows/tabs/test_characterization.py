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

"""Workflow tab characterization contracts."""

from __future__ import annotations

from typing import Any

import importlib
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication
from tests.presentation.workflows.tab_stack_support import (
    _Signal,
    _TabItem,
    _import_workflow_tabs_module,
)


def test_workflow_tab_set_tab_visible_hides_current_tab_with_branch_specific_index_logic() -> (
    None
):
    """Hiding current tab keeps branch-specific index reset behavior."""
    mod = _import_workflow_tabs_module()
    QApplication.instance() or QApplication([])
    tab_bar = mod.TabBar()
    current_changed: list[int] = []
    try:
        item0 = tab_bar.addTab("one", "One")
        tab_bar.addTab("two", "Two")
        tab_bar.currentChanged.connect(current_changed.append)

        tab_bar.setTabVisible(0, False)

        assert item0.isVisible() is False
        assert tab_bar.currentIndex() == 0
        assert current_changed == [0]
    finally:
        tab_bar.close()


def test_workflow_tab_on_tab_renamed_only_emits_manager_request() -> None:
    """Inline rename should emit old/new keys without mutating maps in-place."""
    mod = _import_workflow_tabs_module()
    tab_renamed = _Signal()
    workflow_renamed = _Signal()
    tab_item = _TabItem("workflow_old")
    fake: Any
    fake = SimpleNamespace(
        tabRenamed=tab_renamed,
        workflowRenameRequested=workflow_renamed,
        is_settings_route=lambda _route_key: False,
    )

    mod.TabBar._onTabRenamed(fake, tab_item, "workflow_new")

    assert tab_renamed.calls == [("workflow_old", "workflow_new")]
    assert workflow_renamed.calls == [("workflow_old", "workflow_new")]


def test_workflow_tab_item_uses_connected_top_accent_style() -> None:
    """Workflow tabs should opt into the Firefox-like connected chrome style."""
    mod = _import_workflow_tabs_module()
    style = importlib.import_module("substitute.presentation.shell.chrome_style")
    tab_item = mod.TabItem("Workflow")

    assert mod.TabItem.fixed_height == style.WORKFLOW_TAB_HEIGHT
    assert mod.TabItem.selected_accent_position == "top"
    assert mod.TabItem.selected_border_reacts_to_hover is False
    assert mod.TabItem.selected_bottom_corner_radius == (
        style.WORKFLOW_TAB_BOTTOM_CORNER_RADIUS
    )
    assert mod.TabItem.selected_bottom_corner_width == (
        style.WORKFLOW_TAB_BOTTOM_CORNER_WIDTH
    )
    assert mod.TabItem.selected_bottom_border_mode == "none"
    assert mod.TabItem.selected_connects_to_bottom_surface is True
    assert tab_item.selected_fill_color == style.workflow_chrome_wash_color()
    assert mod.TabItem.selected_fill_radius == style.WORKFLOW_TAB_BODY_TOP_RADIUS
    assert mod.TabItem.unselected_separator_color is None
    assert mod.TabItem.unselected_top_rounded_only is True
    assert mod.TabItem.inactive_text_alpha == style.WORKFLOW_TAB_INACTIVE_TEXT_ALPHA


def test_workflow_tab_remove_tab_decrements_current_index_for_left_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing a tab left of current should decrement current index."""
    mod = _import_workflow_tabs_module()
    removed_from_router: list[str] = []
    monkeypatch.setattr(
        mod.qrouter, "remove", lambda key: removed_from_router.append(key)
    )

    items = [_TabItem("a"), _TabItem("b"), _TabItem("c")]
    removed_item = items[0]
    fake: Any = SimpleNamespace(
        items=items,
        itemMap={item.routeKey(): item for item in items},
        _currentIndex=2,
        hBoxLayout=SimpleNamespace(removeWidget=lambda _w: None),
        currentChanged=_Signal(),
        currentIndex=lambda: fake._currentIndex,
        setCurrentIndex=lambda idx: setattr(fake, "_currentIndex", idx),
        update=lambda: None,
        _emitCurrentChanged=lambda index: fake.currentChanged.emit(index),
        _onTabRemoved=lambda route_key: removed_from_router.append(route_key),
    )

    mod.TabBar.removeTab(fake, 0)

    assert fake._currentIndex == 1
    assert "a" not in fake.itemMap
    assert removed_from_router == ["a"]
    assert removed_item.deleted is True


def test_workflow_tab_corner_overlay_class_is_exported() -> None:
    """Workflow module should expose the parent-owned overlay class."""
    mod = _import_workflow_tabs_module()

    assert mod.WorkflowTabCornerOverlay.__name__ == "WorkflowTabCornerOverlay"
