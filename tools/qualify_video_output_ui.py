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

from pathlib import Path
import sys
from uuid import UUID, uuid4

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]
from substitute.application.ports.video import VideoPlaybackState
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_canvas_projection_model import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.domain.output_media import OutputMediaKind
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_probe import MpvVideoProbe
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_video_badge_overlays import (
    OUTPUT_VIDEO_BADGE_OVERLAY_NAME,
)
from tools.video_output_qualification_support import (
    capture,
    capture_with_popup,
    find_button,
    find_slider,
    images_differ,
    native_click,
    native_click_fraction,
    native_target_is_root,
    open_source_picker,
    pointer_move,
    pump_events,
    render_capture,
    wait_until,
)
from tools.video_output_qualification_fixture import (
    qualification_image,
    qualification_metadata,
)
from tools.video_output_qualification_cli import parse_arguments
from tools.video_output_qualification_evidence import write_video_output_evidence
from tools.video_output_qualification_rehosting import (
    create_qualification_host,
    qualify_rehosting,
    qualify_canvas_margins,
)
from tools.video_output_qualification_sampling import qualify_video_sampling
from tools.video_output_qualification_navigation import qualify_space_pan_zoom


_TIMEOUT_SECONDS = 10.0


def main(argv: list[str] | None = None) -> int:
    """Render mixed grid and player states and record behavioral evidence."""

    arguments = parse_arguments(argv)
    video_path = arguments.video.expanduser().resolve()
    evidence_dir = arguments.evidence_dir.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    existing_application = QApplication.instance()
    application = (
        existing_application
        if isinstance(existing_application, QApplication)
        else QApplication([])
    )
    setTheme(Theme.DARK if arguments.theme == "dark" else Theme.LIGHT)
    runtime = MpvRuntime.bundled()
    poster_result = MpvVideoProbe(runtime).probe(video_path)
    poster = QImage.fromData(poster_result.poster_bytes)
    if poster.isNull():
        raise RuntimeError("Production probe returned an invalid poster.")

    image_id = uuid4()
    video_id = uuid4()
    image_path = evidence_dir / "qualification-image.png"
    image = qualification_image(QSize(640, 360))
    if not image.save(str(image_path)):
        raise RuntimeError("Could not write qualification image.")
    metadata = {
        image_id: qualification_metadata(image_path, OutputMediaKind.IMAGE),
        video_id: qualification_metadata(
            video_path,
            OutputMediaKind.VIDEO,
            duration_seconds=poster_result.duration_seconds,
        ),
    }
    execution_runtime = ExecutionRuntime()
    route_boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime.canvas_execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=route_boundary,
    )
    host, window = create_qualification_host(canvas)
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
        sources = (
            OutputCanvasSourceGroup(
                source_key="image-output",
                label="Image Output",
                images_by_set={
                    1: OutputCanvasImageItem(image_id, metadata[image_id], 1)
                },
            ),
            OutputCanvasSourceGroup(
                source_key="video-output",
                label="Video Output",
                images_by_set={
                    1: OutputCanvasImageItem(video_id, metadata[video_id], 1)
                },
            ),
        )

        def bind_selection(media_id: UUID) -> None:
            """Bind one real source projection through the application boundary."""

            source_key = "image-output" if media_id == image_id else "video-output"
            projection = OutputCanvasProjection(
                sources=sources,
                active_source_key=source_key,
                active_set_index=1,
                active_uuid=media_id,
                set_count=1,
            )
            canvas.bind_projection_session(
                bind_output_canvas_session(
                    route_boundary,
                    workflow_id="video-output-qualification",
                    projection=projection,
                    image_metadata_lookup=metadata,
                )
            )

        def follow_source_selection(raw_media_id: str) -> None:
            """Apply user source-tab selection like the owning shell coordinator."""

            bind_selection(UUID(raw_media_id))

        canvas.activeOutputChanged.connect(follow_source_selection)
        window.resize(1100, 720)
        primary_screen = application.primaryScreen()
        if primary_screen is None:
            raise RuntimeError("Qualification process has no primary screen.")
        available = primary_screen.availableGeometry()
        window.move(available.left() + 40, available.top() + 40)
        window.show()
        host.activate_canvas("Output", keyboard_focus=False)
        pump_events(application, 0.3)
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
        pump_events(application, 0.4)
        video_composition = canvas.document.composition_id_for(video_id)
        video_tile = (
            canvas.workspace.canvasFor(video_composition)
            if video_composition is not None
            else None
        )
        if (
            video_tile is None
            or video_tile.findChild(QWidget, OUTPUT_VIDEO_BADGE_OVERLAY_NAME) is None
        ):
            raise RuntimeError("Video tile did not expose its play badge.")
        badge = video_tile.findChild(QWidget, OUTPUT_VIDEO_BADGE_OVERLAY_NAME)
        assert badge is not None
        capture(window, evidence_dir / "mixed-image-video-grid.png")
        render_capture(video_tile, evidence_dir / "video-tile-rest.png")
        pointer_move(window, video_tile, application)
        if badge.isHidden():
            raise RuntimeError("Video tile hover did not reveal its play affordance.")
        capture(window, evidence_dir / "mixed-image-video-grid-hover.png")
        render_capture(video_tile, evidence_dir / "video-tile-hover.png")
        pointer_move(window, canvas.tabbar_container, application)
        if not images_differ(
            evidence_dir / "video-tile-rest.png",
            evidence_dir / "video-tile-hover.png",
        ):
            raise RuntimeError("Video tile hover did not change rendered output.")

        bind_selection(video_id)
        page = canvas.video_presentation.video_page
        try:
            wait_until(
                application,
                lambda: (
                    page.controller.snapshot.state is VideoPlaybackState.READY
                    and page.controller.snapshot.diagnostics.codec is not None
                    and page.controller.snapshot.diagnostics.pixel_format is not None
                    and page.controller.snapshot.diagnostics.actual_video_output
                    is not None
                ),
                label="ready video detail",
            )
        except TimeoutError as error:
            raise RuntimeError(
                f"{error} Last snapshot: {page.controller.snapshot!r}"
            ) from error
        ready = page.controller.snapshot
        if not ready.loop_enabled:
            raise RuntimeError("Video did not default to automatic looping.")
        capture(window, evidence_dir / "video-detail-paused.png")
        canvas_margin_evidence = qualify_canvas_margins(
            application=application,
            root=window,
            page=page,
            evidence_path=evidence_dir / "video-detail-canvas-margin.png",
        )

        if tuple(canvas.tabbar.items) != ("image-output", "video-output"):
            raise RuntimeError("Output source navigation omitted a projected source.")
        if canvas.tabbar.isVisible() or not canvas.source_selector_button.isVisible():
            raise RuntimeError("Video detail did not force compact source navigation.")
        picker, picker_view = open_source_picker(canvas, window, application)
        if picker_view.item_keys() != ("image-output", "video-output"):
            raise RuntimeError("Compact source picker omitted a projected source.")
        capture_with_popup(
            window,
            picker,
            evidence_dir / "video-detail-source-picker-open.png",
        )
        image_row = picker_view.row_for_key("image-output")
        if image_row is None:
            raise RuntimeError("Compact source picker omitted the image row.")
        native_click(picker, image_row, application)
        wait_until(
            application,
            lambda: (
                canvas.video_presentation.widget.currentWidget() is canvas.workspace
            ),
            label="image compact source selection",
        )
        capture(window, evidence_dir / "image-selected-by-source-picker.png")
        video_tab = canvas.tabbar.items["video-output"]
        native_click(window, video_tab, application)
        wait_until(
            application,
            lambda: canvas.video_presentation.widget.currentWidget() is page,
            label="video source tab selection",
        )

        sampling_evidence = qualify_video_sampling(
            application=application,
            root=window,
            page=page,
            evidence_dir=evidence_dir,
        )
        navigation_evidence = qualify_space_pan_zoom(
            application=application,
            root=window,
            page=page,
            evidence_dir=evidence_dir,
        )
        window.resize(760, 540)
        pump_events(application, 0.25)
        capture(window, evidence_dir / "video-detail-resized.png")
        controls_geometry = page.control_bar.geometry()
        navigation_geometry = canvas.tabbar_container.geometry()
        same_navigation_row = (
            controls_geometry.top() == navigation_geometry.top()
            and controls_geometry.height() == navigation_geometry.height()
            and controls_geometry.left() > navigation_geometry.right()
        )
        if not same_navigation_row:
            raise RuntimeError(
                "Playback controls did not share the Output navigation row."
            )
        window.resize(1100, 720)
        pump_events(application, 0.25)

        native_stacking = {
            "surface": native_target_is_root(window, page.render_surface),
            "play": native_target_is_root(window, find_button(page, "Play or pause")),
            "source_selector": native_target_is_root(
                window, canvas.source_selector_button
            ),
        }
        if not all(native_stacking.values()):
            raise RuntimeError("A native child surface still occludes Output controls.")

        next_button = find_button(page, "Next frame")
        previous_button = find_button(page, "Previous frame")
        loop_button = find_button(page, "Loop video")
        play_button = find_button(page, "Play or pause")
        native_click_fraction(
            window, find_slider(page, "Video position"), 0.5, application
        )
        wait_until(
            application,
            lambda: float(page.controller.snapshot.time_seconds or 0.0) >= 0.45,
            label="UI qualification seek",
        )
        initial_time = float(page.controller.snapshot.time_seconds or 0.0)
        native_click(window, next_button, application)
        wait_until(
            application,
            lambda: (
                float(page.controller.snapshot.time_seconds or 0.0)
                > initial_time + 0.001
            ),
            label="UI next-frame command",
        )
        next_time = float(page.controller.snapshot.time_seconds or 0.0)
        native_click(window, previous_button, application)
        wait_until(
            application,
            lambda: (
                page.controller.snapshot.time_seconds is not None
                and float(page.controller.snapshot.time_seconds) < next_time - 0.001
            ),
            label="UI previous-frame command",
        )
        previous_time = float(page.controller.snapshot.time_seconds or 0.0)
        native_click(window, loop_button, application)
        wait_until(
            application,
            lambda: not page.controller.snapshot.loop_enabled,
            label="UI loop-off command",
        )
        native_click(window, play_button, application)
        wait_until(
            application,
            lambda: page.controller.snapshot.state is VideoPlaybackState.PLAYING,
            label="UI play command",
        )
        playing_started_at = float(page.controller.snapshot.time_seconds or 0.0)
        wait_until(
            application,
            lambda: (
                float(page.controller.snapshot.time_seconds or 0.0)
                > playing_started_at + 0.08
            ),
            label="advancing video playback clock",
        )
        capture(window, evidence_dir / "video-detail-playing.png")
        wait_until(
            application,
            lambda: page.controller.snapshot.state is VideoPlaybackState.ENDED,
            label="loop-off video end",
        )
        loop_off_end_time = float(page.controller.snapshot.time_seconds or 0.0)
        native_click(window, play_button, application)
        wait_until(
            application,
            lambda: (
                page.controller.snapshot.state is VideoPlaybackState.PLAYING
                and float(page.controller.snapshot.time_seconds or 1.0) < 0.35
            ),
            label="restart after loop-off end",
        )
        native_click(window, loop_button, application)
        wait_until(
            application,
            lambda: page.controller.snapshot.loop_enabled,
            label="UI loop-on command",
        )
        native_click_fraction(
            window,
            find_slider(page, "Video position"),
            0.82,
            application,
        )
        wait_until(
            application,
            lambda: float(page.controller.snapshot.time_seconds or 0.0) >= 0.75,
            label="loop qualification near-end seek",
        )
        wait_until(
            application,
            lambda: (
                page.controller.snapshot.state is VideoPlaybackState.PLAYING
                and float(page.controller.snapshot.time_seconds or 1.0) < 0.35
            ),
            label="automatic loop restart",
        )
        loop_restart_time = float(page.controller.snapshot.time_seconds or 0.0)
        if arguments.soak_seconds > 0.0:
            pump_events(application, arguments.soak_seconds)
            if page.controller.snapshot.state is not VideoPlaybackState.PLAYING:
                raise RuntimeError("Video stopped during the native playback soak.")
        soak_end_time = float(page.controller.snapshot.time_seconds or 0.0)
        native_click(window, play_button, application)
        wait_until(
            application,
            lambda: page.controller.snapshot.paused,
            label="pause after loop qualification",
        )

        rehosting_evidence = qualify_rehosting(
            application=application,
            host=host,
            canvas=canvas,
            docked_window=window,
            page=page,
            evidence_dir=evidence_dir,
        )

        picker, picker_view = open_source_picker(canvas, window, application)
        image_row = picker_view.row_for_key("image-output")
        if image_row is None:
            raise RuntimeError("Compact source picker omitted the image row.")
        native_click(picker, image_row, application)
        wait_until(
            application,
            lambda: (
                page.controller.snapshot.paused
                and page.controller.snapshot.effectively_muted
            ),
            label="hidden-video safety",
        )
        capture(window, evidence_dir / "image-after-video.png")
        evidence_path = evidence_dir / "video-output-ui.json"
        write_video_output_evidence(
            path=evidence_path,
            theme=arguments.theme,
            soak_seconds=arguments.soak_seconds,
            page=page,
            canvas=canvas,
            ready=ready,
            next_time=next_time,
            previous_time=previous_time,
            loop_off_end_time=loop_off_end_time,
            loop_restart_time=loop_restart_time,
            soak_end_time=soak_end_time,
            actual_size_zoom=sampling_evidence.actual_size_zoom,
            actual_size_sampling=sampling_evidence.actual_size_sampling,
            fitted_sampling=sampling_evidence.fitted_sampling,
            wheel_viewport=navigation_evidence.wheel_viewport,
            dragged_viewport=navigation_evidence.dragged_viewport,
            same_navigation_row=same_navigation_row,
            native_stacking=native_stacking,
            canvas_margins=canvas_margin_evidence,
            rehosting=rehosting_evidence,
        )
        print(evidence_path)
        return 0
    finally:
        canvas.video_presentation.video_page.close_player()
        window.close()
        window.deleteLater()
        application.processEvents()
        execution_runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
