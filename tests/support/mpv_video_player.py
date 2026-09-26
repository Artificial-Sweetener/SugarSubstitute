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

"""Provide deterministic python-mpv playback doubles and adapter fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

from substitute.application.ports.video import VideoPlaybackEvent
from substitute.domain.generation import VideoPlaybackSettings
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_player import MpvVideoPlayer


class FakeMpvPlayer:
    """Model the synchronous python-mpv surface used by playback."""

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
        self.scale: object = options["scale"]
        self.background_color: object = options["background_color"]
        self._event_handle: object | None = object()
        self.path: object = None
        self.commands: list[tuple[str, tuple[object, ...]]] = []
        self.properties: dict[str, object] = {
            "path": None,
            "pause": self.pause,
            "time-pos": None,
            "duration": None,
            "width": None,
            "height": None,
            "eof-reached": False,
            "seeking": False,
            "core-idle": None,
            "current-vo": None,
            "gpu-api": None,
            "gpu-context": None,
            "hwdec-current": None,
            "video-params/pixelformat": None,
            "video-codec": None,
        }
        self.screenshot_result: object = bgr0_frame(2, 1, (0, 0, 255, 0))
        self.terminated = False
        self.fail_command: str | None = None

    def command(self, name: str, *arguments: object) -> object:
        """Record commands and model load, stop, and screenshot results."""

        if name == self.fail_command:
            raise ValueError("sensitive decoder detail")
        self.commands.append((name, arguments))
        if name == "loadfile":
            self.path = arguments[0]
            self.properties["path"] = arguments[0]
        elif name == "stop":
            self.path = None
            self.properties["path"] = None
        elif name == "screenshot-raw":
            return self.screenshot_result
        return None

    def _get_property(self, name: str) -> object:
        """Return one synchronously polled property."""

        if name == "pause":
            return self.pause
        return self.properties[name]

    def terminate(self) -> None:
        """Record native player teardown."""

        self.terminated = True

    def emit(self, name: str, value: object) -> None:
        """Change one property for the next caller-owned polling pass."""

        self.properties[name] = value


class FakeMpvRuntime:
    """Return one shared fake player from a python-mpv-shaped module."""

    def __init__(self) -> None:
        """Initialize constructor capture state."""

        self.player: FakeMpvPlayer | None = None
        self.render_contexts: list[FakeRenderContext] = []

    def load_module(self) -> ModuleType:
        """Return a binding module whose constructor is called only once."""

        module = ModuleType("mpv")

        def construct(**options: object) -> FakeMpvPlayer:
            """Create and retain the sole native player."""

            self.player = FakeMpvPlayer(**options)
            return self.player

        module.MPV = construct  # type: ignore[attr-defined]
        module.MpvGlGetProcAddressFn = lambda callback: callback  # type: ignore[attr-defined]

        def destroy_event_client(event_client: object) -> None:
            """Record disposal of python-mpv's unused event client."""

            assert self.player is not None
            assert event_client is self.player._event_handle

        module._mpv_destroy = destroy_event_client  # type: ignore[attr-defined]

        def construct_render_context(
            player: FakeMpvPlayer,
            api_type: str,
            **options: object,
        ) -> FakeRenderContext:
            """Create and retain one observable fake render context."""

            context = FakeRenderContext(player, api_type, **options)
            self.render_contexts.append(context)
            return context

        module.MpvRenderContext = construct_render_context  # type: ignore[attr-defined]
        return module


class FakeRenderContext:
    """Record render-API lifecycle without an OpenGL dependency."""

    def __init__(
        self,
        player: FakeMpvPlayer,
        api_type: str,
        **options: object,
    ) -> None:
        """Capture the player, API, and initialization parameters."""

        self.player = player
        self.api_type = api_type
        self.options = options
        self.update_cb: Callable[[], None] | None = None
        self.update_pending = False
        self.rendered: list[dict[str, object]] = []
        self.swap_count = 0
        self.freed = False

    def update(self) -> bool:
        """Return and clear the render update requested by libmpv."""

        pending = self.update_pending
        self.update_pending = False
        return pending

    def render(self, **options: object) -> None:
        """Record one framebuffer render."""

        self.rendered.append(options)

    def report_swap(self) -> None:
        """Record one completed swap."""

        self.swap_count += 1

    def free(self) -> None:
        """Record deterministic release."""

        self.freed = True


def create_video_player(
    tmp_path: Path,
    *,
    render_api: bool = False,
    settings: VideoPlaybackSettings = VideoPlaybackSettings(),
) -> tuple[MpvVideoPlayer, FakeMpvPlayer, list[VideoPlaybackEvent], Path]:
    """Return one adapter, native double, event sink, and local video path."""

    runtime = FakeMpvRuntime()
    events: list[VideoPlaybackEvent] = []
    adapter = MpvVideoPlayer(
        runtime=cast(MpvRuntime, runtime),
        player_generation=7,
        event_callback=events.append,
        render_api=render_api,
        settings=settings,
    )
    assert runtime.player is not None
    video = tmp_path / "generated.webm"
    video.write_bytes(b"video")
    return adapter, runtime.player, events, video


def bgr0_frame(
    width: int,
    height: int,
    pixel: tuple[int, int, int, int],
) -> dict[str, object]:
    """Return one tightly packed constant-color libmpv screenshot node."""

    stride = width * 4
    return {
        "format": "bgr0",
        "w": width,
        "h": height,
        "stride": stride,
        "data": bytes(pixel) * width * height,
    }


__all__ = [
    "FakeMpvPlayer",
    "FakeMpvRuntime",
    "FakeRenderContext",
    "bgr0_frame",
    "create_video_player",
]
