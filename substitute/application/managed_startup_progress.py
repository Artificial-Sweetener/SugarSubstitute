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

"""Own user-facing progress policy for managed ComfyUI startup."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.launch_splash.activity import (
    EXTENDED_ACTIVITY_SECONDS,
    LONG_ACTIVITY_SECONDS,
    SplashActivityStage,
    splash_activity_stage,
)

LONG_STARTUP_SECONDS = LONG_ACTIVITY_SECONDS
POSSIBLE_STARTUP_ISSUE_SECONDS = EXTENDED_ACTIVITY_SECONDS
_ANIMATED_ELLIPSIS_FRAMES = (".", "..", "...")


def managed_startup_progress_text(
    *,
    elapsed_seconds: float,
    animation_frame: int,
) -> ApplicationText:
    """Return concise localized progress copy for one startup age and frame."""

    dots = _ANIMATED_ELLIPSIS_FRAMES[animation_frame % len(_ANIMATED_ELLIPSIS_FRAMES)]
    stage = splash_activity_stage(elapsed_seconds)
    if stage is SplashActivityStage.EXTENDED_WAIT:
        return app_text(
            "Still waiting—custom nodes, slow storage, or a startup issue may be "
            "delaying ComfyUI%1",
            dots,
        )
    if stage is SplashActivityStage.LONG_WAIT:
        return app_text("ComfyUI is taking longer than usual%1", dots)
    return app_text("Waiting for ComfyUI to become ready%1", dots)


__all__ = [
    "LONG_STARTUP_SECONDS",
    "POSSIBLE_STARTUP_ISSUE_SECONDS",
    "managed_startup_progress_text",
]
