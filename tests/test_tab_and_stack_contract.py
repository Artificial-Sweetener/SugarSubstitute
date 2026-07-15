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

"""Characterization tests for custom tab bar and cube stack behavior."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "tab/stack characterization tests require non-xdist execution in this environment",
        allow_module_level=True,
    )


class _Signal:
    """Simple signal recorder."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def emit(self, *args) -> None:
        """Record emitted args."""
        self.calls.append(args)


class _TabItem:
    """Tab item test double."""

    def __init__(self, key: str) -> None:
        self._key = key
        self.deleted = False
        self.visible = True
        self.selected = False
        self._text = key
        self._y = 20
        self._height = 36

    def routeKey(self) -> str:
        """Return route key."""
        return self._key

    def setRouteKey(self, key: str) -> None:
        """Set route key."""
        self._key = key

    def deleteLater(self) -> None:
        """Mark as deleted."""
        self.deleted = True

    def setVisible(self, visible: bool) -> None:
        """Record visibility."""
        self.visible = visible

    def setSelected(self, selected: bool) -> None:
        """Record selected state."""
        self.selected = selected

    def setText(self, text: str) -> None:
        """Set label text."""
        self._text = text

    def y(self) -> int:
        """Return top Y."""
        return self._y

    def height(self) -> int:
        """Return item height."""
        return self._height


class _SlideAnimation:
    """Animation recorder used by CubeStack.setCurrentIndex."""

    def __init__(self) -> None:
        self.stopped = 0
        self.end_value = None
        self.duration = None
        self.curve = None
        self.started = 0

    def stop(self) -> None:
        """Record stop."""
        self.stopped += 1

    def setEndValue(self, value) -> None:
        """Record end value."""
        self.end_value = value

    def setDuration(self, duration: int) -> None:
        """Record duration."""
        self.duration = duration

    def setEasingCurve(self, curve) -> None:
        """Record curve."""
        self.curve = curve

    def start(self) -> None:
        """Record start."""
        self.started += 1


def _import_workflow_tabs_module():
    """Import workflow tab bar module."""
    _clear_gui_stubs()
    return importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )


def _import_stack_panel_module():
    """Import cube stack module."""
    _clear_gui_stubs()
    return importlib.import_module("substitute.presentation.workflows.cube_stack_view")


def _clear_gui_stubs():
    """Drop lightweight GUI stubs so real modules can import cleanly."""
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "Property"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    for name in list(sys.modules):
        if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
            sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("substitute.presentation.workflows.workflow_tabs_view", None)
    sys.modules.pop("substitute.presentation.workflows.cube_stack_view", None)
    sys.modules.pop("substitute.presentation.workflows.reorderable_tabs_base", None)
    sys.modules.pop("substitute.presentation.widgets.cursor_tooltip_filter", None)


def _attach_cube_stack_selection_methods(mod, fake: SimpleNamespace) -> None:
    """Attach CubeStack helper methods used by unbound-method test doubles."""

    fake._select_index = lambda index, *, animate_indicator: (
        mod.CubeStack._select_index(
            fake,
            index,
            animate_indicator=animate_indicator,
        )
    )
    fake._sync_indicator_to_current = lambda *, animated: (
        mod.CubeStack._sync_indicator_to_current(fake, animated=animated)
    )


def test_workflow_tab_set_tab_visible_hides_current_tab_with_branch_specific_index_logic():
    """Hiding current tab keeps branch-specific index reset behavior."""
    mod = _import_workflow_tabs_module()
    item0 = _TabItem("one")
    item1 = _TabItem("two")
    set_index_calls: list[int] = []
    current_changed = _Signal()

    fake = SimpleNamespace(
        items=[item0, item1],
        _currentIndex=0,
        currentChanged=current_changed,
        tabItem=lambda idx: [item0, item1][idx],
        currentIndex=lambda: fake._currentIndex,
        _emitCurrentChanged=lambda index: current_changed.emit(index),
    )

    def _set_current_index(index: int) -> None:
        set_index_calls.append(index)
        fake._currentIndex = index

    fake.setCurrentIndex = _set_current_index

    mod.TabBar.setTabVisible(fake, 0, False)

    assert item0.visible is False
    assert set_index_calls == [1]
    assert fake._currentIndex == 0
    assert current_changed.calls == [(0,)]


def test_workflow_tab_on_tab_renamed_only_emits_manager_request():
    """Inline rename should emit old/new keys without mutating maps in-place."""
    mod = _import_workflow_tabs_module()
    tab_renamed = _Signal()
    workflow_renamed = _Signal()
    tab_item = _TabItem("workflow_old")
    fake = SimpleNamespace(
        tabRenamed=tab_renamed,
        workflowRenameRequested=workflow_renamed,
    )

    mod.TabBar._onTabRenamed(fake, tab_item, "workflow_new")

    assert tab_renamed.calls == [("workflow_old", "workflow_new")]
    assert workflow_renamed.calls == [("workflow_old", "workflow_new")]


def test_workflow_tab_item_uses_connected_top_accent_style():
    """Workflow tabs should opt into the Firefox-like connected chrome style."""
    mod = _import_workflow_tabs_module()
    style = importlib.import_module("substitute.presentation.shell.chrome_style")

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
    assert mod.TabItem.selected_fill_color == style.workflow_chrome_wash_color()
    assert mod.TabItem.selected_fill_radius == style.WORKFLOW_TAB_BODY_TOP_RADIUS
    assert mod.TabItem.unselected_separator_color is None
    assert mod.TabItem.unselected_top_rounded_only is True
    assert mod.TabItem.inactive_text_alpha == style.WORKFLOW_TAB_INACTIVE_TEXT_ALPHA


def test_workflow_tab_remove_tab_decrements_current_index_for_left_removal(monkeypatch):
    """Removing a tab left of current should decrement current index."""
    mod = _import_workflow_tabs_module()
    removed_from_router: list[str] = []
    monkeypatch.setattr(
        mod.qrouter, "remove", lambda key: removed_from_router.append(key)
    )

    items = [_TabItem("a"), _TabItem("b"), _TabItem("c")]
    removed_item = items[0]
    fake = SimpleNamespace(
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


def test_cube_stack_on_tab_renamed_emits_rename_request_without_mutating_keys():
    """Cube tab inline rename should defer alias resolution to higher layers."""
    mod = _import_stack_panel_module()
    tab_item = _TabItem("cube_old")
    fake = SimpleNamespace(
        itemMap={"cube_old": tab_item, "cube_new": _TabItem("cube_new")},
        cubeRenameRequested=_Signal(),
    )

    mod.CubeStack._onTabRenamed(fake, tab_item, "cube_new")

    assert tab_item.routeKey() == "cube_old"
    assert fake.itemMap == {"cube_old": tab_item, "cube_new": fake.itemMap["cube_new"]}
    assert fake.cubeRenameRequested.calls == [("cube_old", "cube_new")]


def test_cube_stack_on_alias_edit_requested_emits_route_key():
    """Cube tab edit requests should be routed without mutating aliases."""

    mod = _import_stack_panel_module()
    tab_item = _TabItem("cube_old")
    fake = SimpleNamespace(cubeRenameEditRequested=_Signal())

    mod.CubeStack._onAliasEditRequested(fake, tab_item)

    assert tab_item.routeKey() == "cube_old"
    assert fake.cubeRenameEditRequested.calls == [("cube_old",)]


def test_cube_stack_item_keeps_non_workflow_selected_style():
    """Cube tabs should not inherit the workflow connected-tab chrome."""
    mod = _import_stack_panel_module()
    style = importlib.import_module("substitute.presentation.shell.chrome_style")

    assert mod.CubeItem.fixed_height == mod.CUBE_ITEM_HEIGHT
    assert mod.CubeItem.selected_accent_position == "bottom"
    assert mod.CubeItem.selected_bottom_corner_radius == 0.0
    assert mod.CubeItem.selected_bottom_corner_width == 0.0
    assert mod.CubeItem.selected_connects_to_bottom_surface is False
    assert mod.CubeItem.selected_fill_color == style.winui_card_fill_color()
    assert mod.CubeItem.selected_bottom_border_mode == "cube"
    assert mod.CubeItem.unselected_separator_color is None
    assert mod.CubeItem.unselected_top_rounded_only is False


def test_cube_stack_expanded_icon_uses_equal_outer_insets():
    """Expanded cube icons should use the same left and vertical padding."""
    mod = _import_stack_panel_module()

    expected_icon_size = mod.CUBE_ITEM_HEIGHT - (mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2)

    assert mod.CUBE_ITEM_ICON_SIZE_EXPANDED == expected_icon_size


def test_cube_stack_expanded_icon_matches_stacked_text_height():
    """Expanded cube icons should be the same height as the two text rows."""
    mod = _import_stack_panel_module()

    assert mod.CUBE_ITEM_ICON_SIZE_EXPANDED == mod.CUBE_ITEM_TEXT_BLOCK_HEIGHT
    assert mod.CUBE_ITEM_HEIGHT == mod.CUBE_ITEM_TEXT_BLOCK_HEIGHT + (
        mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2
    )


def test_cube_stack_compact_icon_keeps_expanded_size():
    """Compact mode should keep the same cube icon size and enough item width."""
    mod = _import_stack_panel_module()

    assert mod.CUBE_ITEM_ICON_SIZE_COMPACT == mod.CUBE_ITEM_ICON_SIZE_EXPANDED
    assert mod.CUBE_ITEM_COMPACT_WIDTH == mod.CUBE_ITEM_ICON_SIZE_COMPACT + (
        mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2
    )


def test_cube_stack_side_insets_match_toolbar_inset():
    """Cube stack side padding should match the toolbar-to-stack gap."""
    mod = _import_stack_panel_module()
    chrome = importlib.import_module("substitute.presentation.shell.chrome_style")

    assert mod.CUBE_STACK_EDGE_INSET == chrome.CUBE_STACK_TOP_INSET
    assert (
        mod.CUBE_STACK_EXPANDED_WIDTH - mod.CUBE_ITEM_EXPANDED_WIDTH
        == chrome.CUBE_STACK_TOP_INSET * 2
    )
    assert (
        mod.CUBE_STACK_COMPACT_WIDTH - mod.CUBE_ITEM_COMPACT_WIDTH
        == chrome.CUBE_STACK_TOP_INSET * 2
    )


def test_cube_close_button_centers_in_text_cutoff_reserve():
    """Expanded cube close button should center between text cutoff and card edge."""
    mod = _import_stack_panel_module()
    item_width = mod.CUBE_ITEM_EXPANDED_WIDTH
    button_width = mod.CUBE_ITEM_CLOSE_BUTTON_SIZE

    close_x = mod.CubeItem._close_button_x(item_width, button_width)
    close_center = close_x + (button_width / 2)
    text_cutoff_x = item_width - mod.CUBE_ITEM_CLOSE_TEXT_RESERVE
    reserve_center = text_cutoff_x + (mod.CUBE_ITEM_CLOSE_TEXT_RESERVE / 2)

    assert close_center == reserve_center


def test_cube_stack_text_rows_center_against_icon():
    """The two text rows should be vertically centered in the expanded cube tab."""
    mod = _import_stack_panel_module()
    text_rect = mod.QRectF(72, 0, 68, mod.CUBE_ITEM_HEIGHT)

    primary_rect, secondary_rect = mod.CubeItem._text_row_rects(text_rect)
    block_top = primary_rect.y()
    block_bottom = secondary_rect.y() + secondary_rect.height()
    block_center = block_top + ((block_bottom - block_top) / 2)

    assert block_center == mod.CUBE_ITEM_HEIGHT / 2


def test_cube_stack_item_reapplies_acrylic_card_fill_from_top_level_window() -> None:
    """Cube items should use the stronger acrylic card fill when acrylic is active."""

    mod = _import_stack_panel_module()
    style = importlib.import_module("substitute.presentation.shell.chrome_style")
    item = mod.CubeItem.__new__(mod.CubeItem)
    item.selected_fill_color = None
    item.update = lambda: None
    item.window = lambda: SimpleNamespace(_backdrop_mode="acrylic")

    mod.CubeItem._apply_theme_styles(item)

    assert item.selected_fill_color == style.winui_card_fill_color("acrylic")


def test_workflow_tab_corner_overlay_class_is_exported():
    """Workflow module should expose the parent-owned overlay class."""
    mod = _import_workflow_tabs_module()

    assert mod.WorkflowTabCornerOverlay.__name__ == "WorkflowTabCornerOverlay"


def test_cube_stack_indicator_overlay_class_is_exported():
    """Cube stack module should expose the parent-owned indicator overlay class."""

    mod = _import_stack_panel_module()

    assert mod.CubeStackIndicatorOverlay.__name__ == "CubeStackIndicatorOverlay"


def test_cube_stack_selected_indicator_uses_viewport_overlay_layer():
    """Cube stack should paint the selected indicator above item widgets."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "presentation"
        / "workflows"
        / "cube_stack_view.py"
    )
    source = source_path.read_text(encoding="utf-8")
    stack_paint_event = source.split(
        "def paintEvent(self, event: QMouseEvent) -> None:"
    )[1].split("def mousePressEvent", maxsplit=1)[0]

    assert "class CubeStackIndicatorOverlay(QWidget):" in source
    assert "super().__init__(stack.view)" in source
    assert "self.raise_()" in source
    assert "self.indicatorOverlay = CubeStackIndicatorOverlay(self)" in source
    assert "drawRoundedRect" not in stack_paint_event
    assert "themeColor()" not in stack_paint_event


def test_cube_stack_set_current_index_ignores_invalid_index():
    """setCurrentIndex should no-op for invalid index."""
    mod = _import_stack_panel_module()
    item = _TabItem("cube")
    fake = SimpleNamespace(
        items=[item],
        _currentIndex=0,
        slideAni=_SlideAnimation(),
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: item,
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.setCurrentIndex(fake, 5)

    assert fake._currentIndex == 0
    assert fake.slideAni.started == 0


def test_cube_stack_set_current_index_animates_indicator_and_selection():
    """Valid setCurrentIndex updates selected tab and indicator animation target."""
    mod = _import_stack_panel_module()
    item0 = _TabItem("cube0")
    item1 = _TabItem("cube1")
    slide = _SlideAnimation()
    fake = SimpleNamespace(
        items=[item0, item1],
        _currentIndex=0,
        slideAni=slide,
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.setCurrentIndex(fake, 1)

    assert item0.selected is False
    assert item1.selected is True
    assert fake._currentIndex == 1
    assert slide.end_value == item1.y() + item1.height() // 2 - 8
    assert slide.duration == 220
    assert slide.started == 1


def test_cube_stack_reselects_current_index_to_realign_indicator():
    """Selecting the current tab again should repair stale indicator geometry."""

    mod = _import_stack_panel_module()
    item = _TabItem("cube")
    item._y = 20
    indicator_values: list[int] = []
    fake = SimpleNamespace(
        items=[item],
        _currentIndex=0,
        slideAni=_SlideAnimation(),
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda value: indicator_values.append(value),
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.realign_indicator(fake, animated=False)
    item._y = 84
    mod.CubeStack.setCurrentIndex(fake, 0)

    assert item.selected is True
    assert fake.slideAni.end_value == item.y() + item.height() // 2 - 8
    assert fake.slideAni.started == 1


def test_cube_stack_select_cube_uses_route_key_for_selection():
    """Route-key selection should resolve the current index from itemMap."""

    mod = _import_stack_panel_module()
    item0 = _TabItem("cube-a")
    item1 = _TabItem("cube-b")
    slide = _SlideAnimation()
    fake = SimpleNamespace(
        items=[item0, item1],
        itemMap={"cube-a": item0, "cube-b": item1},
        _currentIndex=0,
        slideAni=slide,
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.select_cube(fake, "cube-b", animated=True)

    assert item0.selected is False
    assert item1.selected is True
    assert fake._currentIndex == 1
    assert slide.end_value == item1.y() + item1.height() // 2 - 8


def test_cube_stack_indicator_realign_is_coalesced_until_layout_tick(monkeypatch):
    """Tab layout mutations should schedule one deferred indicator realign."""

    mod = _import_stack_panel_module()
    callbacks = []
    monkeypatch.setattr(
        mod.QTimer,
        "singleShot",
        staticmethod(lambda _msec, callback: callbacks.append(callback)),
    )
    complete_calls: list[str] = []
    fake = SimpleNamespace(
        _indicator_realign_pending=False,
        _complete_indicator_realign=lambda: complete_calls.append("complete"),
    )

    mod.CubeStack._schedule_indicator_realign(fake)
    mod.CubeStack._schedule_indicator_realign(fake)

    assert len(callbacks) == 1
    assert fake._indicator_realign_pending is True
    callbacks[0]()
    assert complete_calls == ["complete"]
