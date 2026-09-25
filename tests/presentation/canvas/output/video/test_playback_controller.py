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

"""Verify playback state retention and exact frame commands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import get_ident
from uuid import UUID, uuid4

from PySide6.QtTest import QSignalSpy

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPlayerPort,
    VideoPresentationSampling,
    VideoRuntimeUnavailableError,
)
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoPlaybackController,
    VideoViewportMode,
    VideoViewportState,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_signal


class _FakePlayer:
    """Record controller commands and publish generation-scoped observations."""

    player_generation = 7

    def __init__(self, callback: Callable[[VideoPlaybackEvent], None]) -> None:
        """Store callback and initialize empty player state."""

        self.callback = callback
        self.media_generation = 0
        self.media_id: UUID | None = None
        self.commands: list[tuple[object, ...]] = []
        self.current = _snapshot(None)
        self.pending_poll_snapshot: VideoPlaybackSnapshot | None = None
        self.poll_thread_ids: list[int] = []

    def load(self, media_id: UUID, path: Path) -> None:
        """Record one media replacement."""

        self.media_generation += 1
        self.media_id = media_id
        self.commands.append(("load", media_id, path))
        self.current = _snapshot(media_id)

    def unload(self) -> None:
        """Record unload."""

        self.commands.append(("unload",))

    def set_playing(self, playing: bool) -> None:
        """Record play state."""

        self.commands.append(("playing", playing))

    def seek(self, seconds: float) -> None:
        """Record seek target."""

        self.commands.append(("seek", seconds))

    def step_next_frame(self) -> None:
        """Record exact next-frame command."""

        self.commands.append(("next",))

    def step_previous_frame(self) -> None:
        """Record exact previous-frame command."""

        self.commands.append(("previous",))

    def set_loop_enabled(self, enabled: bool) -> None:
        """Record loop state."""

        self.commands.append(("loop", enabled))

    def set_volume(self, volume: int) -> None:
        """Record volume."""

        self.commands.append(("volume", volume))

    def set_user_muted(self, muted: bool) -> None:
        """Record user mute."""

        self.commands.append(("mute", muted))

    def set_viewport(
        self,
        zoom: float,
        pan_x: float,
        pan_y: float,
        sampling: VideoPresentationSampling,
    ) -> None:
        """Record normalized viewport geometry and source sampling."""

        self.commands.append(("viewport", zoom, pan_x, pan_y, sampling))

    def set_output_active(self, active: bool) -> None:
        """Record visibility policy."""

        self.commands.append(("active", active))

    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return current fake state."""

        return self.current

    def poll_playback_state(self) -> None:
        """Model one callback-free polling pass."""

        self.poll_thread_ids.append(get_ident())
        pending = self.pending_poll_snapshot
        if pending is None:
            return
        self.pending_poll_snapshot = None
        self.emit(pending)

    def close(self) -> None:
        """Record deterministic shutdown."""

        self.commands.append(("close",))

    def emit(self, snapshot: VideoPlaybackSnapshot) -> None:
        """Publish one native-thread-style event through the callback."""

        self.current = snapshot
        self.callback(
            VideoPlaybackEvent(
                player_generation=self.player_generation,
                media_generation=self.media_generation,
                snapshot=snapshot,
            )
        )


def test_controller_restores_loop_time_and_audio_without_auto_resume(
    tmp_path: Path,
) -> None:
    """Navigation should restore transient state and leave playback paused."""

    app = ensure_qt_application()
    players: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        players.append(player)
        return player

    controller = VideoPlaybackController(player_factory=create)
    first = uuid4()
    second = uuid4()
    first_path = tmp_path / "first.webm"
    second_path = tmp_path / "second.webm"
    first_path.write_bytes(b"video")
    second_path.write_bytes(b"video")

    controller.activate(first, first_path)
    controller.set_loop_enabled(False)
    controller.set_volume(37)
    controller.set_user_muted(True)
    controller.set_viewport(VideoViewportState(zoom=2.0, pan_x=0.25, pan_y=-0.1))
    players[0].emit(
        _snapshot(
            first,
            time_seconds=1.25,
            loop_enabled=False,
            volume=37,
            user_muted=True,
        )
    )
    app.processEvents()
    controller.activate(second, second_path)
    controller.activate(first, first_path)

    restored_commands = players[0].commands[-8:]
    assert restored_commands == [
        ("load", first, first_path.resolve()),
        ("volume", 37),
        ("mute", True),
        ("loop", False),
        (
            "viewport",
            2.0,
            0.25,
            -0.1,
            VideoPresentationSampling.BILINEAR,
        ),
        ("seek", 1.25),
        ("active", True),
        ("playing", False),
    ]
    assert controller.session_for(first).zoom == 2.0
    controller.close()


def test_controller_routes_frame_steps_and_hidden_policy(tmp_path: Path) -> None:
    """Frame commands remain explicit and hiding always pauses/mutes via the port."""

    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(uuid4(), path)
    controller.step_previous_frame()
    controller.step_next_frame()
    controller.deactivate()

    assert ("previous",) in player_box[0].commands
    assert ("next",) in player_box[0].commands
    assert player_box[0].commands[-1] == ("active", False)
    controller.close()


def test_controller_reconstructs_native_player_with_retained_session(
    tmp_path: Path,
) -> None:
    """Window transitions should rebuild native state without losing user choices."""

    app = ensure_qt_application()
    players: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        players.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)
    controller.set_loop_enabled(False)
    controller.set_volume(42)
    controller.set_user_muted(True)
    controller.set_viewport(
        VideoViewportState(
            zoom=1.75,
            pan_x=0.2,
            pan_y=-0.3,
            mode=VideoViewportMode.CUSTOM,
        )
    )
    players[0].emit(
        _snapshot(
            media_id,
            time_seconds=0.8,
            loop_enabled=False,
            volume=42,
            user_muted=True,
        )
    )
    app.processEvents()

    transition_snapshots = QSignalSpy(controller.snapshotChanged)
    controller.release_native_player_for_window_transition()

    assert controller.snapshot.state is VideoPlaybackState.LOADING
    assert controller.snapshot.media_id == media_id
    assert controller.snapshot.paused
    assert controller.snapshot.effectively_muted
    assert transition_snapshots.count() == 1

    controller.activate(media_id, path)

    assert len(players) == 2
    assert players[0].commands[-1] == ("close",)
    assert players[1].commands == [
        ("load", media_id, path.resolve()),
        ("volume", 42),
        ("mute", True),
        ("loop", False),
        (
            "viewport",
            1.75,
            0.2,
            -0.3,
            VideoPresentationSampling.BILINEAR,
        ),
        ("seek", 0.8),
        ("active", True),
        ("playing", False),
    ]
    assert controller.session_for(media_id).viewport_mode is VideoViewportMode.CUSTOM
    controller.close()


def test_controller_polls_native_state_on_the_qt_thread(tmp_path: Path) -> None:
    """Drive observations from the GUI timer without a native callback thread."""

    ensure_qt_application()
    players: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        players.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)
    changed = QSignalSpy(controller.snapshotChanged)
    players[0].pending_poll_snapshot = _snapshot(media_id, time_seconds=0.5)

    wait_for_qt_signal(changed, timeout_ms=1000)

    assert controller.snapshot.time_seconds == 0.5
    assert players[0].poll_thread_ids
    assert set(players[0].poll_thread_ids) == {get_ident()}
    controller.close()


def test_controller_computes_physical_one_to_one_scale_and_fit_state(
    tmp_path: Path,
) -> None:
    """1:1 must map source pixels to physical pixels and Fit must reset it."""

    app = ensure_qt_application()
    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)
    player_box[0].emit(_snapshot(media_id))
    app.processEvents()

    controller.set_actual_size_viewport(
        surface_width=1280,
        surface_height=720,
        device_pixel_ratio=1.0,
    )
    actual = controller.session_for(media_id)
    assert actual.viewport_mode is VideoViewportMode.ACTUAL_SIZE
    assert actual.zoom == 0.25
    assert player_box[0].commands[-1] == (
        "viewport",
        0.25,
        0.0,
        0.0,
        VideoPresentationSampling.BILINEAR,
    )

    controller.reset_viewport()
    fitted = controller.session_for(media_id)
    assert fitted.viewport_mode is VideoViewportMode.FIT
    assert fitted.zoom == 1.0
    assert player_box[0].commands[-1] == (
        "viewport",
        1.0,
        0.0,
        0.0,
        VideoPresentationSampling.BILINEAR,
    )
    controller.close()


def test_controller_anchors_one_to_one_at_the_double_click_position(
    tmp_path: Path,
) -> None:
    """1:1 should retain the source point under an off-center double-click."""

    app = ensure_qt_application()
    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)
    player_box[0].emit(_snapshot(media_id))
    app.processEvents()

    controller.set_actual_size_viewport(
        surface_width=160,
        surface_height=90,
        device_pixel_ratio=1.0,
        anchor_x=0.5,
        anchor_y=-0.5,
    )

    actual = controller.session_for(media_id)
    assert actual.viewport_mode is VideoViewportMode.ACTUAL_SIZE
    assert actual.zoom == 2.0
    assert actual.pan_x == -0.5
    assert actual.pan_y == 0.5
    assert (0.5 - actual.pan_x) / actual.zoom == 0.5
    assert (-0.5 - actual.pan_y) / actual.zoom == -0.5
    controller.close()


def test_controller_matches_qpane_sampling_at_two_physical_pixels_per_source(
    tmp_path: Path,
) -> None:
    """Switch to nearest exactly at QPane's DPI-aware two-times threshold."""

    app = ensure_qt_application()
    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)
    player_box[0].emit(_snapshot(media_id))
    app.processEvents()

    controller.set_surface_metrics(width=319, height=179, device_pixel_ratio=2.0)
    assert str(player_box[0].commands[-1][-1]) == "bilinear"

    controller.set_surface_metrics(width=320, height=180, device_pixel_ratio=2.0)
    assert str(player_box[0].commands[-1][-1]) == "nearest"
    controller.close()


def test_controller_unloads_active_media_before_retirement(tmp_path: Path) -> None:
    """Retirement should synchronously release the decoder's file handle."""

    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    media_id = uuid4()
    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=create)
    controller.activate(media_id, path)

    assert controller.retire(media_id)
    assert player_box[0].commands[-1] == ("unload",)
    assert controller.snapshot.media_id is None
    assert controller.snapshot.state is VideoPlaybackState.EMPTY
    assert controller.retire(media_id)
    assert player_box[0].commands.count(("unload",)) == 1
    controller.close()


def test_controller_reports_missing_bundled_runtime_without_local_path(
    tmp_path: Path,
) -> None:
    """Runtime startup failure should provide a stable actionable UI message."""

    def unavailable(_callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        raise VideoRuntimeUnavailableError("missing C:/private/libmpv-2.dll")

    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(player_factory=unavailable)

    controller.activate(uuid4(), path)

    assert controller.snapshot.state is VideoPlaybackState.ERROR
    assert controller.snapshot.error == "The bundled video runtime is unavailable."
    assert "private" not in (controller.snapshot.error or "")
    controller.close()


def test_controller_closes_player_when_render_surface_preparation_fails(
    tmp_path: Path,
) -> None:
    """A failed OpenGL bind must not retain a half-prepared native player."""

    player_box: list[_FakePlayer] = []

    def create(callback: Callable[[VideoPlaybackEvent], None]) -> _FakePlayer:
        player = _FakePlayer(callback)
        player_box.append(player)
        return player

    def fail_preparation(_player: VideoPlayerPort) -> None:
        raise RuntimeError("render context unavailable")

    path = tmp_path / "clip.webm"
    path.write_bytes(b"video")
    controller = VideoPlaybackController(
        player_factory=create,
        player_preparer=fail_preparation,
    )

    controller.activate(uuid4(), path)

    assert player_box[0].commands == [("close",)]
    assert controller.snapshot.state is VideoPlaybackState.ERROR
    controller.close()


def _snapshot(
    media_id: UUID | None,
    *,
    time_seconds: float | None = None,
    loop_enabled: bool = True,
    volume: int = 100,
    user_muted: bool = False,
) -> VideoPlaybackSnapshot:
    """Build one coherent fake playback snapshot."""

    return VideoPlaybackSnapshot(
        media_id=media_id,
        state=(
            VideoPlaybackState.EMPTY if media_id is None else VideoPlaybackState.READY
        ),
        paused=True,
        loop_enabled=loop_enabled,
        user_muted=user_muted,
        effectively_muted=user_muted,
        volume=volume,
        time_seconds=time_seconds,
        duration_seconds=2.0 if media_id is not None else None,
        width=320 if media_id is not None else None,
        height=180 if media_id is not None else None,
    )
