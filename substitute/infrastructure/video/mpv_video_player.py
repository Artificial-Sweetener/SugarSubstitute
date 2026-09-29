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
from uuid import UUID

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPresentationSampling,
    VideoRepresentativeFrame,
)
from substitute.domain.generation import VideoPlaybackSettings
from substitute.infrastructure.video.mpv_playback_diagnostics import (
    build_playback_diagnostics,
)
from substitute.infrastructure.video.mpv_player_factory import (
    MpvPlayerProtocol,
    create_mpv_player,
)
from substitute.infrastructure.video.mpv_representative_frame import (
    MpvRepresentativeFrameCapture,
)
from substitute.infrastructure.video.mpv_observation_values import (
    MPV_PLAYBACK_OBSERVED_PROPERTIES,
    observation_matches_media,
    optional_nonnegative_float,
    optional_positive_integer,
    optional_string,
)
from substitute.infrastructure.video.mpv_frame_step_coordinator import (
    MpvFrameStepCoordinator,
)
from substitute.infrastructure.video.mpv_render_background import MpvRenderBackground
from substitute.infrastructure.video.mpv_opengl_render_bridge import (
    MpvOpenGLRenderBridge,
)
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_viewport_presentation import (
    MpvViewportPresentation,
)
from substitute.infrastructure.video.video_player_error import VideoPlayerError


class MpvVideoPlayer:
    """Own one reusable, isolated libmpv player and generation-scoped state."""

    def __init__(
        self,
        *,
        runtime: MpvRuntime,
        player_generation: int,
        event_callback: Callable[[VideoPlaybackEvent], None],
        render_api: bool = False,
        settings: VideoPlaybackSettings = VideoPlaybackSettings(),
    ) -> None:
        """Create a closed player prepared for optional OpenGL rendering."""

        self._lock = RLock()
        self._player_generation = player_generation
        self._media_generation = 0
        self._event_callback = event_callback
        self._media_id: UUID | None = None
        self._media_path: Path | None = None
        self._observed_path: str | None = None
        self._state = VideoPlaybackState.EMPTY
        self._paused = True
        self._frame_step_pause_latched = False
        self._loop_enabled = True
        self._user_muted = False
        self._output_active = False
        self._volume = 100
        self._time_seconds: float | None = None
        self._duration_seconds: float | None = None
        self._width: int | None = None
        self._height: int | None = None
        self._error: str | None = None
        self._last_polled_snapshot: VideoPlaybackSnapshot | None = None
        self._settings = settings
        self._render_api = render_api
        self._actual_video_output: str | None = None
        self._gpu_api: str | None = None
        self._gpu_context: str | None = None
        self._hardware_decoder: str | None = None
        self._hardware_decoder_observed = False
        self._pixel_format: str | None = None
        self._codec: str | None = None
        self._presentation_sampling = VideoPresentationSampling.BILINEAR
        self._closed = False
        self._module = runtime.load_module()
        self._player: MpvPlayerProtocol = create_mpv_player(
            self._module,
            render_api=render_api,
            settings=settings,
        )
        self._frame_steps = MpvFrameStepCoordinator(self._player)
        self._render_background = MpvRenderBackground(self._player)
        self._renderer = MpvOpenGLRenderBridge(self._module, self._player)
        self._representative_frames = MpvRepresentativeFrameCapture()
        self._viewport = MpvViewportPresentation(self._player)

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
            self._representative_frames.reset()
            self._media_id = media_id
            self._media_path = resolved
            self._observed_path = None
            self._state = VideoPlaybackState.LOADING
            self._paused = True
            self._frame_step_pause_latched = False
            self._frame_steps.reset()
            self._loop_enabled = True
            self._time_seconds = None
            self._duration_seconds = None
            self._width = None
            self._height = None
            self._hardware_decoder = None
            self._hardware_decoder_observed = False
            self._pixel_format = None
            self._codec = None
            self._error = None
            self._apply_audio_state()
            self._player.loop_file = "inf"
            self._player.pause = True
            self._player.video_zoom = 0.0
            self._player.video_pan_x = 0.0
            self._player.video_pan_y = 0.0
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
            self._observed_path = None
            self._state = VideoPlaybackState.EMPTY
            self._paused = True
            self._frame_step_pause_latched = False
            self._frame_steps.reset()
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
            self._frame_step_pause_latched = False
            if playing:
                self._frame_steps.cancel_steps()
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
                self._frame_steps.seek(target)
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

    def set_viewport(
        self,
        zoom: float,
        pan_x: float,
        pan_y: float,
        sampling: VideoPresentationSampling,
    ) -> None:
        """Apply bounded viewport geometry and the selected native sampler."""

        with self._lock:
            self._require_media()
            try:
                self._presentation_sampling = self._viewport.apply(
                    zoom=zoom,
                    pan_x=pan_x,
                    pan_y=pan_y,
                    sampling=sampling,
                )
            except Exception as error:
                self._record_failure("Video viewport could not be changed.", error)

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

    def poll_playback_state(self) -> None:
        """Read native state without allowing libmpv to call into Python."""

        with self._lock:
            self._require_open()
            if self._media_id is None:
                return
            try:
                observations = {
                    name: self._player._get_property(name)
                    for name in MPV_PLAYBACK_OBSERVED_PROPERTIES
                }
            except Exception as error:
                self._record_failure("Video state could not be read.", error)
                return
            for name, value in observations.items():
                self._apply_observation(name, value)
            try:
                self._frame_steps.observe_seeking(observations["seeking"])
            except Exception as error:
                self._record_failure("Queued frame advancement failed.", error)
                return
            event = self._event()
            if event.snapshot == self._last_polled_snapshot:
                return
            representative_frame = self._representative_frames.capture_if_changed(
                self._player,
                event.snapshot,
            )
            if representative_frame is not None:
                event = self._event(representative_frame=representative_frame)
            self._last_polled_snapshot = event.snapshot
        self._event_callback(event)

    def initialize_renderer(
        self,
        get_proc_address: Callable[[str], int],
    ) -> None:
        """Create libmpv's render context against the current Qt GL context."""

        with self._lock:
            self._require_open()
        self._renderer.initialize(get_proc_address)

    def set_render_background_color(self, color: tuple[int, int, int, int]) -> None:
        """Set libmpv's fill for pixels outside the decoded video rectangle."""

        with self._lock:
            self._require_open()
            self._render_background.apply(color)

    def poll_renderer_update(self) -> bool:
        """Acknowledge one render update without a native-thread Python callback."""

        with self._lock:
            self._require_open()
        return self._renderer.poll_update()

    def render_frame(
        self,
        *,
        framebuffer: int,
        width: int,
        height: int,
    ) -> None:
        """Render one frame into the current OpenGL framebuffer."""

        self._renderer.render(
            framebuffer=framebuffer,
            width=width,
            height=height,
        )

    def report_swap(self) -> None:
        """Report presentation of the most recently rendered frame."""

        self._renderer.report_swap()

    def release_renderer(self) -> None:
        """Release the render context before terminating the mpv client."""

        self._renderer.release()

    def close(self) -> None:
        """Invalidate observations and terminate native player resources."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._media_generation += 1
            self._media_id = None
            self._media_path = None
            self._observed_path = None
            self._state = VideoPlaybackState.EMPTY
        self.release_renderer()
        self._player.terminate()

    def _step_frame(self, command: str, failure_message: str) -> None:
        """Execute one exact decoded-frame command while remaining paused."""

        with self._lock:
            self._require_media()
            try:
                self._frame_steps.step(command)
            except Exception as error:
                self._record_failure(failure_message, error)
                return
            self._paused = True
            self._frame_step_pause_latched = True
            self._state = VideoPlaybackState.READY
            event = self._event()
        self._event_callback(event)

    def _apply_observation(self, name: str, value: object) -> None:
        """Fold one synchronously read native property into owned state."""

        if self._closed or self._media_id is None:
            return
        if name == "path":
            self._observed_path = optional_string(value)
            return
        if not observation_matches_media(
            media_path=self._media_path,
            observed_path=self._observed_path,
            state=self._state,
        ):
            return
        if name == "pause" and isinstance(value, bool):
            if self._frame_step_pause_latched and not value:
                return
            self._paused = value
            if self._state not in {
                VideoPlaybackState.LOADING,
                VideoPlaybackState.ENDED,
                VideoPlaybackState.ERROR,
            }:
                self._state = (
                    VideoPlaybackState.READY if value else VideoPlaybackState.PLAYING
                )
        elif name == "time-pos":
            self._time_seconds = optional_nonnegative_float(value)
        elif name == "duration":
            self._duration_seconds = optional_nonnegative_float(value)
        elif name == "width":
            self._width = optional_positive_integer(value)
        elif name == "height":
            self._height = optional_positive_integer(value)
        elif name == "eof-reached" and value is True:
            self._state = VideoPlaybackState.ENDED
            self._paused = True
        elif name == "core-idle" and value is False:
            self._state = (
                VideoPlaybackState.READY if self._paused else VideoPlaybackState.PLAYING
            )
        elif name == "current-vo":
            self._actual_video_output = optional_string(value)
        elif name == "gpu-api":
            self._gpu_api = optional_string(value)
        elif name == "gpu-context":
            self._gpu_context = optional_string(value)
        elif name == "hwdec-current":
            self._hardware_decoder_observed = True
            self._hardware_decoder = optional_string(value)
        elif name == "video-params/pixelformat":
            self._pixel_format = optional_string(value)
        elif name == "video-codec":
            self._codec = optional_string(value)

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

    def _event(
        self,
        *,
        representative_frame: VideoRepresentativeFrame | None = None,
    ) -> VideoPlaybackEvent:
        """Build one immutable generation-scoped player event."""

        return VideoPlaybackEvent(
            player_generation=self._player_generation,
            media_generation=self._media_generation,
            snapshot=self._snapshot(),
            representative_frame=representative_frame,
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
            diagnostics=build_playback_diagnostics(
                settings=self._settings,
                render_api=self._render_api,
                actual_video_output=self._actual_video_output,
                gpu_api=self._gpu_api,
                gpu_context=self._gpu_context,
                hardware_decoder_observed=self._hardware_decoder_observed,
                hardware_decoder=self._hardware_decoder,
                pixel_format=self._pixel_format,
                codec=self._codec,
                presentation_sampling=self._presentation_sampling,
            ),
        )


__all__ = ["MpvVideoPlayer", "VideoPlayerError"]
