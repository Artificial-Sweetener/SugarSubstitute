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

"""Implement the application video-player port with one long-lived libmpv."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Protocol, cast
from uuid import UUID

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
)
from substitute.infrastructure.video.mpv_options import local_video_options
from substitute.infrastructure.video.mpv_runtime import MpvRuntime


_ObservedCallback = Callable[[str, object], None]


class VideoPlayerError(RuntimeError):
    """Report a safe actionable playback failure."""


class _MpvPlayer(Protocol):
    """Describe the python-mpv surface used by the playback adapter."""

    pause: object
    loop_file: object
    mute: object
    volume: object
    path: object

    def command(self, name: str, *arguments: object) -> object:
        """Execute one libmpv client command."""

    def observe_property(self, name: str, callback: _ObservedCallback) -> None:
        """Observe one player property on the native event thread."""

    def unobserve_property(self, name: str, callback: _ObservedCallback) -> None:
        """Remove one registered property observation."""

    def terminate(self) -> None:
        """Release native player resources."""


class MpvVideoPlayer:
    """Own one reusable, isolated libmpv player and generation-scoped state."""

    _OBSERVED_PROPERTIES = (
        "pause",
        "time-pos",
        "duration",
        "width",
        "height",
        "eof-reached",
        "core-idle",
    )

    def __init__(
        self,
        *,
        runtime: MpvRuntime,
        player_generation: int,
        event_callback: Callable[[VideoPlaybackEvent], None],
        native_window_id: int | None = None,
    ) -> None:
        """Create a closed player bound to an optional native render surface."""

        self._lock = RLock()
        self._player_generation = player_generation
        self._media_generation = 0
        self._event_callback = event_callback
        self._media_id: UUID | None = None
        self._media_path: Path | None = None
        self._state = VideoPlaybackState.EMPTY
        self._paused = True
        self._loop_enabled = True
        self._user_muted = False
        self._output_active = False
        self._volume = 100
        self._time_seconds: float | None = None
        self._duration_seconds: float | None = None
        self._width: int | None = None
        self._height: int | None = None
        self._error: str | None = None
        self._closed = False
        self._observer = self._property_observed
        self._player = self._create_player(
            runtime.load_module(),
            native_window_id=native_window_id,
        )
        for name in self._OBSERVED_PROPERTIES:
            self._player.observe_property(name, self._observer)

    @property
    def player_generation(self) -> int:
        """Return the immutable generation of this native player."""

        return self._player_generation

    @property
    def media_generation(self) -> int:
        """Return the current media generation."""

        with self._lock:
            return self._media_generation

    def load(self, media_id: UUID, path: Path) -> None:
        """Replace the current decoder input with one validated local file."""

        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise VideoPlayerError(f"Video artifact is unavailable: {resolved.name}")
        with self._lock:
            self._require_open()
            self._media_generation += 1
            self._media_id = media_id
            self._media_path = resolved
            self._state = VideoPlaybackState.LOADING
            self._paused = True
            self._loop_enabled = True
            self._time_seconds = None
            self._duration_seconds = None
            self._width = None
            self._height = None
            self._error = None
            self._apply_audio_state()
            self._player.loop_file = "inf"
            self._player.pause = True
            event = self._event()
        self._event_callback(event)
        try:
            self._player.command("loadfile", str(resolved), "replace")
        except Exception as error:
            self._record_failure("Video could not be loaded.", error)

    def unload(self) -> None:
        """Stop and detach the current media while retaining libmpv."""

        with self._lock:
            self._require_open()
            self._media_generation += 1
            try:
                self._player.command("stop")
            except Exception as error:
                self._record_failure("Video could not be unloaded.", error)
                return
            self._media_id = None
            self._media_path = None
            self._state = VideoPlaybackState.EMPTY
            self._paused = True
            self._time_seconds = None
            self._duration_seconds = None
            self._width = None
            self._height = None
            self._error = None
            self._apply_audio_state()
            event = self._event()
        self._event_callback(event)

    def set_playing(self, playing: bool) -> None:
        """Set playback, restarting an unlooped video when it ended."""

        with self._lock:
            self._require_media()
            if playing and not self._output_active:
                raise VideoPlayerError("Video output is not active.")
            try:
                if playing and self._state is VideoPlaybackState.ENDED:
                    self._player.command("seek", 0.0, "absolute+exact")
                self._player.pause = not playing
            except Exception as error:
                self._record_failure("Playback state could not be changed.", error)
                return
            self._paused = not playing
            self._state = (
                VideoPlaybackState.PLAYING if playing else VideoPlaybackState.READY
            )
            event = self._event()
        self._event_callback(event)

    def seek(self, seconds: float) -> None:
        """Seek to a bounded absolute presentation time."""

        with self._lock:
            self._require_media()
            target = max(0.0, seconds)
            if self._duration_seconds is not None:
                target = min(target, self._duration_seconds)
            try:
                self._player.command("seek", target, "absolute+exact")
            except Exception as error:
                self._record_failure("Video seek failed.", error)

    def step_next_frame(self) -> None:
        """Pause and advance one decoded frame through libmpv."""

        self._step_frame("frame-step", "Next-frame playback failed.")

    def step_previous_frame(self) -> None:
        """Pause and retreat one decoded frame through libmpv."""

        self._step_frame("frame-back-step", "Previous-frame playback failed.")

    def set_loop_enabled(self, enabled: bool) -> None:
        """Apply the current video's loop policy immediately."""

        with self._lock:
            self._require_media()
            try:
                self._player.loop_file = "inf" if enabled else "no"
            except Exception as error:
                self._record_failure("Video loop state could not be changed.", error)
                return
            self._loop_enabled = enabled
            event = self._event()
        self._event_callback(event)

    def set_volume(self, volume: int) -> None:
        """Set user volume in the inclusive range zero through one hundred."""

        with self._lock:
            self._require_open()
            bounded = min(max(int(volume), 0), 100)
            try:
                self._player.volume = bounded
            except Exception as error:
                self._record_failure("Video volume could not be changed.", error)
                return
            self._volume = bounded
            event = self._event()
        self._event_callback(event)

    def set_user_muted(self, muted: bool) -> None:
        """Set user mute without changing inactive-output muting."""

        with self._lock:
            self._require_open()
            self._user_muted = muted
            try:
                self._apply_audio_state()
            except Exception as error:
                self._record_failure("Video mute state could not be changed.", error)
                return
            event = self._event()
        self._event_callback(event)

    def set_output_active(self, active: bool) -> None:
        """Force pause and mute whenever this output is not visible and active."""

        with self._lock:
            self._require_open()
            self._output_active = active
            try:
                if not active and self._media_id is not None:
                    self._player.pause = True
                    self._paused = True
                    if self._state is VideoPlaybackState.PLAYING:
                        self._state = VideoPlaybackState.READY
                self._apply_audio_state()
            except Exception as error:
                self._record_failure(
                    "Video visibility state could not be changed.", error
                )
                return
            event = self._event()
        self._event_callback(event)

    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return the latest coherent adapter-owned state."""

        with self._lock:
            return self._snapshot()

    def close(self) -> None:
        """Invalidate observations and terminate native player resources."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._media_generation += 1
            for name in self._OBSERVED_PROPERTIES:
                self._player.unobserve_property(name, self._observer)
            self._player.terminate()
            self._media_id = None
            self._media_path = None
            self._state = VideoPlaybackState.EMPTY

    @staticmethod
    def _create_player(
        module: ModuleType,
        *,
        native_window_id: int | None,
    ) -> _MpvPlayer:
        """Create the isolated native player with native embedding when supplied."""

        options = local_video_options(
            video_output="gpu-next" if native_window_id is not None else "null",
            audio_output="auto" if native_window_id is not None else "null",
        )
        options.update(
            {
                "idle": "yes",
                "keep_open": "always",
                "pause": True,
                "loop_file": "inf",
                "volume": 100,
                "mute": True,
            }
        )
        if native_window_id is not None:
            options["wid"] = str(native_window_id)
        constructor = cast(Callable[..., _MpvPlayer], getattr(module, "MPV"))
        return constructor(**options)

    def _step_frame(self, command: str, failure_message: str) -> None:
        """Execute one exact decoded-frame command while remaining paused."""

        with self._lock:
            self._require_media()
            try:
                self._player.pause = True
                self._player.command(command)
            except Exception as error:
                self._record_failure(failure_message, error)
                return
            self._paused = True
            self._state = VideoPlaybackState.READY
            event = self._event()
        self._event_callback(event)

    def _property_observed(self, name: str, value: object) -> None:
        """Translate native observations into one generation-scoped snapshot."""

        with self._lock:
            if (
                self._closed
                or self._media_id is None
                or not self._observes_current_path()
            ):
                return
            if name == "pause" and isinstance(value, bool):
                self._paused = value
                if self._state not in {
                    VideoPlaybackState.LOADING,
                    VideoPlaybackState.ENDED,
                    VideoPlaybackState.ERROR,
                }:
                    self._state = (
                        VideoPlaybackState.READY
                        if value
                        else VideoPlaybackState.PLAYING
                    )
            elif name == "time-pos":
                self._time_seconds = _optional_nonnegative_float(value)
            elif name == "duration":
                self._duration_seconds = _optional_nonnegative_float(value)
            elif name == "width":
                self._width = _optional_positive_integer(value)
            elif name == "height":
                self._height = _optional_positive_integer(value)
            elif name == "eof-reached" and value is True:
                self._state = VideoPlaybackState.ENDED
                self._paused = True
            elif name == "core-idle" and value is False:
                self._state = (
                    VideoPlaybackState.READY
                    if self._paused
                    else VideoPlaybackState.PLAYING
                )
            event = self._event()
        self._event_callback(event)

    def _observes_current_path(self) -> bool:
        """Reject late observations that belong to a replaced decoder input."""

        if self._media_path is None:
            return False
        observed_path = self._player.path
        if not isinstance(observed_path, str) or not observed_path:
            return self._state is VideoPlaybackState.LOADING
        try:
            return Path(observed_path).expanduser().resolve() == self._media_path
        except OSError:
            return False

    def _apply_audio_state(self) -> None:
        """Project user mute and visibility into the effective native mute."""

        self._player.mute = self._user_muted or not self._output_active

    def _record_failure(self, message: str, error: Exception) -> None:
        """Store a sanitized failure and notify the current generation."""

        with self._lock:
            self._state = VideoPlaybackState.ERROR
            self._paused = True
            self._error = f"{message} ({type(error).__name__})"
            event = self._event()
        self._event_callback(event)

    def _require_open(self) -> None:
        """Reject commands after deterministic shutdown."""

        if self._closed:
            raise VideoPlayerError("Video player is closed.")

    def _require_media(self) -> None:
        """Reject media commands until a local artifact is loaded."""

        self._require_open()
        if self._media_id is None:
            raise VideoPlayerError("No video is loaded.")

    def _event(self) -> VideoPlaybackEvent:
        """Build one immutable generation-scoped player event."""

        return VideoPlaybackEvent(
            player_generation=self._player_generation,
            media_generation=self._media_generation,
            snapshot=self._snapshot(),
        )

    def _snapshot(self) -> VideoPlaybackSnapshot:
        """Build one immutable snapshot while the adapter lock is held."""

        return VideoPlaybackSnapshot(
            media_id=self._media_id,
            state=self._state,
            paused=self._paused,
            loop_enabled=self._loop_enabled,
            user_muted=self._user_muted,
            effectively_muted=self._user_muted or not self._output_active,
            volume=self._volume,
            time_seconds=self._time_seconds,
            duration_seconds=self._duration_seconds,
            width=self._width,
            height=self._height,
            error=self._error,
        )


def _optional_nonnegative_float(value: object) -> float | None:
    """Return one optional nonnegative numeric observation."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if converted >= 0.0 else None


def _optional_positive_integer(value: object) -> int | None:
    """Return one optional positive integer observation."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = int(value)
    return converted if converted > 0 else None


__all__ = ["MpvVideoPlayer", "VideoPlayerError"]
