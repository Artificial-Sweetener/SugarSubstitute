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
from typing import cast
from uuid import uuid4

import pytest

from substitute.application.ports.video import (
    VideoPlaybackFallback,
    VideoPlaybackState,
    VideoPresentationSampling,
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
from tests.support.mpv_video_player import (
    FakeMpvRuntime as FakeRuntime,
    create_video_player as _player,
)


def test_player_uses_closed_runtime_and_qt_composited_render_api(
    tmp_path: Path,
) -> None:
    """Construct one isolated player for application-owned OpenGL rendering."""

    adapter, native, _events, _video = _player(tmp_path, render_api=True)

    assert native.options["vo"] == "libmpv"
    assert native.options["hwdec"] == "no"
    assert native.options["ao"] == "auto"
    assert "wid" not in native.options
    assert native.options["config"] is False
    assert native.options["load_scripts"] is False
    assert native.options["demuxer_lavf_o"] == "protocol_whitelist=file"
    assert native.options["background"] == "none"
    assert native.options["background_color"] == "#00000000"
    assert native.options["scale"] == "bilinear"
    assert native.options["loop_file"] == "inf"
    assert native.options["mute"] is True
    assert native.options["start_event_thread"] is False
    assert native._event_handle is None
    adapter.close()


def test_player_applies_explicit_safe_video_preferences(tmp_path: Path) -> None:
    """Validated user choices should map to the closed libmpv option surface."""

    adapter, native, _events, _video = _player(
        tmp_path,
        render_api=True,
        settings=VideoPlaybackSettings(
            hardware_decoding=VideoHardwareDecoding.AUTO,
            renderer=VideoRenderer.GPU,
        ),
    )

    assert native.options["vo"] == "libmpv"
    assert native.options["hwdec"] == "auto-safe"
    adapter.close()


def test_render_context_is_polled_without_native_thread_python_callback(
    tmp_path: Path,
) -> None:
    """Keep every Python and Qt render action on the GUI polling thread."""

    runtime = FakeRuntime()
    adapter = MpvVideoPlayer(
        runtime=cast(MpvRuntime, runtime),
        player_generation=7,
        event_callback=lambda _event: None,
        render_api=True,
    )
    adapter.initialize_renderer(lambda _name: 1234)
    assert len(runtime.render_contexts) == 1
    context = runtime.render_contexts[0]
    resolver = cast(
        Callable[[object, bytes], int],
        cast(dict[str, object], context.options["opengl_init_params"])[
            "get_proc_address"
        ],
    )
    assert resolver(object(), b"glGetString") == 1234
    assert context.update_cb is None
    assert not adapter.poll_renderer_update()
    context.update_pending = True
    assert adapter.poll_renderer_update()
    assert not adapter.poll_renderer_update()

    adapter.render_frame(framebuffer=19, width=1280, height=720)
    adapter.report_swap()
    assert context.rendered == [
        {
            "opengl_fbo": {
                "fbo": 19,
                "w": 1280,
                "h": 720,
                "internal_format": 0,
            },
            "flip_y": True,
        }
    ]
    assert context.swap_count == 1

    adapter.close()
    assert context.freed
    assert context.update_cb is None
    assert runtime.player is not None and runtime.player.terminated


def test_render_background_color_is_applied_as_opaque_mpv_color() -> None:
    """Use the canvas material instead of black for decoded-frame margins."""

    runtime = FakeRuntime()
    adapter = MpvVideoPlayer(
        runtime=cast(MpvRuntime, runtime),
        player_generation=7,
        event_callback=lambda _event: None,
        render_api=True,
    )
    try:
        adapter.set_render_background_color((32, 41, 50, 255))

        assert runtime.player is not None
        assert runtime.player.background_color == "#FF202932"
    finally:
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


def test_frame_step_never_publishes_native_transient_playback(tmp_path: Path) -> None:
    """Keep the Play glyph stable while libmpv advances one paused frame."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    adapter.step_next_frame()

    native.pause = False
    native.emit("time-pos", 0.04)
    adapter.poll_playback_state()

    assert adapter.snapshot().paused
    assert adapter.snapshot().state is VideoPlaybackState.READY

    adapter.set_playing(True)
    assert not adapter.snapshot().paused
    assert adapter.snapshot().state is VideoPlaybackState.PLAYING
    adapter.close()


def test_frame_step_waits_for_an_inflight_exact_seek(tmp_path: Path) -> None:
    """Preserve a user's step request until libmpv finishes repositioning."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    native.emit("seeking", True)

    adapter.seek(0.5)
    adapter.step_next_frame()

    assert ("frame-step", ()) not in native.commands
    native.emit("seeking", False)
    adapter.poll_playback_state()
    assert native.commands[-1] == ("frame-step", ())
    adapter.close()


def test_loop_off_eof_and_play_restart_from_beginning(tmp_path: Path) -> None:
    """Remain ended without looping and restart from zero on the next Play."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    adapter.set_output_active(True)
    adapter.set_loop_enabled(False)

    native.emit("eof-reached", True)
    adapter.poll_playback_state()
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


def test_viewport_maps_geometry_and_sampling_to_native_properties(
    tmp_path: Path,
) -> None:
    """Viewport control should apply bounded geometry and explicit source sampling."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    adapter.set_viewport(
        4.0,
        0.25,
        -0.5,
        VideoPresentationSampling.NEAREST,
    )

    assert native.video_zoom == 2.0
    assert native.video_pan_x == 0.25
    assert native.video_pan_y == -0.5
    assert native.scale == "nearest"

    adapter.set_viewport(
        1.5,
        0.0,
        0.0,
        VideoPresentationSampling.BILINEAR,
    )
    assert str(native.scale) == "bilinear"
    adapter.close()


def test_observations_update_state_and_reject_replaced_path(tmp_path: Path) -> None:
    """Publish current-path observations and ignore stale decoder callbacks."""

    adapter, native, events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    native.emit("duration", 2.5)
    native.emit("width", 320)
    native.emit("height", 180)
    native.emit("time-pos", 0.125)
    adapter.poll_playback_state()
    current_count = len(events)
    native.emit("path", str(tmp_path / "old.webm"))
    native.emit("time-pos", 1.75)
    adapter.poll_playback_state()

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

    adapter, native, _events, video = _player(
        tmp_path,
        settings=VideoPlaybackSettings(
            hardware_decoding=VideoHardwareDecoding.AUTO,
        ),
    )
    adapter.load(uuid4(), video)

    native.emit("current-vo", "gpu-next")
    native.emit("gpu-api", "d3d11")
    native.emit("gpu-context", "d3d11")
    native.emit("video-codec", "vp9")
    native.emit("video-params/pixelformat", "yuv420p")
    native.emit("hwdec-current", None)
    adapter.poll_playback_state()

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
    adapter.poll_playback_state()

    diagnostics = adapter.snapshot().diagnostics
    assert diagnostics.requested_renderer is VideoRenderer.GPU_NEXT
    assert diagnostics.actual_video_output == "gpu"
    assert diagnostics.fallback is VideoPlaybackFallback.RENDERER
    adapter.close()


def test_render_api_is_the_requested_qt_composition_path(tmp_path: Path) -> None:
    """The libmpv VO should not be mislabeled as a renderer fallback."""

    adapter, native, _events, video = _player(
        tmp_path,
        render_api=True,
        settings=VideoPlaybackSettings(renderer=VideoRenderer.GPU_NEXT),
    )
    adapter.load(uuid4(), video)

    native.emit("current-vo", "libmpv")
    adapter.poll_playback_state()

    diagnostics = adapter.snapshot().diagnostics
    assert diagnostics.actual_video_output == "libmpv"
    assert diagnostics.fallback is None
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
    adapter.poll_playback_state()

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


def test_queued_frame_step_failure_is_sanitized(tmp_path: Path) -> None:
    """Contain a decoder failure raised after an asynchronous seek settles."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    native.emit("seeking", True)
    adapter.seek(0.5)
    adapter.step_next_frame()
    native.fail_command = "frame-step"

    native.emit("seeking", False)
    adapter.poll_playback_state()

    snapshot = adapter.snapshot()
    assert snapshot.state is VideoPlaybackState.ERROR
    assert snapshot.error == "Queued frame advancement failed. (ValueError)"
    adapter.close()


def test_close_terminates_callback_free_player_once(tmp_path: Path) -> None:
    """Release callback-free native resources deterministically and idempotently."""

    adapter, native, _events, video = _player(tmp_path)
    adapter.load(uuid4(), video)

    adapter.close()
    adapter.close()

    assert native.terminated
    with pytest.raises(VideoPlayerError, match="closed"):
        adapter.set_volume(50)


def test_native_state_changes_publish_only_when_caller_polls(tmp_path: Path) -> None:
    """Never let a background libmpv thread enter application Python code."""

    adapter, native, events, video = _player(tmp_path)
    adapter.load(uuid4(), video)
    initial_count = len(events)
    native.emit("time-pos", 0.5)

    assert len(events) == initial_count
    adapter.poll_playback_state()
    assert len(events) == initial_count + 1
    assert events[-1].snapshot.time_seconds == 0.5
    adapter.close()
