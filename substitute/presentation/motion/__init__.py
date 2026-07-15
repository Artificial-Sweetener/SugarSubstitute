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

"""Presentation-layer motion policy and reusable animation helpers."""

from .fluent_motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
    CUBE_STACK_INDICATOR_DURATION_MS,
    CUBE_STACK_MODE_DURATION_MS,
    ENTER_EASING_CURVE,
    EXIT_EASING_CURVE,
    HIGHLIGHT_SETTLE_DURATION_MS,
    INPUT_SCROLL_DURATION_MS,
    REVEAL_FADE_DURATION_MS,
    SCROLL_DURATION_MS,
    SETTINGS_NAV_INDICATOR_DURATION_MS,
    SETTINGS_PAGE_TRANSITION_DURATION_MS,
    SETTINGS_PAGE_TRANSITION_OFFSET,
    SIDE_PANEL_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    is_reduced_motion_enabled,
    resolve_motion_duration,
    restart_property_animation,
    stop_animation,
)

__all__ = [
    "ACCORDION_COLLAPSE_DURATION_MS",
    "ACCORDION_COLLAPSE_EASING_CURVE",
    "ACCORDION_EXPAND_DURATION_MS",
    "ACCORDION_EXPAND_EASING_CURVE",
    "CUBE_STACK_INDICATOR_DURATION_MS",
    "CUBE_STACK_MODE_DURATION_MS",
    "ENTER_EASING_CURVE",
    "EXIT_EASING_CURVE",
    "HIGHLIGHT_SETTLE_DURATION_MS",
    "INPUT_SCROLL_DURATION_MS",
    "REVEAL_FADE_DURATION_MS",
    "SCROLL_DURATION_MS",
    "SETTINGS_NAV_INDICATOR_DURATION_MS",
    "SETTINGS_PAGE_TRANSITION_DURATION_MS",
    "SETTINGS_PAGE_TRANSITION_OFFSET",
    "SIDE_PANEL_DURATION_MS",
    "TRANSFORM_EASING_CURVE",
    "is_reduced_motion_enabled",
    "resolve_motion_duration",
    "restart_property_animation",
    "stop_animation",
]
