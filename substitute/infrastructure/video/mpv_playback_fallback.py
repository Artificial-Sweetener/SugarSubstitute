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

"""Classify observed libmpv playback fallbacks against requested policy."""

from __future__ import annotations

from substitute.application.ports.video import VideoPlaybackFallback
from substitute.domain.generation import (
    VideoHardwareDecoding,
    VideoPlaybackSettings,
    VideoRenderer,
)


def playback_fallback(
    *,
    settings: VideoPlaybackSettings,
    render_api: bool,
    actual_video_output: str | None,
    hardware_decoder_observed: bool,
    hardware_decoder: str | None,
) -> VideoPlaybackFallback | None:
    """Return the user-relevant fallback implied by current native observations."""

    if (
        settings.hardware_decoding is VideoHardwareDecoding.AUTO
        and hardware_decoder_observed
        and hardware_decoder in {None, "no"}
    ):
        return VideoPlaybackFallback.SOFTWARE_DECODING
    requested_output = {
        VideoRenderer.GPU_NEXT: "gpu-next",
        VideoRenderer.GPU: "gpu",
    }.get(settings.renderer)
    if (
        not render_api
        and requested_output is not None
        and actual_video_output is not None
        and actual_video_output != requested_output
    ):
        return VideoPlaybackFallback.RENDERER
    return None


__all__ = ["playback_fallback"]
