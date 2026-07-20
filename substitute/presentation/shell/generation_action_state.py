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

"""Describe generation titlebar state without depending on Qt widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sugarsubstitute_shared.localization import ApplicationText

GenerationSelectedMode = Literal["generate", "continuous"]
GenerationPlayPresentationMode = Literal["generate", "continuous", "end_continuous"]


@dataclass(frozen=True)
class GenerationActionState:
    """Describe shell state needed to project generation titlebar actions."""

    selected_mode: GenerationSelectedMode
    continuous_active: bool
    backend_ready: bool
    workflow_runnable: bool
    settings_route_active: bool
    queue_has_active: bool
    queue_has_cancellable: bool
    pending_queue_count: int
    queue_has_visible_jobs: bool
    queue_panel_visible: bool

    def __post_init__(self) -> None:
        """Normalize externally gathered values before projection."""

        object.__setattr__(
            self, "pending_queue_count", max(0, self.pending_queue_count)
        )


@dataclass(frozen=True)
class GenerationActionPresentation:
    """Describe the complete titlebar generation control presentation."""

    play_mode: GenerationPlayPresentationMode
    play_enabled: bool
    play_tooltip: ApplicationText
    stop_enabled: bool
    skip_enabled: bool
    queue_primary_enabled: bool
    queue_badge_count: int
    queue_segment_visible: bool
    batch_accessory_visible: bool
    batch_accessory_enabled: bool
    mode_menu_enabled: bool


__all__ = [
    "GenerationActionPresentation",
    "GenerationActionState",
    "GenerationPlayPresentationMode",
    "GenerationSelectedMode",
]
