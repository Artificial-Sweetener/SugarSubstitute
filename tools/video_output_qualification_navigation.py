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

"""Qualify Space-owned QPane-style video viewport navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
    VideoViewportState,
)
from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage
from tools.video_output_qualification_support import (
    capture,
    key_press,
    key_release,
    native_double_click,
    native_drag,
    native_wheel,
    wait_until,
)


@dataclass(frozen=True, slots=True)
class VideoNavigationEvidence:
    """Retain the observed anchored-zoom and pointer-pan states."""

    wheel_viewport: VideoViewportState
    dragged_viewport: VideoViewportState


def qualify_space_pan_zoom(
    *,
    application: QApplication,
    root: QWidget,
    page: VideoPlaybackPage,
    evidence_dir: Path,
) -> VideoNavigationEvidence:
    """Exercise transient navigation, anchored zoom, drag pan, and mode toggles."""

    paused_before_navigation = page.controller.snapshot.paused
    key_press(page.render_surface, Qt.Key.Key_Space, application)
    if not page.pan_zoom_active:
        raise RuntimeError("Holding Space did not activate video pan/zoom.")
    _toggle_one_to_one_and_fit(application=application, root=root, page=page)
    native_wheel(
        root,
        page.render_surface,
        240,
        application,
        horizontal_fraction=0.75,
        vertical_fraction=0.25,
    )
    wait_until(
        application,
        lambda: page.viewport_state.mode is VideoViewportMode.CUSTOM,
        label="pointer-wheel video zoom",
    )
    wheel_viewport = page.viewport_state
    _assert_pointer_anchor(page, wheel_viewport)
    native_drag(
        root,
        page.render_surface,
        application,
        start=(0.5, 0.5),
        finish=(0.62, 0.58),
    )
    wait_until(
        application,
        lambda: (
            page.viewport_state.pan_x != wheel_viewport.pan_x
            and page.viewport_state.pan_y != wheel_viewport.pan_y
        ),
        label="Space-drag video pan",
    )
    dragged_viewport = page.viewport_state
    capture(root, evidence_dir / "video-detail-zoomed-panned.png")
    native_double_click(root, page.render_surface, application)
    wait_until(
        application,
        lambda: page.viewport_state.mode is VideoViewportMode.FIT,
        label="double-click fit after pointer viewport changes",
    )
    key_release(page.render_surface, Qt.Key.Key_Space, application)
    if page.pan_zoom_active:
        raise RuntimeError("Releasing Space left video pan/zoom active.")
    if page.controller.snapshot.paused is not paused_before_navigation:
        raise RuntimeError("Space pan/zoom unexpectedly changed playback state.")
    return VideoNavigationEvidence(wheel_viewport, dragged_viewport)


def _toggle_one_to_one_and_fit(
    *,
    application: QApplication,
    root: QWidget,
    page: VideoPlaybackPage,
) -> None:
    """Prove both double-click transitions while Space remains held."""

    for expected_mode, label in (
        (VideoViewportMode.ACTUAL_SIZE, "Space double-click 1:1 video view"),
        (VideoViewportMode.FIT, "Space double-click fitted video view"),
    ):
        native_double_click(
            root,
            page.render_surface,
            application,
            horizontal_fraction=0.75,
            vertical_fraction=0.25,
        )
        wait_until(
            application,
            lambda: page.viewport_state.mode is expected_mode,
            label=label,
        )


def _assert_pointer_anchor(
    page: VideoPlaybackPage,
    viewport: VideoViewportState,
) -> None:
    """Require the source coordinate under the wheel pointer to remain fixed."""

    surface_width = max(1, page.render_surface.width())
    surface_height = max(1, page.render_surface.height())
    anchor = page.last_zoom_anchor
    if anchor is None:
        raise RuntimeError("Video navigation did not record its wheel anchor.")
    expected_x = round((surface_width - 1) * 0.75)
    expected_y = round((surface_height - 1) * 0.25)
    if abs(anchor.x() - expected_x) > 2 or abs(anchor.y() - expected_y) > 2:
        raise RuntimeError("Native wheel input reached an unexpected video coordinate.")
    anchor_x = anchor.x() / surface_width * 2.0 - 1.0
    anchor_y = anchor.y() / surface_height * 2.0 - 1.0
    anchored_x = (anchor_x - viewport.pan_x) / viewport.zoom
    anchored_y = (anchor_y - viewport.pan_y) / viewport.zoom
    if abs(anchored_x - anchor_x) >= 1e-6 or abs(anchored_y - anchor_y) >= 1e-6:
        raise RuntimeError("Video wheel zoom did not retain its pointer anchor.")


__all__ = ["VideoNavigationEvidence", "qualify_space_pan_zoom"]
