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

"""Project generation titlebar button presentation from shell state."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, app_text

from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationActionState,
    GenerationPlayPresentationMode,
)

_GENERATE_TOOLTIP = app_text("Generate")
_CONTINUOUS_TOOLTIP = app_text("Continuous")
_END_CONTINUOUS_TOOLTIP = app_text("Stop continuous after current job")


def project_generation_actions(
    state: GenerationActionState,
) -> GenerationActionPresentation:
    """Derive titlebar generation presentation from shell state."""

    normal_generation_available = _normal_generation_available(state)
    play_mode = _project_play_mode(state)
    play_enabled = state.continuous_active or normal_generation_available
    queue_badge_count = max(0, state.pending_queue_count)
    batch_accessory_visible = play_mode == "generate"
    mode_menu_enabled = normal_generation_available and not state.continuous_active

    return GenerationActionPresentation(
        play_mode=play_mode,
        play_enabled=play_enabled,
        play_tooltip=_play_tooltip(play_mode),
        stop_enabled=state.continuous_active or state.queue_has_cancellable,
        skip_enabled=state.continuous_active
        or (state.queue_has_active and queue_badge_count > 0),
        queue_primary_enabled=state.queue_has_visible_jobs,
        queue_badge_count=queue_badge_count,
        queue_segment_visible=not state.queue_panel_visible,
        batch_accessory_visible=batch_accessory_visible,
        batch_accessory_enabled=batch_accessory_visible and normal_generation_available,
        mode_menu_enabled=mode_menu_enabled,
    )


def _normal_generation_available(state: GenerationActionState) -> bool:
    """Return whether a new normal generation request can start."""

    return (
        state.backend_ready
        and not state.settings_route_active
        and state.workflow_runnable
        and not state.continuous_active
    )


def _project_play_mode(state: GenerationActionState) -> GenerationPlayPresentationMode:
    """Return the play segment presentation mode for current generation state."""

    if state.continuous_active:
        return "end_continuous"
    return state.selected_mode


def _play_tooltip(play_mode: GenerationPlayPresentationMode) -> ApplicationMessage:
    """Return tooltip text for one play segment presentation mode."""

    if play_mode == "generate":
        return _GENERATE_TOOLTIP
    if play_mode == "continuous":
        return _CONTINUOUS_TOOLTIP
    return _END_CONTINUOUS_TOOLTIP


__all__ = ["project_generation_actions"]
