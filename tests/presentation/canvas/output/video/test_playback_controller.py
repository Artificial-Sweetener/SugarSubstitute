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
from uuid import UUID, uuid4

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
)
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoPlaybackController,
    VideoViewportState,
)
from tests.support.qt.lifecycle import ensure_qt_application


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

    def set_viewport(self, zoom: float, pan_x: float, pan_y: float) -> None:
        """Record normalized video viewport geometry."""

        self.commands.append(("viewport", zoom, pan_x, pan_y))

    def set_output_active(self, active: bool) -> None:
        """Record visibility policy."""

        self.commands.append(("active", active))

    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return current fake state."""

        return self.current

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
        ("viewport", 2.0, 0.25, -0.1),
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
