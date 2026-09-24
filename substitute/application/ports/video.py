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

"""Define application-owned video probing and playback contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.domain.generation import VideoHardwareDecoding, VideoRenderer


@dataclass(frozen=True, slots=True)
class VideoProbeResult:
    """Describe one decodable local video and its static poster."""

    width: int
    height: int
    duration_seconds: float | None
    mime_type: str | None
    poster_bytes: bytes
    codec: str | None = None
    pixel_format: str | None = None


class VideoPlaybackState(StrEnum):
    """Name the stable playback states projected to presentation."""

    EMPTY = "empty"
    LOADING = "loading"
    READY = "ready"
    PLAYING = "playing"
    ENDED = "ended"
    ERROR = "error"


class VideoPlaybackFallback(StrEnum):
    """Describe one safe native playback fallback selected at runtime."""

    SOFTWARE_DECODING = "software_decoding"
    RENDERER = "renderer"


class VideoRuntimeUnavailableError(RuntimeError):
    """Report that the project-owned video runtime cannot be loaded."""


@dataclass(frozen=True, slots=True)
class VideoPlaybackDiagnostics:
    """Expose requested and observed native playback facts for support reports."""

    requested_hardware_decoding: VideoHardwareDecoding = VideoHardwareDecoding.AUTO
    requested_renderer: VideoRenderer = VideoRenderer.AUTO
    actual_video_output: str | None = None
    gpu_api: str | None = None
    gpu_context: str | None = None
    hardware_decoder: str | None = None
    pixel_format: str | None = None
    codec: str | None = None
    fallback: VideoPlaybackFallback | None = None


@dataclass(frozen=True, slots=True)
class VideoPlaybackSnapshot:
    """Expose the current player state without leaking libmpv types."""

    media_id: UUID | None
    state: VideoPlaybackState
    paused: bool
    loop_enabled: bool
    user_muted: bool
    effectively_muted: bool
    volume: int
    time_seconds: float | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    error: str | None = None
    diagnostics: VideoPlaybackDiagnostics = VideoPlaybackDiagnostics()


@dataclass(frozen=True, slots=True)
class VideoPlaybackEvent:
    """Carry one generation-scoped player observation to presentation."""

    player_generation: int
    media_generation: int
    snapshot: VideoPlaybackSnapshot


class VideoProbe(Protocol):
    """Validate local video media and produce its first-frame poster."""

    def probe(self, path: Path) -> VideoProbeResult:
        """Return validated media facts or raise a diagnostic exception."""


class VideoPlayerPort(Protocol):
    """Control one long-lived local-video player instance."""

    @property
    def player_generation(self) -> int:
        """Return the immutable generation of this player instance."""

    @property
    def media_generation(self) -> int:
        """Return the generation of the currently loaded media."""

    def load(self, media_id: UUID, path: Path) -> None:
        """Replace the current media with one validated local artifact."""

    def unload(self) -> None:
        """Release the current decoder while retaining the player instance."""

    def set_playing(self, playing: bool) -> None:
        """Set whether the current video is actively playing."""

    def seek(self, seconds: float) -> None:
        """Seek to an absolute presentation time."""

    def step_next_frame(self) -> None:
        """Pause and advance exactly one decoded frame."""

    def step_previous_frame(self) -> None:
        """Pause and retreat exactly one decoded frame."""

    def set_loop_enabled(self, enabled: bool) -> None:
        """Apply looping to the current video immediately."""

    def set_volume(self, volume: int) -> None:
        """Set user volume in the inclusive range zero through one hundred."""

    def set_user_muted(self, muted: bool) -> None:
        """Set the user's persistent-in-session mute choice."""

    def set_viewport(self, zoom: float, pan_x: float, pan_y: float) -> None:
        """Apply normalized zoom and pan to the rendered video."""

    def set_output_active(self, active: bool) -> None:
        """Pause and effectively mute playback while the output is inactive."""

    def snapshot(self) -> VideoPlaybackSnapshot:
        """Return the latest coherent player state."""

    def close(self) -> None:
        """Terminate callbacks, decoding, and native player resources."""


__all__ = [
    "VideoPlaybackEvent",
    "VideoPlaybackDiagnostics",
    "VideoPlaybackFallback",
    "VideoPlaybackSnapshot",
    "VideoPlaybackState",
    "VideoPlayerPort",
    "VideoProbe",
    "VideoProbeResult",
    "VideoRuntimeUnavailableError",
]
