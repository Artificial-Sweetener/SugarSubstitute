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

"""Own session playback state and Qt-thread delivery for generated videos."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, Qt, Signal, Slot
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPlayerPort,
    VideoRuntimeUnavailableError,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

_LOGGER = get_logger("presentation.canvas.output.video_playback_controller")


class VideoViewportMode(StrEnum):
    """Name the user-visible interpretation of video viewport scale."""

    FIT = "fit"
    ACTUAL_SIZE = "actual_size"
    CUSTOM = "custom"


@dataclass(slots=True)
class VideoMediaSession:
    """Retain transient user playback choices for one video identity."""

    time_seconds: float = 0.0
    loop_enabled: bool = True
    volume: int = 100
    user_muted: bool = False
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    viewport_mode: VideoViewportMode = VideoViewportMode.FIT


@dataclass(frozen=True, slots=True)
class VideoViewportState:
    """Describe one normalized video viewport transform."""

    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    mode: VideoViewportMode = VideoViewportMode.FIT


class VideoPlaybackController(QObject):
    """Coordinate one long-lived player without exposing native callbacks to Qt UI."""

    snapshotChanged = Signal(object)
    viewportChanged = Signal(object)
    _eventSubmitted = Signal(object)

    def __init__(
        self,
        *,
        player_factory: Callable[
            [Callable[[VideoPlaybackEvent], None]], VideoPlayerPort
        ],
        player_preparer: Callable[[VideoPlayerPort], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Store the lazy player factory and initialize empty playback state."""

        super().__init__(parent)
        self._player_factory = player_factory
        self._player_preparer = player_preparer
        self._player: VideoPlayerPort | None = None
        self._current_media_id: UUID | None = None
        self._current_path: Path | None = None
        self._sessions: dict[UUID, VideoMediaSession] = {}
        self._snapshot = VideoPlaybackSnapshot(
            media_id=None,
            state=VideoPlaybackState.EMPTY,
            paused=True,
            loop_enabled=True,
            user_muted=False,
            effectively_muted=True,
            volume=100,
            time_seconds=None,
            duration_seconds=None,
            width=None,
            height=None,
        )
        self._eventSubmitted.connect(
            self._receive_player_event,
            Qt.ConnectionType.QueuedConnection,
        )

    @property
    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return the latest GUI-thread playback snapshot."""

        return self._snapshot

    def activate(self, media_id: UUID, path: Path) -> None:
        """Load or reveal one video, restoring transient state while staying paused."""

        resolved = path.expanduser().resolve()
        try:
            player = self._ensure_player()
            if media_id != self._current_media_id or resolved != self._current_path:
                self._remember_current_session()
                self._current_media_id = media_id
                self._current_path = resolved
                player.load(media_id, resolved)
                session = self._sessions.setdefault(media_id, VideoMediaSession())
                player.set_volume(session.volume)
                player.set_user_muted(session.user_muted)
                player.set_loop_enabled(session.loop_enabled)
                player.set_viewport(session.zoom, session.pan_x, session.pan_y)
                if session.time_seconds > 0:
                    player.seek(session.time_seconds)
                self.viewportChanged.emit(_viewport_for_session(session))
            player.set_output_active(True)
            player.set_playing(False)
        except Exception as error:
            self._publish_error(error)

    def deactivate(self) -> None:
        """Pause and effectively mute the player while retaining its decoder."""

        self._remember_current_session()
        if self._player is None:
            return
        try:
            self._player.set_output_active(False)
        except Exception as error:
            self._publish_error(error)

    def set_playing(self, playing: bool) -> None:
        """Apply explicit play or pause intent to the active video."""

        self._apply(lambda player: player.set_playing(playing))

    def seek(self, seconds: float) -> None:
        """Seek the active video to an absolute presentation time."""

        self._apply(lambda player: player.seek(seconds))

    def step_next_frame(self) -> None:
        """Pause and advance one decoded frame."""

        self._apply(lambda player: player.step_next_frame())

    def step_previous_frame(self) -> None:
        """Pause and retreat one decoded frame."""

        self._apply(lambda player: player.step_previous_frame())

    def set_loop_enabled(self, enabled: bool) -> None:
        """Set and retain the current video's session loop preference."""

        if self._current_media_id is not None:
            self._sessions.setdefault(
                self._current_media_id, VideoMediaSession()
            ).loop_enabled = enabled
        self._apply(lambda player: player.set_loop_enabled(enabled))

    def set_volume(self, volume: int) -> None:
        """Set and retain the current video's session volume."""

        bounded = min(max(int(volume), 0), 100)
        if self._current_media_id is not None:
            self._sessions.setdefault(
                self._current_media_id, VideoMediaSession()
            ).volume = bounded
        self._apply(lambda player: player.set_volume(bounded))

    def set_user_muted(self, muted: bool) -> None:
        """Set and retain user mute independently from visibility muting."""

        if self._current_media_id is not None:
            self._sessions.setdefault(
                self._current_media_id, VideoMediaSession()
            ).user_muted = muted
        self._apply(lambda player: player.set_user_muted(muted))

    def set_viewport(self, state: VideoViewportState) -> None:
        """Set and retain the active video's normalized viewport transform."""

        media_id = self._current_media_id
        if media_id is None:
            return
        session = self._sessions.setdefault(media_id, VideoMediaSession())
        session.zoom = state.zoom
        session.pan_x = state.pan_x
        session.pan_y = state.pan_y
        session.viewport_mode = state.mode
        self._apply(
            lambda player: player.set_viewport(
                state.zoom,
                state.pan_x,
                state.pan_y,
            )
        )
        self.viewportChanged.emit(state)

    def reset_viewport(self) -> None:
        """Restore fit geometry for the active video."""

        self.set_viewport(VideoViewportState(mode=VideoViewportMode.FIT))

    def set_actual_size_viewport(
        self,
        *,
        surface_width: int,
        surface_height: int,
        device_pixel_ratio: float,
    ) -> None:
        """Show one source pixel as one physical display pixel when possible."""

        snapshot = self._snapshot
        source_width = snapshot.width
        source_height = snapshot.height
        if source_width is None or source_height is None:
            return
        physical_width = max(1.0, surface_width * device_pixel_ratio)
        physical_height = max(1.0, surface_height * device_pixel_ratio)
        fit_scale = min(
            physical_width / source_width,
            physical_height / source_height,
        )
        self.set_viewport(
            VideoViewportState(
                zoom=1.0 / max(fit_scale, 1.0 / 64.0),
                mode=VideoViewportMode.ACTUAL_SIZE,
            )
        )

    def retry(self) -> None:
        """Reload the current local artifact after a recoverable player failure."""

        media_id = self._current_media_id
        path = self._current_path
        if media_id is None or path is None:
            return
        self._current_media_id = None
        self.activate(media_id, path)

    def retire(self, media_id: UUID) -> bool:
        """Unload retired active media before its artifact lease is released."""

        self._sessions.pop(media_id, None)
        if media_id != self._current_media_id:
            return True
        player = self._player
        if player is not None:
            try:
                player.unload()
            except Exception as error:
                self._publish_error(error)
                return False
        self._current_media_id = None
        self._current_path = None
        self._snapshot = VideoPlaybackSnapshot(
            media_id=None,
            state=VideoPlaybackState.EMPTY,
            paused=True,
            loop_enabled=True,
            user_muted=False,
            effectively_muted=True,
            volume=100,
            time_seconds=None,
            duration_seconds=None,
            width=None,
            height=None,
        )
        self.snapshotChanged.emit(self._snapshot)
        return True

    def close(self) -> None:
        """Release native player resources and reject later observations."""

        self._remember_current_session()
        player = self._player
        self._player = None
        self._current_media_id = None
        self._current_path = None
        if player is not None:
            player.close()

    def session_for(self, media_id: UUID) -> VideoMediaSession:
        """Return a detached session snapshot for deterministic verification."""

        session = self._sessions.setdefault(media_id, VideoMediaSession())
        return VideoMediaSession(
            time_seconds=session.time_seconds,
            loop_enabled=session.loop_enabled,
            volume=session.volume,
            user_muted=session.user_muted,
            zoom=session.zoom,
            pan_x=session.pan_x,
            pan_y=session.pan_y,
            viewport_mode=session.viewport_mode,
        )

    def _ensure_player(self) -> VideoPlayerPort:
        """Create the one native player only when a video is first activated."""

        if self._player is None:
            player = self._player_factory(self._eventSubmitted.emit)
            try:
                if self._player_preparer is not None:
                    self._player_preparer(player)
            except Exception:
                player.close()
                raise
            self._player = player
        return self._player

    def _apply(self, command: Callable[[VideoPlayerPort], None]) -> None:
        """Apply one player command and surface recoverable failures."""

        if self._player is None:
            return
        try:
            command(self._player)
        except Exception as error:
            self._publish_error(error)

    @Slot(object)
    def _receive_player_event(self, value: object) -> None:
        """Accept only observations belonging to the current player and media."""

        if not isinstance(value, VideoPlaybackEvent) or self._player is None:
            return
        if (
            value.player_generation != self._player.player_generation
            or value.media_generation != self._player.media_generation
            or value.snapshot.media_id != self._current_media_id
        ):
            return
        self._snapshot = value.snapshot
        self._remember_current_session()
        self.snapshotChanged.emit(value.snapshot)

    def _remember_current_session(self) -> None:
        """Capture the latest stable playback choices for the current media."""

        media_id = self._current_media_id
        if media_id is None:
            return
        snapshot = self._snapshot
        session = self._sessions.setdefault(media_id, VideoMediaSession())
        if snapshot.media_id == media_id:
            if snapshot.time_seconds is not None:
                session.time_seconds = snapshot.time_seconds
            session.loop_enabled = snapshot.loop_enabled
            session.volume = snapshot.volume
            session.user_muted = snapshot.user_muted

    def _publish_error(self, error: Exception) -> None:
        """Expose a sanitized player failure without leaking local paths."""

        message = (
            render_application_text(
                app_text("The bundled video runtime is unavailable.")
            )
            if isinstance(error, VideoRuntimeUnavailableError)
            else render_application_text(
                app_text("Video playback is unavailable (%1).", type(error).__name__)
            )
        )
        self._snapshot = VideoPlaybackSnapshot(
            media_id=self._current_media_id,
            state=VideoPlaybackState.ERROR,
            paused=True,
            loop_enabled=self._snapshot.loop_enabled,
            user_muted=self._snapshot.user_muted,
            effectively_muted=True,
            volume=self._snapshot.volume,
            time_seconds=self._snapshot.time_seconds,
            duration_seconds=self._snapshot.duration_seconds,
            width=self._snapshot.width,
            height=self._snapshot.height,
            error=message,
            diagnostics=self._snapshot.diagnostics,
        )
        log_warning_exception(
            _LOGGER,
            "Video playback command failed",
            error=error,
            media_id=str(self._current_media_id or ""),
        )
        self.snapshotChanged.emit(self._snapshot)


def _viewport_for_session(session: VideoMediaSession) -> VideoViewportState:
    """Project mutable session geometry as an immutable viewport state."""

    return VideoViewportState(
        zoom=session.zoom,
        pan_x=session.pan_x,
        pan_y=session.pan_y,
        mode=session.viewport_mode,
    )


__all__ = [
    "VideoMediaSession",
    "VideoPlaybackController",
    "VideoViewportMode",
    "VideoViewportState",
]
