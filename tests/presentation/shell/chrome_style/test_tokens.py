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

"""Verify workflow chrome geometry and color tokens."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from substitute.presentation.shell import chrome_style


def _rgba(color: tuple[int, int, int, int]) -> str:
    """Format one token as a CSS rgba value."""
    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


def test_workflow_chrome_material_constants_match_mica_alt_plan() -> None:
    """Expose the canonical theme-aware washes and shell geometry."""
    assert chrome_style.BODY_MATERIAL_SURFACE_OBJECT_NAME == (
        "SubstituteBodyMaterialSurface"
    )
    assert chrome_style.body_material_wash_rgba() in (
        chrome_style.body_material_wash_style()
    )
    assert len(chrome_style.body_material_wash_color()) == 4
    assert len(chrome_style.winui_card_fill_color()) == 4
    assert len(chrome_style.winui_card_border_color()) == 4
    assert chrome_style.CUBE_STACK_TOP_INSET == 6
    assert len(chrome_style.workflow_chrome_wash_color()) == 4
    assert chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT == 4
    assert chrome_style.WORKFLOW_TITLEBAR_HEIGHT == 34
    assert chrome_style.WORKFLOW_TAB_CORNER_OVERLAY_WIDTH == 8.0
    assert chrome_style.WORKFLOW_TAB_BODY_TOP_RADIUS == 8.0
    assert chrome_style.WORKFLOW_TAB_BOTTOM_CORNER_RADIUS == 4.0
    assert chrome_style.WORKFLOW_TAB_BOTTOM_CORNER_WIDTH == 8.0
    assert chrome_style.WORKFLOW_TAB_INACTIVE_INSET == 1.0
    assert chrome_style.WORKFLOW_TAB_INACTIVE_RADIUS == 7.0
    assert len(chrome_style.workflow_tab_separator_rgba()) == 4
    assert chrome_style.WORKFLOW_TOOLBAR_VERTICAL_PADDING == 4
    assert chrome_style.WORKFLOW_TOOLBAR_CONTROL_HEIGHT == 36
    assert chrome_style.WORKFLOW_TOOLBAR_HEIGHT == 44
    assert chrome_style.APP_ORB_DIAMETER == 46
    assert chrome_style.APP_ORB_LEFT_MARGIN == 8
    assert chrome_style.APP_ORB_TOP == 6
    assert chrome_style.APP_ORB_RESERVED_WIDTH == (
        chrome_style.APP_ORB_LEFT_MARGIN + chrome_style.APP_ORB_DIAMETER + 8
    )
    assert chrome_style.APP_ORB_ICON_SIZE == 28
    assert chrome_style.APP_ORB_TAB_RESERVED_WIDTH == (
        chrome_style.APP_ORB_RESERVED_WIDTH - 14
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_RADIUS == 25.0
    assert chrome_style.APP_ORB_TAB_CUTOUT_OVERLAP == (
        chrome_style.APP_ORB_RESERVED_WIDTH - chrome_style.APP_ORB_TAB_RESERVED_WIDTH
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_CENTER_X == (
        chrome_style.APP_ORB_LEFT_MARGIN
        + chrome_style.APP_ORB_DIAMETER / 2
        - chrome_style.APP_ORB_TAB_RESERVED_WIDTH
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_CENTER_Y == (
        chrome_style.APP_ORB_TOP
        + chrome_style.APP_ORB_DIAMETER / 2
        - chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_ANIMATION_MS == 160
    assert chrome_style.WORKFLOW_TAB_HEIGHT == (
        chrome_style.WORKFLOW_TITLEBAR_HEIGHT
        - chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
    )


def test_acrylic_shell_washes_gain_opacity_without_becoming_opaque(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use stronger translucent washes for acrylic shell surfaces."""
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.body_material_wash_color() == (32, 32, 32, 150)
    assert chrome_style.body_material_wash_color("acrylic") == (32, 32, 32, 169)
    assert chrome_style.workflow_chrome_wash_color() == (44, 44, 44, 150)
    assert chrome_style.workflow_chrome_wash_color("acrylic") == (44, 44, 44, 169)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.body_material_wash_color("acrylic") == (251, 251, 251, 177)
    assert chrome_style.workflow_chrome_wash_color("acrylic") == (
        252,
        252,
        252,
        177,
    )


def test_winui_card_tokens_match_windows_card_resource_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose the canonical WinUI card fill and stroke tokens."""
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.winui_card_fill_color() == (255, 255, 255, 179)
    assert chrome_style.winui_card_fill_color("acrylic") == (255, 255, 255, 224)
    assert chrome_style.winui_card_border_color() == (0, 0, 0, 15)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.winui_card_fill_color() == (255, 255, 255, 13)
    assert chrome_style.winui_card_fill_color("acrylic") == (255, 255, 255, 16)
    assert chrome_style.winui_card_border_color() == (0, 0, 0, 25)


def test_field_row_divider_token_matches_card_stroke_tints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Match field-row dividers to the node-card stroke token."""
    assert chrome_style.field_row_divider_rgba().startswith("rgba(")

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.field_row_divider_rgba() == "rgba(0, 0, 0, 15)"
    assert chrome_style.field_row_divider_rgba() == _rgba(
        chrome_style.winui_card_border_color()
    )

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.field_row_divider_rgba() == "rgba(0, 0, 0, 25)"
    assert chrome_style.field_row_divider_rgba() == _rgba(
        chrome_style.winui_card_border_color()
    )


def test_floating_surface_uses_opaque_winui_findbar_colors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use opaque WinUI find-bar colors for floating shell surfaces."""
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.floating_surface_rgba() == "rgba(252, 252, 252, 255)"
    assert chrome_style.floating_surface_color() == QColor(252, 252, 252, 255)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.floating_surface_rgba() == "rgba(44, 44, 44, 255)"
    assert chrome_style.floating_surface_color() == QColor(44, 44, 44, 255)
    assert chrome_style.floating_surface_border_color() == QColor(255, 255, 255, 25)
    assert chrome_style.floating_surface_text_color() == QColor(255, 255, 255)


def test_winui_accent_button_disabled_tokens_match_fluent_primary_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirror Fluent primary-button tokens for disabled accent buttons."""
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.winui_accent_button_disabled_fill_color() == QColor(
        205,
        205,
        205,
    )
    assert chrome_style.winui_accent_button_disabled_foreground_color() == QColor(
        255,
        255,
        255,
        230,
    )

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.winui_accent_button_disabled_fill_color() == QColor(52, 52, 52)
    assert chrome_style.winui_accent_button_disabled_foreground_color() == QColor(
        255,
        255,
        255,
        110,
    )
