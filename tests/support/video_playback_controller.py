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

"""Provide deterministic playback-controller boundary observations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import get_ident
from uuid import UUID

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPresentationSampling,
)


class FakeVideoPlayer:
    """Record controller commands and publish generation-scoped observations."""

    player_generation = 7

    def __init__(self, callback: Callable[[VideoPlaybackEvent], None]) -> None:
        """Store callback and initialize empty player state."""

        self.callback = callback
        self.media_generation = 0
        self.media_id: UUID | None = None
        self.commands: list[tuple[object, ...]] = []
        self.current = playback_snapshot(None)
        self.pending_poll_snapshot: VideoPlaybackSnapshot | None = None
        self.poll_thread_ids: list[int] = []

    def load(self, media_id: UUID, path: Path) -> None:
        """Record one media replacement."""

        self.media_generation += 1
        self.media_id = media_id
        self.commands.append(("load", media_id, path))
        self.current = playback_snapshot(media_id)

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


def playback_snapshot(
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


__all__ = ["FakeVideoPlayer", "playback_snapshot"]
