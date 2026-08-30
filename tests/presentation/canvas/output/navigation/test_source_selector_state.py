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

"""Verify source-selector and compare-source button presentation state."""

from __future__ import annotations


from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    SourceSelectorButtonState,
    apply_compare_source_button_state,
    apply_source_selector_button_state,
    compare_source_button_state,
    source_selector_button_state,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    SelectorButtonSpy,
)


def test_source_selector_button_state_sets_tooltip_for_elided_text() -> None:
    """Collapsed source selector state should expose full labels as tooltips."""

    assert source_selector_button_state(
        full_text="Very long source label",
        display_text="Very long...",
        width=260,
        visible=True,
    ) == SourceSelectorButtonState(
        text="Very long...",
        tooltip="Very long source label",
        width=260,
        visible=True,
    )


def test_source_selector_button_state_preserves_authoritative_visibility() -> None:
    """Collapsed source selector state should preserve prepared visibility."""

    assert (
        source_selector_button_state(
            full_text="Text",
            display_text="Text",
            width=58,
            visible=False,
        ).visible
        is False
    )


def test_compare_source_button_state_sets_tooltip_for_elided_text() -> None:
    """Compare source selector state should expose full labels as tooltips."""

    assert compare_source_button_state(
        full_text="Very long comparison source",
        display_text="Very long...",
        width=260,
        visible=True,
    ) == SourceSelectorButtonState(
        text="Very long...",
        tooltip="Very long comparison source",
        width=260,
        visible=True,
    )


def test_compare_source_button_state_preserves_hidden_visibility() -> None:
    """Compare source selector state should preserve prepared visibility."""

    assert compare_source_button_state(
        full_text="Text",
        display_text="Text",
        width=58,
        visible=False,
    ) == SourceSelectorButtonState(
        text="Text",
        tooltip="",
        width=58,
        visible=False,
    )


def test_apply_source_selector_button_state_updates_button() -> None:
    """Source selector adapter should apply text, tooltip, width, and visibility."""

    button = SelectorButtonSpy()

    button_state = apply_source_selector_button_state(
        button,
        full_text="Primary Source",
        display_text="Primary...",
        width=96,
        visible=True,
    )

    assert button_state == SourceSelectorButtonState(
        text="Primary...",
        tooltip="Primary Source",
        width=96,
        visible=True,
    )
    assert button.text == "Primary..."
    assert button.tooltip == "Primary Source"
    assert button.fixed_width == 96
    assert button.visible is True


def test_apply_compare_source_button_state_updates_button() -> None:
    """Compare source adapter should apply text, tooltip, width, and visibility."""

    button = SelectorButtonSpy()

    button_state = apply_compare_source_button_state(
        button,
        full_text="Comparison Source",
        display_text="Comparison...",
        width=124,
        visible=True,
    )

    assert button_state == SourceSelectorButtonState(
        text="Comparison...",
        tooltip="Comparison Source",
        width=124,
        visible=True,
    )
    assert button.text == "Comparison..."
    assert button.tooltip == "Comparison Source"
    assert button.fixed_width == 124
    assert button.visible is True
