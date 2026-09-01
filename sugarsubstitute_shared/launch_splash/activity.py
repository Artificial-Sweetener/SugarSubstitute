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

"""Define transport-safe splash activity copy and timing policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

LONG_ACTIVITY_SECONDS = 120.0
EXTENDED_ACTIVITY_SECONDS = 300.0
ACTIVITY_FRAME_SECONDS = 1.0
_ACTIVITY_DOT_FRAMES = (".", "..", "...")


class SplashActivityStage(Enum):
    """Identify the message stage selected for an activity age."""

    INITIAL = "initial"
    LONG_WAIT = "long_wait"
    EXTENDED_WAIT = "extended_wait"


@dataclass(frozen=True, slots=True)
class SplashActivity:
    """Carry localized base copy for one long-running splash operation."""

    initial_text: str
    long_wait_text: str
    extended_wait_text: str

    def __post_init__(self) -> None:
        """Reject activity copy that cannot produce every required stage."""

        if not all(
            text.strip()
            for text in (
                self.initial_text,
                self.long_wait_text,
                self.extended_wait_text,
            )
        ):
            raise ValueError("Splash activity text must not be empty.")


def splash_activity_stage(elapsed_seconds: float) -> SplashActivityStage:
    """Return the activity stage for one non-negative elapsed duration."""

    elapsed = max(0.0, elapsed_seconds)
    if elapsed >= EXTENDED_ACTIVITY_SECONDS:
        return SplashActivityStage.EXTENDED_WAIT
    if elapsed >= LONG_ACTIVITY_SECONDS:
        return SplashActivityStage.LONG_WAIT
    return SplashActivityStage.INITIAL


def splash_activity_dots(elapsed_seconds: float) -> str:
    """Return the continuously cycling dot suffix for one activity age."""

    elapsed = max(0.0, elapsed_seconds)
    frame = int(elapsed / ACTIVITY_FRAME_SECONDS)
    return _ACTIVITY_DOT_FRAMES[frame % len(_ACTIVITY_DOT_FRAMES)]


def render_splash_activity(activity: SplashActivity, elapsed_seconds: float) -> str:
    """Render the selected localized activity stage with animated dots."""

    stage = splash_activity_stage(elapsed_seconds)
    if stage is SplashActivityStage.EXTENDED_WAIT:
        base_text = activity.extended_wait_text
    elif stage is SplashActivityStage.LONG_WAIT:
        base_text = activity.long_wait_text
    else:
        base_text = activity.initial_text
    return f"{base_text.rstrip('.…')}{splash_activity_dots(elapsed_seconds)}"


__all__ = [
    "ACTIVITY_FRAME_SECONDS",
    "EXTENDED_ACTIVITY_SECONDS",
    "LONG_ACTIVITY_SECONDS",
    "SplashActivity",
    "SplashActivityStage",
    "render_splash_activity",
    "splash_activity_dots",
    "splash_activity_stage",
]
