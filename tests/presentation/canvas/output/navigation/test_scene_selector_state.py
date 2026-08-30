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

"""Verify scene-selector and compare-scene button presentation state."""

from __future__ import annotations


from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    SceneSelectorButtonState,
    apply_compare_scene_button_state,
    apply_scene_selector_button_state,
    compare_scene_button_state,
    compare_scene_full_text,
    scene_selector_button_state,
    scene_selector_full_text,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    SelectorButtonSpy,
)


def test_apply_scene_selector_button_state_updates_button() -> None:
    """Scene selector adapter should apply text, tooltip, width, and visibility."""

    button = SelectorButtonSpy()

    button_state = apply_scene_selector_button_state(
        button,
        full_text="Wide Scene",
        display_text="Wide...",
        width=84,
        visible=True,
    )

    assert button_state == SceneSelectorButtonState(
        text="Wide...",
        tooltip="Wide Scene",
        width=84,
        visible=True,
    )
    assert button.text == "Wide..."
    assert button.tooltip == "Wide Scene"
    assert button.fixed_width == 84
    assert button.visible is True


def test_compare_scene_full_text_uses_selected_scene_title() -> None:
    """Compare scene labels should use the selected concrete scene title."""

    scenes = (
        OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),
        OutputCanvasSceneGroup("run-2", "cafe", "Cafe", 1, ()),
    )

    assert (
        compare_scene_full_text(scenes, scene_key="portrait", scene_count=2)
        == "Portrait"
    )


def test_compare_scene_full_text_uses_all_without_scene_choice() -> None:
    """Compare scene labels should use All when no concrete scene is available."""

    scenes = (OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),)

    assert compare_scene_full_text(scenes, scene_key="portrait", scene_count=1) == "All"
    assert compare_scene_full_text(scenes, scene_key="missing", scene_count=2) == "All"


def test_compare_scene_button_state_sets_tooltip_for_elided_text() -> None:
    """Compare scene selector state should expose full labels as tooltips."""

    assert compare_scene_button_state(
        full_text="Very long comparison scene",
        display_text="Very long...",
        width=260,
        visible=True,
    ) == SceneSelectorButtonState(
        text="Very long...",
        tooltip="Very long comparison scene",
        width=260,
        visible=True,
    )


def test_apply_compare_scene_button_state_updates_button() -> None:
    """Compare scene adapter should apply text, tooltip, width, and visibility."""

    button = SelectorButtonSpy()

    button_state = apply_compare_scene_button_state(
        button,
        full_text="Comparison Scene",
        display_text="Comparison...",
        width=112,
        visible=True,
    )

    assert button_state == SceneSelectorButtonState(
        text="Comparison...",
        tooltip="Comparison Scene",
        width=112,
        visible=True,
    )
    assert button.text == "Comparison..."
    assert button.tooltip == "Comparison Scene"
    assert button.fixed_width == 112
    assert button.visible is True


def test_compare_scene_button_state_preserves_hidden_visibility() -> None:
    """Compare scene selector state should preserve prepared visibility."""

    assert compare_scene_button_state(
        full_text="All",
        display_text="All",
        width=58,
        visible=False,
    ) == SceneSelectorButtonState(
        text="All",
        tooltip="",
        width=58,
        visible=False,
    )


def test_scene_selector_full_text_uses_active_scene_title() -> None:
    """Scene selector labels should prefer the active scene title."""

    scenes = (
        OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),
        OutputCanvasSceneGroup("run-2", "cafe", "Cafe", 1, ()),
    )

    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="cafe",
            active_scene_overview=False,
        )
        == "Cafe"
    )


def test_scene_selector_full_text_uses_all_for_overview_or_missing_scene() -> None:
    """Scene selector labels should use All outside a concrete scene."""

    scenes = (OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),)

    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="portrait",
            active_scene_overview=True,
        )
        == "All"
    )
    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="missing",
            active_scene_overview=False,
        )
        == "All"
    )


def test_scene_selector_button_state_sets_tooltip_for_elided_text() -> None:
    """Scene selector state should expose full labels as tooltips."""

    assert scene_selector_button_state(
        full_text="Very long scene title",
        display_text="Very long...",
        width=260,
        visible=True,
    ) == SceneSelectorButtonState(
        text="Very long...",
        tooltip="Very long scene title",
        width=260,
        visible=True,
    )


def test_scene_selector_button_state_preserves_hidden_visibility() -> None:
    """Scene selector state should preserve prepared visibility."""

    assert scene_selector_button_state(
        full_text="Portrait",
        display_text="Portrait",
        width=92,
        visible=False,
    ) == SceneSelectorButtonState(
        text="Portrait",
        tooltip="",
        width=92,
        visible=False,
    )
