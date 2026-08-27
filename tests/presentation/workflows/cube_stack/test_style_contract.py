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

"""Cube stack style and geometry contracts."""

from __future__ import annotations

from typing import Any

import importlib
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QRectF
from tests.presentation.workflows.tab_stack_support import (
    _Signal,
    _TabItem,
    _import_stack_panel_module,
)


def test_cube_stack_on_tab_renamed_emits_rename_request_without_mutating_keys() -> None:
    """Cube tab inline rename should defer alias resolution to higher layers."""
    mod = _import_stack_panel_module()
    tab_item = _TabItem("cube_old")
    fake: Any = SimpleNamespace(
        itemMap={"cube_old": tab_item, "cube_new": _TabItem("cube_new")},
        cubeRenameRequested=_Signal(),
    )

    mod.CubeStack._onTabRenamed(fake, tab_item, "cube_new")

    assert tab_item.routeKey() == "cube_old"
    assert fake.itemMap == {"cube_old": tab_item, "cube_new": fake.itemMap["cube_new"]}
    assert fake.cubeRenameRequested.calls == [("cube_old", "cube_new")]


def test_cube_stack_on_alias_edit_requested_emits_route_key() -> None:
    """Cube tab edit requests should be routed without mutating aliases."""

    mod = _import_stack_panel_module()
    tab_item = _TabItem("cube_old")
    fake: Any = SimpleNamespace(cubeRenameEditRequested=_Signal())

    mod.CubeStack._onAliasEditRequested(fake, tab_item)

    assert tab_item.routeKey() == "cube_old"
    assert fake.cubeRenameEditRequested.calls == [("cube_old",)]


def test_cube_stack_item_keeps_non_workflow_selected_style() -> None:
    """Cube tabs should not inherit the workflow connected-tab chrome."""
    mod = _import_stack_panel_module()

    assert mod.CubeItem.fixed_height == mod.CUBE_ITEM_HEIGHT
    assert mod.CubeItem.selected_accent_position == "bottom"
    assert mod.CubeItem.selected_bottom_corner_radius == 0.0
    assert mod.CubeItem.selected_bottom_corner_width == 0.0
    assert mod.CubeItem.selected_connects_to_bottom_surface is False
    assert mod.CubeItem.selected_fill_color in {
        (255, 255, 255, 179),
        (255, 255, 255, 13),
    }
    assert mod.CubeItem.selected_bottom_border_mode == "cube"
    assert mod.CubeItem.unselected_separator_color is None
    assert mod.CubeItem.unselected_top_rounded_only is False


def test_cube_stack_expanded_icon_uses_equal_outer_insets() -> None:
    """Expanded cube icons should use the same left and vertical padding."""
    mod = _import_stack_panel_module()

    expected_icon_size = mod.CUBE_ITEM_HEIGHT - (mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2)

    assert mod.CUBE_ITEM_ICON_SIZE_EXPANDED == expected_icon_size


def test_cube_stack_expanded_icon_matches_stacked_text_height() -> None:
    """Expanded cube icons should be the same height as the two text rows."""
    mod = _import_stack_panel_module()

    assert mod.CUBE_ITEM_ICON_SIZE_EXPANDED == mod.CUBE_ITEM_TEXT_BLOCK_HEIGHT
    assert mod.CUBE_ITEM_HEIGHT == mod.CUBE_ITEM_TEXT_BLOCK_HEIGHT + (
        mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2
    )


def test_cube_stack_compact_icon_keeps_expanded_size() -> None:
    """Compact mode should keep the same cube icon size and enough item width."""
    mod = _import_stack_panel_module()

    assert mod.CUBE_ITEM_ICON_SIZE_COMPACT == mod.CUBE_ITEM_ICON_SIZE_EXPANDED
    assert mod.CUBE_ITEM_COMPACT_WIDTH == mod.CUBE_ITEM_ICON_SIZE_COMPACT + (
        mod.CUBE_ITEM_ICON_INSET_EXPANDED * 2
    )


def test_cube_stack_side_insets_match_toolbar_inset() -> None:
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


def test_cube_close_button_centers_in_text_cutoff_reserve() -> None:
    """Expanded cube close button should center between text cutoff and card edge."""
    mod = _import_stack_panel_module()
    item_width = mod.CUBE_ITEM_EXPANDED_WIDTH
    button_width = mod.CUBE_ITEM_CLOSE_BUTTON_SIZE

    close_x = mod.CubeItem._close_button_x(item_width, button_width)
    close_center = close_x + (button_width / 2)
    text_cutoff_x = item_width - mod.CUBE_ITEM_CLOSE_TEXT_RESERVE
    reserve_center = text_cutoff_x + (mod.CUBE_ITEM_CLOSE_TEXT_RESERVE / 2)

    assert close_center == reserve_center


def test_cube_stack_text_rows_center_against_icon() -> None:
    """The two text rows should be vertically centered in the expanded cube tab."""
    mod = _import_stack_panel_module()
    text_rect = QRectF(72, 0, 68, mod.CUBE_ITEM_HEIGHT)

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


def test_cube_stack_indicator_overlay_class_is_exported() -> None:
    """Cube stack module should expose the parent-owned indicator overlay class."""

    mod = _import_stack_panel_module()

    assert mod.CubeStackIndicatorOverlay.__name__ == "CubeStackIndicatorOverlay"


def test_cube_stack_selected_indicator_uses_viewport_overlay_layer() -> None:
    """Cube stack should paint the selected indicator above item widgets."""

    stack_source_path = (
        Path(__file__).parents[4]
        / "substitute"
        / "presentation"
        / "workflows"
        / "cube_stack_view.py"
    )
    overlay_source_path = stack_source_path.with_name("cube_stack_indicator_overlay.py")
    stack_source = stack_source_path.read_text(encoding="utf-8")
    overlay_source = overlay_source_path.read_text(encoding="utf-8")
    stack_paint_event = stack_source.split(
        "def paintEvent(self, event: QMouseEvent) -> None:"
    )[1].split("def mousePressEvent", maxsplit=1)[0]

    assert "class CubeStackIndicatorOverlay(QWidget):" in overlay_source
    assert "super().__init__(stack.view)" in overlay_source
    assert "self.raise_()" in overlay_source
    assert "self.indicatorOverlay = CubeStackIndicatorOverlay(self)" in stack_source
    assert "drawRoundedRect" not in stack_paint_event
    assert "themeColor()" not in stack_paint_event
