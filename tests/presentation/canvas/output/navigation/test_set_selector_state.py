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

"""Verify set-selector and compare-set button presentation state."""

from __future__ import annotations


from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    SetSelectorButtonState,
    apply_compare_set_button_state,
    apply_set_selector_button_state,
    compare_set_button_state,
    set_selector_button_state,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    SelectorButtonSpy,
)


def test_set_selector_button_state_preserves_visible_state() -> None:
    """Set selector state should preserve prepared visible state."""

    assert set_selector_button_state(
        active_set_index=3,
        visible=True,
    ) == SetSelectorButtonState(text="3", visible=True)


def test_apply_set_selector_button_state_updates_button() -> None:
    """Set selector adapter should apply text and visibility to the host button."""

    button = SelectorButtonSpy()

    button_state = apply_set_selector_button_state(
        button,
        active_set_index=2,
        visible=True,
    )

    assert button_state == SetSelectorButtonState(text="2", visible=True)
    assert button.text == "2"
    assert button.visible is True


def test_set_selector_button_state_preserves_visibility_for_set_one() -> None:
    """Set selector state should preserve prepared visibility for any label."""

    assert set_selector_button_state(
        active_set_index=1,
        visible=True,
    ) == SetSelectorButtonState(text="1", visible=True)


def test_set_selector_button_state_preserves_hidden_state() -> None:
    """Set selector state should preserve prepared hidden state."""

    assert (
        set_selector_button_state(
            active_set_index=2,
            visible=False,
        ).visible
        is False
    )


def test_compare_set_button_state_preserves_visible_state() -> None:
    """Compare set selector state should preserve prepared visible state."""

    assert compare_set_button_state(
        set_index=4, visible=True
    ) == SetSelectorButtonState(
        text="4",
        visible=True,
    )


def test_apply_compare_set_button_state_updates_button() -> None:
    """Compare set adapter should apply text and visibility to the host button."""

    button = SelectorButtonSpy()

    button_state = apply_compare_set_button_state(
        button,
        set_index=3,
        visible=True,
    )

    assert button_state == SetSelectorButtonState(text="3", visible=True)
    assert button.text == "3"
    assert button.visible is True


def test_compare_set_button_state_preserves_hidden_state() -> None:
    """Compare set selector state should preserve prepared hidden state."""

    assert compare_set_button_state(
        set_index=1, visible=False
    ) == SetSelectorButtonState(
        text="1",
        visible=False,
    )
