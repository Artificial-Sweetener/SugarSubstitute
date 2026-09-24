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

"""Apply prepared Output selector state to opaque widget hosts."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    ToolTipTarget,
    set_fluent_tooltip_text,
)

from substitute.presentation.canvas.output.output_navigation_selector_state import (
    SceneSelectorButtonState,
    SetSelectorButtonState,
    SourceSelectorButtonState,
    compare_scene_button_state,
    compare_set_button_state,
    compare_source_button_state,
    scene_selector_button_state,
    set_selector_button_state,
    source_selector_button_state,
)


def apply_source_selector_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SourceSelectorButtonState:
    """Build and apply normal source-selector presentation state."""

    state = source_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )
    apply_source_button_state(button, state)
    return state


def apply_compare_source_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SourceSelectorButtonState:
    """Build and apply comparison source-selector presentation state."""

    state = compare_source_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )
    apply_source_button_state(button, state)
    return state


def apply_source_button_state(
    button: object,
    state: SourceSelectorButtonState,
) -> None:
    """Apply source-like selector presentation state to an opaque button."""

    _set_button_text(button, state.text)
    _set_button_tooltip(button, state.tooltip)
    _set_button_width(button, state.width)
    _set_button_visible(button, state.visible)


def apply_set_selector_button_state(
    button: object,
    *,
    active_set_index: int,
    visible: bool,
) -> SetSelectorButtonState:
    """Build and apply normal set-selector presentation state."""

    state = set_selector_button_state(
        active_set_index=active_set_index,
        visible=visible,
    )
    _apply_set_button_state(button, state)
    return state


def apply_compare_set_button_state(
    button: object,
    *,
    set_index: int,
    visible: bool,
) -> SetSelectorButtonState:
    """Build and apply comparison set-selector presentation state."""

    state = compare_set_button_state(set_index=set_index, visible=visible)
    _apply_set_button_state(button, state)
    return state


def sync_comparison_navigation_buttons(
    *,
    comparison_nav_container: object,
    enabled: bool,
    base_selection: object | None,
    comparison_selection: object | None,
    base_scene_button: object,
    base_set_button: object,
    base_source_button: object,
    comparison_scene_button: object,
    comparison_set_button: object,
    comparison_source_button: object,
    sync_scene_button: Callable[[str, object, object], None],
    sync_set_button: Callable[[str, object, object], None],
    sync_source_button: Callable[[str, object, object], None],
) -> bool:
    """Refresh each comparison bar from the selection rendered on that side."""

    if not enabled or base_selection is None or comparison_selection is None:
        hide_container = getattr(comparison_nav_container, "hide", None)
        if callable(hide_container):
            hide_container()
        return False

    for side, selection, scene_button, set_button, source_button in (
        (
            "base",
            base_selection,
            base_scene_button,
            base_set_button,
            base_source_button,
        ),
        (
            "comparison",
            comparison_selection,
            comparison_scene_button,
            comparison_set_button,
            comparison_source_button,
        ),
    ):
        sync_scene_button(side, scene_button, selection)
        sync_set_button(side, set_button, selection)
        sync_source_button(side, source_button, selection)
    return True


def apply_scene_selector_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SceneSelectorButtonState:
    """Build and apply normal scene-selector presentation state."""

    state = scene_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )
    apply_scene_button_state(button, state)
    return state


def apply_compare_scene_button_state(
    button: object,
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SceneSelectorButtonState:
    """Build and apply comparison scene-selector presentation state."""

    state = compare_scene_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )
    apply_scene_button_state(button, state)
    return state


def apply_scene_button_state(
    button: object,
    state: SceneSelectorButtonState,
) -> None:
    """Apply scene-like selector presentation state to an opaque button."""

    _set_button_text(button, state.text)
    _set_button_tooltip(button, state.tooltip)
    _set_button_width(button, state.width)
    _set_button_visible(button, state.visible)


def _apply_set_button_state(button: object, state: SetSelectorButtonState) -> None:
    """Apply set-selector state to an opaque button."""

    _set_button_text(button, state.text)
    _set_button_visible(button, state.visible)


def _set_button_text(button: object, text: str) -> None:
    """Set button text when the host exposes the expected method."""

    setter = getattr(button, "setText", None)
    if callable(setter):
        setter(text)


def _set_button_tooltip(button: object, text: str) -> None:
    """Set Fluent tooltip text when the host supports tooltips."""

    if hasattr(button, "setToolTip"):
        set_fluent_tooltip_text(cast(ToolTipTarget, button), text)


def _set_button_width(button: object, width: int) -> None:
    """Set a fixed button width when supported."""

    setter = getattr(button, "setFixedWidth", None)
    if callable(setter):
        setter(width)


def _set_button_visible(button: object, visible: bool) -> None:
    """Set button visibility when supported."""

    setter = getattr(button, "setVisible", None)
    if callable(setter):
        setter(visible)


__all__ = [
    "apply_compare_scene_button_state",
    "apply_compare_set_button_state",
    "apply_compare_source_button_state",
    "apply_scene_button_state",
    "apply_scene_selector_button_state",
    "apply_set_selector_button_state",
    "apply_source_button_state",
    "apply_source_selector_button_state",
    "sync_comparison_navigation_buttons",
]
