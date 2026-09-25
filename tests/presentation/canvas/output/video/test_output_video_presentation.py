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

"""Prove mixed media stays in CuteCanvas and video detail uses the player."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import QWidget
from cutecanvas import ExecutionRuntime

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_video_badge_overlays import (
    OUTPUT_VIDEO_BADGE_OVERLAY_NAME,
)
from tests.presentation.canvas.output.document.support import _app, _sized_image
from tests.support.qt.lifecycle import destroy_qt_object


class _Player:
    """Record the player commands exercised by Output presentation switching."""

    player_generation = 1

    def __init__(self, callback: Callable[[VideoPlaybackEvent], None]) -> None:
        """Store callback and empty command state."""

        self.callback = callback
        self.media_generation = 0
        self.media_id: UUID | None = None
        self.commands: list[tuple[object, ...]] = []

    def load(self, media_id: UUID, path: Path) -> None:
        """Record one local artifact load."""

        self.media_generation += 1
        self.media_id = media_id
        self.commands.append(("load", media_id, path))

    def unload(self) -> None:
        """Record unload."""

        self.commands.append(("unload",))

    def set_playing(self, playing: bool) -> None:
        """Record playback state."""

        self.commands.append(("playing", playing))

    def seek(self, seconds: float) -> None:
        """Record seek."""

        self.commands.append(("seek", seconds))

    def step_next_frame(self) -> None:
        """Record next-frame."""

        self.commands.append(("next",))

    def step_previous_frame(self) -> None:
        """Record previous-frame."""

        self.commands.append(("previous",))

    def set_loop_enabled(self, enabled: bool) -> None:
        """Record loop policy."""

        self.commands.append(("loop", enabled))

    def set_volume(self, volume: int) -> None:
        """Record volume."""

        self.commands.append(("volume", volume))

    def set_user_muted(self, muted: bool) -> None:
        """Record user mute."""

        self.commands.append(("mute", muted))

    def set_viewport(self, zoom: float, pan_x: float, pan_y: float) -> None:
        """Record viewport geometry."""

        self.commands.append(("viewport", zoom, pan_x, pan_y))

    def set_output_active(self, active: bool) -> None:
        """Record output visibility."""

        self.commands.append(("active", active))

    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return the ready state used by controls."""

        return VideoPlaybackSnapshot(
            media_id=self.media_id,
            state=(
                VideoPlaybackState.EMPTY
                if self.media_id is None
                else VideoPlaybackState.READY
            ),
            paused=True,
            loop_enabled=True,
            user_muted=False,
            effectively_muted=False,
            volume=100,
            time_seconds=0.0,
            duration_seconds=2.0,
            width=320,
            height=180,
        )

    def close(self) -> None:
        """Record teardown."""

        self.commands.append(("close",))


def test_mixed_grid_uses_video_badge_and_single_video_uses_player(
    execution_runtime: ExecutionRuntime,
    tmp_path: Path,
) -> None:
    """CuteCanvas owns mixed grids while only video detail swaps to playback."""

    app = _app()
    player_box: list[_Player] = []

    def create_player(callback: Callable[[VideoPlaybackEvent], None]) -> _Player:
        player = _Player(callback)
        player_box.append(player)
        return player

    image_id = uuid4()
    video_id = uuid4()
    video_path = tmp_path / "clip.webm"
    video_path.write_bytes(b"fixture")
    metadata = {
        image_id: _metadata(tmp_path / "image.png", OutputMediaKind.IMAGE),
        video_id: _metadata(video_path, OutputMediaKind.VIDEO),
    }
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
        video_player_factory=create_player,
    )
    try:
        canvas.set_final_output_lookup(
            payload_lookup=lambda media_id: {
                image_id: _sized_image("red", QSize(320, 180)),
                video_id: _sized_image("blue", QSize(320, 180)),
            }.get(media_id),
            metadata_lookup=metadata.get,
        )
        assert canvas.document.admit_image(
            image_id, _sized_image("red", QSize(320, 180))
        )
        assert canvas.document.admit_image(
            video_id, _sized_image("blue", QSize(320, 180)), path=video_path
        )
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.present_grid((image_id, video_id))
        app.processEvents()

        video_composition = canvas.document.composition_id_for(video_id)
        assert video_composition is not None
        video_tile = canvas.workspace.canvasFor(video_composition)
        assert video_tile is not None
        badges = video_tile.findChildren(QWidget, OUTPUT_VIDEO_BADGE_OVERLAY_NAME)
        assert len(badges) == 1
        assert canvas.video_presentation.widget.currentWidget() is canvas.workspace
        assert player_box == []

        without_hover = video_tile.grab().toImage()
        app.sendEvent(video_tile, QEvent(QEvent.Type.Enter))
        app.processEvents()
        with_hover = video_tile.grab().toImage()
        assert with_hover != without_hover
        app.sendEvent(video_tile, QEvent(QEvent.Type.Leave))
        app.processEvents()
        assert video_tile.grab().toImage() == without_hover

        assert canvas.document.present_single(video_id)
        app.processEvents()
        assert (
            canvas.video_presentation.widget.currentWidget()
            is canvas.video_presentation.video_page
        )
        assert player_box[0].commands[:6] == [
            ("load", video_id, video_path.resolve()),
            ("volume", 100),
            ("mute", False),
            ("loop", True),
            ("viewport", 1.0, 0.0, 0.0),
            ("active", True),
        ]
        canvas.video_presentation.video_page.controller.step_previous_frame()
        canvas.video_presentation.video_page.controller.step_next_frame()
        assert player_box[0].commands[-2:] == [("previous",), ("next",)]

        assert canvas.video_presentation.retire_media(video_id)
        assert player_box[0].commands[-1] == ("unload",)
        assert canvas.video_presentation.widget.currentWidget() is canvas.workspace

        assert canvas.document.present_single(image_id)
        app.processEvents()
        assert canvas.video_presentation.widget.currentWidget() is canvas.workspace
        assert ("active", False) in player_box[0].commands
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def _metadata(path: Path, kind: OutputMediaKind) -> ImageMeta:
    """Build a complete media record for presentation switching."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Cube",
        image_number=1,
        suffix="",
        path=path.as_posix(),
        source_key="source",
        source_label="Source",
        media_kind=kind,
        duration_seconds=2.0 if kind is OutputMediaKind.VIDEO else None,
        mime_type="video/webm" if kind is OutputMediaKind.VIDEO else "image/png",
    )
