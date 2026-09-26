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

"""Project observed mpv state into application playback diagnostics."""

from substitute.application.ports.video import (
    VideoPlaybackDiagnostics,
    VideoPresentationSampling,
)
from substitute.domain.generation import VideoPlaybackSettings
from substitute.infrastructure.video.mpv_playback_fallback import playback_fallback


def build_playback_diagnostics(
    *,
    settings: VideoPlaybackSettings,
    render_api: bool,
    actual_video_output: str | None,
    gpu_api: str | None,
    gpu_context: str | None,
    hardware_decoder_observed: bool,
    hardware_decoder: str | None,
    pixel_format: str | None,
    codec: str | None,
    presentation_sampling: VideoPresentationSampling,
) -> VideoPlaybackDiagnostics:
    """Build diagnostics from the native properties owned by the player."""

    return VideoPlaybackDiagnostics(
        requested_hardware_decoding=settings.hardware_decoding,
        requested_renderer=settings.renderer,
        actual_video_output=actual_video_output,
        gpu_api=gpu_api,
        gpu_context=gpu_context,
        hardware_decoder=hardware_decoder,
        pixel_format=pixel_format,
        codec=codec,
        fallback=playback_fallback(
            settings=settings,
            render_api=render_api,
            actual_video_output=actual_video_output,
            hardware_decoder_observed=hardware_decoder_observed,
            hardware_decoder=hardware_decoder,
        ),
        presentation_sampling=presentation_sampling,
    )


__all__ = ["build_playback_diagnostics"]
