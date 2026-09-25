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

"""Serialize native video-output qualification observations."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.video import (
    VideoPlaybackSnapshot,
    VideoPresentationSampling,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
    VideoViewportState,
)
from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage


def write_video_output_evidence(
    *,
    path: Path,
    theme: str,
    soak_seconds: float,
    page: VideoPlaybackPage,
    canvas: OutputCanvas,
    ready: VideoPlaybackSnapshot,
    next_time: float,
    previous_time: float,
    loop_off_end_time: float,
    loop_restart_time: float,
    soak_end_time: float,
    actual_size_zoom: float,
    actual_size_sampling: VideoPresentationSampling,
    fitted_sampling: VideoPresentationSampling,
    wheel_viewport: VideoViewportState,
    dragged_viewport: VideoViewportState,
    same_navigation_row: bool,
    native_stacking: dict[str, bool],
    transparent_bars: dict[str, object],
    rehosting: dict[str, object],
) -> None:
    """Write one stable JSON record for the completed native scenario."""

    evidence = {
        "schema_version": "2",
        "theme": theme,
        "mixed_grid_badge": True,
        "next_frame": next_time,
        "previous_frame": previous_time,
        "loop_defaulted_on": ready.loop_enabled,
        "loop_off_end_time": loop_off_end_time,
        "loop_restart_time": loop_restart_time,
        "soak_seconds": soak_seconds,
        "soak_end_time": soak_end_time,
        "loop_reenabled": page.controller.snapshot.loop_enabled,
        "hidden_paused": page.controller.snapshot.paused,
        "hidden_muted": page.controller.snapshot.effectively_muted,
        "source_navigation_items": tuple(canvas.tabbar.items),
        "video_uses_compact_source_picker": True,
        "actual_size_zoom": actual_size_zoom,
        "actual_size_sampling": actual_size_sampling.value,
        "fitted_sampling": fitted_sampling.value,
        "wheel_zoom": wheel_viewport.zoom,
        "wheel_pan": [wheel_viewport.pan_x, wheel_viewport.pan_y],
        "pointer_pan": [dragged_viewport.pan_x, dragged_viewport.pan_y],
        "fit_restored": page.viewport_state.mode is VideoViewportMode.FIT,
        "rendered_hover_changed": True,
        "controls_share_output_navigation_row": same_navigation_row,
        "native_stacking": native_stacking,
        "device_pixel_ratio": page.render_surface.devicePixelRatioF(),
        "diagnostics": {
            "codec": ready.diagnostics.codec,
            "pixel_format": ready.diagnostics.pixel_format,
            "renderer": ready.diagnostics.actual_video_output,
        },
        "transparent_bars": transparent_bars,
        "rehosting": rehosting,
    }
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )


__all__ = ["write_video_output_evidence"]
