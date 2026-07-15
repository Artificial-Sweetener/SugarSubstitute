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

"""Define shell progress projection rendering modes."""

from __future__ import annotations

from enum import Enum


class ProgressProjectionMode(Enum):
    """Describe why progress is being projected onto shared shell widgets."""

    LIVE_UPDATE = "live_update"
    SELECTION_REPLAY = "selection_replay"
    CLEAR = "clear"

    @property
    def animated(self) -> bool:
        """Return whether value changes should use progress-bar animation."""

        return self is ProgressProjectionMode.LIVE_UPDATE


def set_progress_bar_value(
    bar: object,
    value: int,
    *,
    mode: ProgressProjectionMode,
) -> None:
    """Set one progress bar value with animation policy for the projection source."""

    set_value = getattr(bar, "setValue", None)
    if not callable(set_value):
        return
    if mode.animated:
        set_value(value)
        return

    set_use_animation = getattr(bar, "setUseAni", None)
    is_use_animation = getattr(bar, "isUseAni", None)
    if not callable(set_use_animation) or not callable(is_use_animation):
        set_value(value)
        return

    previous_animation_state = bool(is_use_animation())
    set_use_animation(False)
    try:
        set_value(value)
    finally:
        set_use_animation(previous_animation_state)


__all__ = [
    "ProgressProjectionMode",
    "set_progress_bar_value",
]
