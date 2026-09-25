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

"""Qualify transparent video bars and Output canvas window transitions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget
from sugarsubstitute_shared.localization import app_text

from substitute.application.ports.video import VideoPlaybackState
from substitute.presentation.canvas.host.canvas_host import CanvasHost
from substitute.presentation.canvas.host.canvas_host_state import CanvasHostPage
from substitute.presentation.canvas.factory import (
    create_output_floating_chrome_factory,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
)
from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage
from substitute.presentation.shell.chrome_style import body_material_wash_color
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.workspace_body_material_surface import (
    WorkspaceBodyMaterialSurface,
)
from tools.video_output_qualification_support import (
    capture,
    find_button,
    find_slider,
    key_press,
    key_release,
    native_click,
    native_click_fraction,
    native_wheel,
    pump_events,
    wait_until,
)
from tools.video_output_qualification_volume import qualify_volume_flyout

_BACKDROP = QColor(37, 53, 71)


def create_qualification_host(canvas: OutputCanvas) -> tuple[CanvasHost, QMainWindow]:
    """Mount Output in its production dock owner over a known canvas wash."""

    host = CanvasHost(
        pages=(
            CanvasHostPage(
                route_key="Output",
                title=app_text("Output"),
                widget=canvas,
                floating_chrome_factory=create_output_floating_chrome_factory(),
            ),
        )
    )
    window = QMainWindow()
    window.setWindowTitle("SugarSubstitute video output qualification")
    palette = window.palette()
    palette.setColor(QPalette.ColorRole.Window, _BACKDROP)
    window.setPalette(palette)
    window.setAutoFillBackground(True)
    material = WorkspaceBodyMaterialSurface(
        backdrop_mode=ShellBackdropMode.MICA,
        parent=window,
    )
    material_layout = QHBoxLayout(material)
    material_layout.setContentsMargins(0, 0, 0, 0)
    material_layout.setSpacing(0)
    material_layout.addWidget(host)
    window.setCentralWidget(material)
    window.setWindowOpacity(0.0)
    return host, window


def qualify_transparent_bars(
    *,
    root: QWidget,
    page: VideoPlaybackPage,
    evidence_path: Path,
) -> dict[str, object]:
    """Prove uncovered Fit-mode pixels contain the host canvas wash."""

    capture(root, evidence_path)
    image = QImage(str(evidence_path))
    if image.isNull():
        raise RuntimeError("Transparent-bar evidence could not be loaded.")
    sample = page.render_surface.mapTo(
        root, QPoint(page.render_surface.width() // 2, 8)
    )
    ratio = root.devicePixelRatioF()
    pixel = image.pixelColor(round(sample.x() * ratio), round(sample.y() * ratio))
    expected = qualification_wash_color()
    if not _colors_match(pixel, expected):
        raise RuntimeError(
            "Video letterbox region did not expose the Output canvas wash: "
            f"observed={pixel.name(QColor.NameFormat.HexArgb)} "
            f"expected={expected.name(QColor.NameFormat.HexArgb)}"
        )
    return {
        "wash_rgba": [pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()],
        "sample_device_pixel": [
            round(sample.x() * ratio),
            round(sample.y() * ratio),
        ],
    }


def qualify_rehosting(
    *,
    application: QApplication,
    host: CanvasHost,
    canvas: OutputCanvas,
    docked_window: QWidget,
    page: VideoPlaybackPage,
    evidence_dir: Path,
) -> dict[str, object]:
    """Exercise playback and viewport controls while floating and redocked."""

    play = find_button(page, "Play or pause")
    next_frame = find_button(page, "Next frame")
    previous_frame = find_button(page, "Previous frame")
    loop = find_button(page, "Loop video")
    fit = find_button(page, "Fit video")
    actual_size = find_button(page, "Show video at actual size")
    seek = find_slider(page, "Video position")
    volume_evidence = qualify_volume_flyout(
        application=application,
        root=docked_window,
        page=page,
        evidence_dir=evidence_dir,
    )

    if page.controller.snapshot.loop_enabled:
        native_click(docked_window, loop, application)
    key_press(page.render_surface, Qt.Key.Key_Space, application)
    native_wheel(
        docked_window,
        page.render_surface,
        120,
        application,
        horizontal_fraction=0.7,
        vertical_fraction=0.3,
    )
    key_release(page.render_surface, Qt.Key.Key_Space, application)
    wait_until(
        application,
        lambda: (
            not page.controller.snapshot.loop_enabled
            and page.viewport_state.mode is VideoViewportMode.CUSTOM
        ),
        label="pre-undock state",
    )
    pre_undock_viewport = page.viewport_state

    host.detach_canvas("Output")
    wait_until(
        application,
        lambda: canvas.window() is not docked_window and canvas.window().isVisible(),
        label="floating Output canvas",
    )
    floating_window = canvas.window()
    wait_until(
        application,
        lambda: (
            page.controller.snapshot.state is VideoPlaybackState.READY
            and page.controller.snapshot.paused
            and not page.controller.snapshot.loop_enabled
            and page.controller.snapshot.user_muted
            and 38 <= page.controller.snapshot.volume <= 46
            and page.viewport_state == pre_undock_viewport
            and not canvas.tabbar.isVisible()
            and canvas.source_selector_button.isVisible()
        ),
        label="preserved floating video state",
    )
    floating_capture = evidence_dir / "video-detail-floating.png"
    capture(floating_window, floating_capture)
    _assert_video_frame_visible(floating_capture, floating_window, page)
    _exercise_transport(
        application=application,
        root=floating_window,
        page=page,
        play=play,
        next_frame=next_frame,
        previous_frame=previous_frame,
        seek=seek,
    )
    native_click(floating_window, actual_size, application)
    native_click(floating_window, loop, application)
    wait_until(
        application,
        lambda: (
            page.viewport_state.mode is VideoViewportMode.ACTUAL_SIZE
            and page.controller.snapshot.loop_enabled
        ),
        label="floating viewport and loop controls",
    )

    host.handle_canvas_dock_action("Output")
    wait_until(
        application,
        lambda: canvas.window() is docked_window and canvas.isVisible(),
        label="redocked Output canvas",
    )
    wait_until(
        application,
        lambda: (
            page.controller.snapshot.state is VideoPlaybackState.READY
            and page.controller.snapshot.paused
            and page.controller.snapshot.loop_enabled
            and page.controller.snapshot.user_muted
            and 38 <= page.controller.snapshot.volume <= 46
            and page.viewport_state.mode is VideoViewportMode.ACTUAL_SIZE
            and not canvas.tabbar.isVisible()
            and canvas.source_selector_button.isVisible()
        ),
        label="preserved redocked video state",
    )
    redocked_capture = evidence_dir / "video-detail-redocked.png"
    capture(docked_window, redocked_capture)
    _assert_video_frame_visible(redocked_capture, docked_window, page)
    _exercise_transport(
        application=application,
        root=docked_window,
        page=page,
        play=play,
        next_frame=next_frame,
        previous_frame=previous_frame,
        seek=seek,
    )
    native_click(docked_window, fit, application)
    wait_until(
        application,
        lambda: page.viewport_state.mode is VideoViewportMode.FIT,
        label="redocked Fit control",
    )
    return {
        "floating_playback_controls": True,
        "floating_viewport_controls": True,
        "redocked_playback_controls": True,
        "redocked_viewport_controls": True,
        "state_survived_detach": True,
        "state_survived_redock": True,
        "volume_flyout": volume_evidence,
    }


def _exercise_transport(
    *,
    application: QApplication,
    root: QWidget,
    page: VideoPlaybackPage,
    play: QWidget,
    next_frame: QWidget,
    previous_frame: QWidget,
    seek: QWidget,
) -> None:
    """Prove seek, frame stepping, play, and pause in one host window."""

    native_click_fraction(root, seek, 0.38, application)
    wait_until(
        application,
        lambda: float(page.controller.snapshot.time_seconds or 0.0) >= 0.25,
        label="rehosted seek",
    )
    initial = float(page.controller.snapshot.time_seconds or 0.0)
    native_click(root, next_frame, application)
    wait_until(
        application,
        lambda: float(page.controller.snapshot.time_seconds or 0.0) > initial,
        label="rehosted next frame",
    )
    advanced = float(page.controller.snapshot.time_seconds or 0.0)
    native_click(root, previous_frame, application)
    wait_until(
        application,
        lambda: float(page.controller.snapshot.time_seconds or 0.0) < advanced,
        label="rehosted previous frame",
    )
    native_click(root, play, application)
    wait_until(
        application,
        lambda: page.controller.snapshot.state is VideoPlaybackState.PLAYING,
        label="rehosted play",
    )
    started = float(page.controller.snapshot.time_seconds or 0.0)
    wait_until(
        application,
        lambda: float(page.controller.snapshot.time_seconds or 0.0) > started + 0.04,
        label="rehosted playback clock",
    )
    native_click(root, play, application)
    wait_until(
        application,
        lambda: page.controller.snapshot.paused,
        label="rehosted pause",
    )
    pump_events(application, 0.05)


def qualification_wash_color() -> QColor:
    """Return the production material wash composited over the known backdrop."""

    foreground = QColor(*body_material_wash_color(ShellBackdropMode.MICA))
    alpha = foreground.alphaF()
    return QColor(
        round(foreground.red() * alpha + _BACKDROP.red() * (1.0 - alpha)),
        round(foreground.green() * alpha + _BACKDROP.green() * (1.0 - alpha)),
        round(foreground.blue() * alpha + _BACKDROP.blue() * (1.0 - alpha)),
    )


def _assert_video_frame_visible(
    capture_path: Path,
    root: QWidget,
    page: VideoPlaybackPage,
) -> None:
    """Reject a rehosted surface that only paints black or the canvas wash."""

    image = QImage(str(capture_path))
    if image.isNull():
        raise RuntimeError("Rehosted video evidence could not be loaded.")
    center = page.render_surface.mapTo(root, page.render_surface.rect().center())
    ratio = root.devicePixelRatioF()
    pixel = image.pixelColor(round(center.x() * ratio), round(center.y() * ratio))
    if pixel.lightness() <= 4 or _colors_match(pixel, qualification_wash_color()):
        raise RuntimeError(
            "Rehosted video surface did not contain a decoded frame: "
            f"observed={pixel.name(QColor.NameFormat.HexArgb)}"
        )


def _colors_match(actual: QColor, expected: QColor) -> bool:
    """Return whether capture conversion preserved the requested wash color."""

    return all(
        abs(left - right) <= 2
        for left, right in zip(
            (actual.red(), actual.green(), actual.blue()),
            (expected.red(), expected.green(), expected.blue()),
            strict=True,
        )
    )


__all__ = [
    "create_qualification_host",
    "qualification_wash_color",
    "qualify_rehosting",
    "qualify_transparent_bars",
]
