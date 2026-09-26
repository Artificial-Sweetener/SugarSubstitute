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

"""Qualify QPane-compatible video sampling through native Output controls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports.video import VideoPresentationSampling
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
)
from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage
from tools.video_output_qualification_support import (
    capture,
    find_button,
    native_click,
    wait_until,
)


@dataclass(frozen=True, slots=True)
class VideoSamplingEvidence:
    """Record native sampling choices on both sides of the two-times threshold."""

    actual_size_zoom: float
    actual_size_sampling: VideoPresentationSampling
    fitted_sampling: VideoPresentationSampling


def qualify_video_sampling(
    *,
    application: QApplication,
    root: QWidget,
    page: VideoPlaybackPage,
    evidence_dir: Path,
) -> VideoSamplingEvidence:
    """Prove 1:1 stays filtered while high physical scale becomes nearest."""

    actual_size_button = find_button(page, "Show video at actual size")
    fit_button = find_button(page, "Fit video")
    native_click(root, actual_size_button, application)
    wait_until(
        application,
        lambda: (
            page.viewport_state.mode is VideoViewportMode.ACTUAL_SIZE
            and page.controller.snapshot.diagnostics.presentation_sampling
            is VideoPresentationSampling.BILINEAR
        ),
        label="1:1 bilinear video viewport",
    )
    actual_size_zoom = page.viewport_state.zoom
    actual_size_sampling = page.controller.snapshot.diagnostics.presentation_sampling
    capture(root, evidence_dir / "video-detail-actual-size.png")
    native_click(root, fit_button, application)
    wait_until(
        application,
        lambda: (
            page.viewport_state.mode is VideoViewportMode.FIT
            and page.controller.snapshot.diagnostics.presentation_sampling
            is VideoPresentationSampling.NEAREST
        ),
        label="high-scale nearest video viewport",
    )
    return VideoSamplingEvidence(
        actual_size_zoom=actual_size_zoom,
        actual_size_sampling=actual_size_sampling,
        fitted_sampling=page.controller.snapshot.diagnostics.presentation_sampling,
    )


__all__ = ["VideoSamplingEvidence", "qualify_video_sampling"]
