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

"""Render and drive the production mixed-media Output canvas with real libmpv."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Callable
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget
from PIL import ImageGrab
from substitute.application.ports.video import VideoPlaybackState
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_probe import MpvVideoProbe
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_video_badge_overlays import (
    OUTPUT_VIDEO_BADGE_OVERLAY_NAME,
)


_TIMEOUT_SECONDS = 10.0


def main(argv: list[str] | None = None) -> int:
    """Render mixed grid and player states and record behavioral evidence."""

    arguments = _parse_arguments(argv)
    video_path = arguments.video.expanduser().resolve()
    evidence_dir = arguments.evidence_dir.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    existing_application = QApplication.instance()
    application = (
        existing_application
        if isinstance(existing_application, QApplication)
        else QApplication([])
    )
    runtime = MpvRuntime.bundled()
    poster_result = MpvVideoProbe(runtime).probe(video_path)
    poster = QImage.fromData(poster_result.poster_bytes, b"PNG")
    if poster.isNull():
        raise RuntimeError("Production probe returned an invalid poster.")

    image_id = uuid4()
    video_id = uuid4()
    image_path = evidence_dir / "qualification-image.png"
    image = _qualification_image(QSize(640, 360))
    if not image.save(str(image_path)):
        raise RuntimeError("Could not write qualification image.")
    metadata = {
        image_id: _metadata(image_path, OutputMediaKind.IMAGE),
        video_id: _metadata(
            video_path,
            OutputMediaKind.VIDEO,
            duration_seconds=poster_result.duration_seconds,
        ),
    }
    execution_runtime = ExecutionRuntime()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime.canvas_execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    window = QMainWindow()
    window.setWindowTitle("SugarSubstitute video output qualification")
    window.setCentralWidget(canvas)
    try:
        canvas.set_final_output_lookup(
            payload_lookup=lambda media_id: {
                image_id: image,
                video_id: poster,
            }.get(media_id),
            metadata_lookup=metadata.get,
        )
        if not canvas.document.admit_image(image_id, image, path=image_path):
            raise RuntimeError("Qualification image was not admitted.")
        if not canvas.document.admit_image(video_id, poster, path=video_path):
            raise RuntimeError("Qualification video poster was not admitted.")
        window.resize(1100, 720)
        primary_screen = application.primaryScreen()
        if primary_screen is None:
            raise RuntimeError("Qualification process has no primary screen.")
        available = primary_screen.availableGeometry()
        window.move(available.left() + 40, available.top() + 40)
        window.show()
        _pump_events(application, 0.3)
        print(
            "Rendered geometry:",
            f"window={window.width()}x{window.height()}",
            f"position={window.x()},{window.y()}",
            f"canvas={canvas.width()}x{canvas.height()}",
            f"stack={canvas.video_presentation.widget.width()}x{canvas.video_presentation.widget.height()}",
            flush=True,
        )

        if not canvas.document.present_grid((image_id, video_id)):
            raise RuntimeError("Mixed-media grid presentation failed.")
        _pump_events(application, 0.4)
        video_composition = canvas.document.composition_id_for(video_id)
        video_tile = (
            canvas.workspace.canvasFor(video_composition)
            if video_composition is not None
            else None
        )
        if (
            video_tile is None
            or OUTPUT_VIDEO_BADGE_OVERLAY_NAME not in video_tile.contentOverlays()
        ):
            raise RuntimeError("Video tile did not expose its play badge.")
        _capture(window, evidence_dir / "mixed-image-video-grid.png")

        if not canvas.document.present_single(video_id):
            raise RuntimeError("Video detail presentation failed.")
        page = canvas.video_presentation.video_page
        _wait_until(
            application,
            lambda: (
                page.controller.snapshot.state is VideoPlaybackState.READY
                and page.controller.snapshot.diagnostics.codec is not None
                and page.controller.snapshot.diagnostics.pixel_format is not None
                and page.controller.snapshot.diagnostics.actual_video_output is not None
            ),
            label="ready video detail",
        )
        ready = page.controller.snapshot
        _capture(window, evidence_dir / "video-detail-paused.png")

        next_button = _button(page, "Next frame")
        previous_button = _button(page, "Previous frame")
        loop_button = _button(page, "Loop video")
        play_button = _button(page, "Play or pause")
        page.controller.seek(0.5)
        _wait_until(
            application,
            lambda: float(page.controller.snapshot.time_seconds or 0.0) >= 0.45,
            label="UI qualification seek",
        )
        initial_time = float(page.controller.snapshot.time_seconds or 0.0)
        next_button.click()
        _wait_until(
            application,
            lambda: (
                float(page.controller.snapshot.time_seconds or 0.0)
                > initial_time + 0.001
            ),
            label="UI next-frame command",
        )
        next_time = float(page.controller.snapshot.time_seconds or 0.0)
        previous_button.click()
        _wait_until(
            application,
            lambda: (
                page.controller.snapshot.time_seconds is not None
                and float(page.controller.snapshot.time_seconds) < next_time - 0.001
            ),
            label="UI previous-frame command",
        )
        previous_time = float(page.controller.snapshot.time_seconds or 0.0)
        loop_button.click()
        _wait_until(
            application,
            lambda: not page.controller.snapshot.loop_enabled,
            label="UI loop-off command",
        )
        play_button.click()
        _wait_until(
            application,
            lambda: page.controller.snapshot.state is VideoPlaybackState.PLAYING,
            label="UI play command",
        )
        _pump_events(application, 0.25)
        _capture(window, evidence_dir / "video-detail-playing.png")

        if not canvas.document.present_single(image_id):
            raise RuntimeError("Image detail presentation failed.")
        _wait_until(
            application,
            lambda: (
                page.controller.snapshot.paused
                and page.controller.snapshot.effectively_muted
            ),
            label="hidden-video safety",
        )
        _capture(window, evidence_dir / "image-after-video.png")
        evidence = {
            "schema_version": "1",
            "mixed_grid_badge": True,
            "next_frame": next_time,
            "previous_frame": previous_time,
            "loop_disabled": not page.controller.snapshot.loop_enabled,
            "hidden_paused": page.controller.snapshot.paused,
            "hidden_muted": page.controller.snapshot.effectively_muted,
            "diagnostics": {
                "codec": ready.diagnostics.codec,
                "pixel_format": ready.diagnostics.pixel_format,
                "renderer": ready.diagnostics.actual_video_output,
            },
        }
        evidence_path = evidence_dir / "video-output-ui.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(evidence_path)
        return 0
    finally:
        canvas.video_presentation.video_page.close_player()
        window.close()
        window.deleteLater()
        application.processEvents()
        execution_runtime.shutdown()


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse the local video and evidence destinations."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    return parser.parse_args(argv)


def _qualification_image(size: QSize) -> QImage:
    """Create one project-owned image fixture with visible spatial detail."""

    image = QImage(size, QImage.Format.Format_RGB32)
    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, QColor("#e85d75"))
    gradient.setColorAt(0.5, QColor("#7a5cff"))
    gradient.setColorAt(1.0, QColor("#38bdf8"))
    painter = QPainter(image)
    painter.fillRect(image.rect(), gradient)
    painter.setPen(QColor("white"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "IMAGE")
    painter.end()
    return image


def _metadata(
    path: Path,
    kind: OutputMediaKind,
    *,
    duration_seconds: float | None = None,
) -> ImageMeta:
    """Create one complete final-media record for the production canvas."""

    return ImageMeta(
        workflow_name="Video qualification",
        cube_name="Mixed output",
        image_number=1,
        suffix="",
        path=path.as_posix(),
        source_key="qualification",
        source_label="Mixed output",
        media_kind=kind,
        duration_seconds=duration_seconds,
        mime_type="video/mp4" if kind is OutputMediaKind.VIDEO else "image/png",
    )


def _button(parent: QWidget, accessible_name: str) -> QPushButton:
    """Find one public accessibility-labeled playback control."""

    for button in parent.findChildren(QPushButton):
        if button.accessibleName() == accessible_name:
            return button
    raise RuntimeError(f"Playback control is unavailable: {accessible_name}")


def _capture(widget: QWidget, path: Path) -> None:
    """Capture the complete top-level canvas including native child surfaces."""

    if sys.platform == "win32":
        bounds = wintypes.RECT()
        window_handle = int(widget.winId())
        user32 = ctypes.windll.user32
        if not user32.GetWindowRect(
            window_handle,
            ctypes.byref(bounds),
        ):
            raise RuntimeError("Could not resolve rendered window bounds.")
        physical_screen_width = int(user32.GetSystemMetrics(0))
        logical_screen_width = widget.screen().geometry().width()
        coordinate_scale = (
            logical_screen_width / physical_screen_width
            if physical_screen_width > 0
            else 1.0
        )
        capture_bounds = (
            round(bounds.left * coordinate_scale),
            round(bounds.top * coordinate_scale),
            round(bounds.right * coordinate_scale),
            round(bounds.bottom * coordinate_scale),
        )
        capture = ImageGrab.grab(
            bbox=capture_bounds,
            all_screens=True,
        )
        capture.save(path, format="PNG")
        return
    screen = widget.screen()
    if screen is None:
        raise RuntimeError("Output canvas has no active screen.")
    pixmap = screen.grabWindow(int(widget.winId()))
    if pixmap.isNull() or not pixmap.save(str(path)):
        raise RuntimeError(f"Could not capture rendered output: {path.name}")


def _wait_until(
    application: QApplication,
    predicate: Callable[[], bool],
    *,
    label: str,
) -> None:
    """Wait for one Qt/native state transition with a bounded timeout."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError(f"Timed out waiting for {label}.")


def _pump_events(application: QApplication, seconds: float) -> None:
    """Keep the Qt/native event queues moving for one bounded render interval."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)


if __name__ == "__main__":
    raise SystemExit(main())
