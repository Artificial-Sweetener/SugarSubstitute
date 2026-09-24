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

"""Verify long-lived libmpv playback semantics and lifecycle policy."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from uuid import uuid4

import pytest

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackFallback,
    VideoPlaybackState,
)
from substitute.domain.generation import (
    VideoHardwareDecoding,
    VideoPlaybackSettings,
    VideoRenderer,
)
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_player import (
    MpvVideoPlayer,
    VideoPlayerError,
)


ObservedCallback = Callable[[str, object], None]


class FakePlayer:
    """Model the python-mpv commands and property observers used by playback."""

    def __init__(self, **options: object) -> None:
        """Capture constructor policy and initialize property state."""

        self.options = options
        self.pause: object = options["pause"]
        self.loop_file: object = options["loop_file"]
        self.mute: object = options["mute"]
        self.volume: object = options["volume"]
        self.video_zoom: object = 0.0
        self.video_pan_x: object = 0.0
        self.video_pan_y: object = 0.0
        self.path: object = None
        self.commands: list[tuple[str, tuple[object, ...]]] = []
        self.observers: dict[str, ObservedCallback] = {}
        self.terminated = False
        self.fail_command: str | None = None

    def command(self, name: str, *arguments: object) -> object:
        """Record commands and model load/stop path changes."""

        if name == self.fail_command:
            raise ValueError("sensitive decoder detail")
        self.commands.append((name, arguments))
        if name == "loadfile":
            self.path = arguments[0]
        elif name == "stop":
            self.path = None
        return None

    def observe_property(self, name: str, callback: ObservedCallback) -> None:
        """Register one observer by property name."""

        self.observers[name] = callback

    def unobserve_property(self, name: str, callback: ObservedCallback) -> None:
        """Remove the matching property observer."""

        if self.observers.get(name) is callback:
            del self.observers[name]

    def terminate(self) -> None:
        """Record native player teardown."""

        self.terminated = True

    def emit(self, name: str, value: object) -> None:
        """Deliver one synthetic native property observation."""

        self.observers[name](name, value)


class FakeRuntime:
    """Return one shared fake player from a python-mpv-shaped module."""

    def __init__(self) -> None:
        """Initialize constructor capture state."""

        self.player: FakePlayer | None = None

    def load_module(self) -> ModuleType:
        """Return a binding module whose constructor is called only once."""

        module = ModuleType("mpv")

        def construct(**options: object) -> FakePlayer:
            """Create and retain the sole native player."""

            self.player = FakePlayer(**options)
            return self.player

        module.MPV = construct  # type: ignore[attr-defined]
        return module


def _player(
    tmp_path: Path,
    *,
    native_window_id: int | None = None,
    settings: VideoPlaybackSettings = VideoPlaybackSettings(),
) -> tuple[MpvVideoPlayer, FakePlayer, list[VideoPlaybackEvent], Path]:
    """Return one adapter, native double, event sink, and local video path."""

    runtime = FakeRuntime()
    events: list[VideoPlaybackEvent] = []
    adapter = MpvVideoPlayer(
        runtime=cast(MpvRuntime, runtime),
        player_generation=7,
        event_callback=events.append,
        native_window_id=native_window_id,
        settings=settings,
    )
    assert runtime.player is not None
    video = tmp_path / "generated.webm"
    video.write_bytes(b"video")
    return adapter, runtime.player, events, video


def test_player_uses_closed_runtime_and_native_embedding(tmp_path: Path) -> None:
    """Construct one isolated player with the supplied native render surface."""

    adapter, native, _events, _video = _player(tmp_path, native_window_id=4312)

    assert native.options["vo"] == "gpu-next,gpu"
    assert native.options["hwdec"] == "auto-safe"
    assert native.options["ao"] == "auto"
    assert native.options["wid"] == "4312"
    assert native.options["config"] is False
    assert native.options["load_scripts"] is False
    assert native.options["demuxer_lavf_o"] == "protocol_whitelist=file"
    assert native.options["loop_file"] == "inf"
    assert native.options["mute"] is True
    adapter.close()


def test_player_applies_explicit_safe_video_preferences(tmp_path: Path) -> None:
    """Validated user choices should map to the closed libmpv option surface."""

    adapter, native, _events, _video = _player(
        tmp_path,
        native_window_id=4312,
        settings=VideoPlaybackSettings(
            hardware_decoding=VideoHardwareDecoding.OFF,
            renderer=VideoRenderer.GPU,
        ),
    )

    assert native.options["vo"] == "gpu"
    assert native.options["hwdec"] == "no"
    adapter.close()


def test_load_defaults_to_paused_looping_and_inactive_mute(tmp_path: Path) -> None:
    """Admit each video with loop on while preserving hidden-page safety."""

    adapter, native, events, video = _player(tmp_path)
    media_id = uuid4()

    adapter.load(media_id, video)

    snapshot = adapter.snapshot()
    assert snapshot.media_id == media_id
    assert snapshot.state is VideoPlaybackState.LOADING
    assert snapshot.paused
    assert snapshot.loop_enabled
    assert snapshot.effectively_muted
    assert native.loop_file == "inf"
    assert native.commands == [("loadfile", (str(video.resolve()), "replace"))]
    assert events[-1].player_generation == 7
    assert events[-1].media_generation == 1
    adapter.close()


def test_frame_commands_pause_and_use_decoded_frame_operations(tmp_path: Path) -> None:
    """Never approximate stepping with a frame-rate-derived seek."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    adapter.set_playing(True)

    adapter.step_next_frame()
    adapter.step_previous_frame()

    assert native.pause is True
    assert ("frame-step", ()) in native.commands
    assert ("frame-back-step", ()) in native.commands
    assert adapter.snapshot().paused
    assert adapter.snapshot().state is VideoPlaybackState.READY
    adapter.close()


def test_loop_off_eof_and_play_restart_from_beginning(tmp_path: Path) -> None:
    """Remain ended without looping and restart from zero on the next Play."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    adapter.set_loop_enabled(False)

    native.emit("eof-reached", True)
    assert adapter.snapshot().state is VideoPlaybackState.ENDED
    assert native.loop_file == "no"

    adapter.set_playing(True)
    assert native.commands[-1] == ("seek", (0.0, "absolute+exact"))
    assert adapter.snapshot().state is VideoPlaybackState.PLAYING
    adapter.close()


def test_inactive_output_forces_pause_and_effective_mute(tmp_path: Path) -> None:
    """Hide playback without overwriting the user's volume or mute choice."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    adapter.set_volume(37)
    adapter.set_user_muted(False)
    adapter.set_playing(True)

    adapter.set_output_active(False)

    hidden = adapter.snapshot()
    assert hidden.paused
    assert hidden.effectively_muted
    assert not hidden.user_muted
    assert hidden.volume == 37
    assert native.mute is True

    adapter.set_output_active(True)
    shown = adapter.snapshot()
    assert shown.paused
    assert not shown.effectively_muted
    assert native.mute is False
    adapter.close()


def test_viewport_maps_scale_to_native_zoom_and_pan(tmp_path: Path) -> None:
    """Viewport control should apply bounded logarithmic zoom and normalized pan."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    adapter.set_viewport(4.0, 0.25, -0.5)

    assert native.video_zoom == 2.0
    assert native.video_pan_x == 0.25
    assert native.video_pan_y == -0.5
    adapter.close()


def test_observations_update_state_and_reject_replaced_path(tmp_path: Path) -> None:
    """Publish current-path observations and ignore stale decoder callbacks."""

    adapter, native, events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    native.emit("duration", 2.5)
    native.emit("width", 320)
    native.emit("height", 180)
    native.emit("time-pos", 0.125)
    current_count = len(events)
    native.path = str(tmp_path / "old.webm")
    native.emit("time-pos", 1.75)

    snapshot = adapter.snapshot()
    assert snapshot.duration_seconds == 2.5
    assert snapshot.width == 320
    assert snapshot.height == 180
    assert snapshot.time_seconds == 0.125
    assert len(events) == current_count
    adapter.close()


def test_observations_publish_actual_native_path_and_software_fallback(
    tmp_path: Path,
) -> None:
    """Diagnostics should distinguish requested policy from observed playback."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    native.emit("current-vo", "gpu-next")
    native.emit("gpu-api", "d3d11")
    native.emit("gpu-context", "d3d11")
    native.emit("video-codec", "vp9")
    native.emit("video-format", "yuv420p")
    native.emit("hwdec-current", None)

    diagnostics = adapter.snapshot().diagnostics
    assert diagnostics.actual_video_output == "gpu-next"
    assert diagnostics.gpu_api == "d3d11"
    assert diagnostics.gpu_context == "d3d11"
    assert diagnostics.codec == "vp9"
    assert diagnostics.pixel_format == "yuv420p"
    assert diagnostics.fallback is VideoPlaybackFallback.SOFTWARE_DECODING
    adapter.close()


def test_diagnostics_report_explicit_renderer_fallback(tmp_path: Path) -> None:
    """A renderer override should report when libmpv selects another backend."""

    adapter, native, _events, video = _player(
        tmp_path,
        settings=VideoPlaybackSettings(renderer=VideoRenderer.GPU_NEXT),
    )
    adapter.load(uuid4(), video)

    native.emit("current-vo", "gpu")

    diagnostics = adapter.snapshot().diagnostics
    assert diagnostics.requested_renderer is VideoRenderer.GPU_NEXT
    assert diagnostics.actual_video_output == "gpu"
    assert diagnostics.fallback is VideoPlaybackFallback.RENDERER
    adapter.close()


def test_software_decode_preference_is_not_reported_as_fallback(
    tmp_path: Path,
) -> None:
    """An explicit software choice should remain policy rather than a fallback."""

    adapter, native, _events, video = _player(
        tmp_path,
        settings=VideoPlaybackSettings(
            hardware_decoding=VideoHardwareDecoding.OFF,
        ),
    )
    adapter.load(uuid4(), video)

    native.emit("hwdec-current", None)

    assert adapter.snapshot().diagnostics.fallback is None
    adapter.close()


def test_command_failure_is_sanitized_and_keeps_media_loaded(tmp_path: Path) -> None:
    """Expose an actionable error without leaking native exception detail."""

    adapter, native, _events, video = _player(tmp_path)
    media_id = uuid4()
    adapter.load(media_id, video)
    native.fail_command = "frame-step"

    adapter.step_next_frame()

    snapshot = adapter.snapshot()
    assert snapshot.media_id == media_id
    assert snapshot.state is VideoPlaybackState.ERROR
    assert snapshot.error == "Next-frame playback failed. (ValueError)"
    assert "sensitive" not in snapshot.error
    adapter.close()


def test_close_invalidates_observers_and_terminates_once(tmp_path: Path) -> None:
    """Release callbacks and native resources deterministically and idempotently."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    adapter.close()
    adapter.close()

    assert native.observers == {}
    assert native.terminated
    with pytest.raises(VideoPlayerError, match="closed"):
        adapter.set_volume(50)
