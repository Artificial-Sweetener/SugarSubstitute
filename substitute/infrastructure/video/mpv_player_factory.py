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

"""Create a closed python-mpv player from validated video preferences."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType
from typing import Protocol, cast

from substitute.domain.generation import (
    VideoHardwareDecoding,
    VideoPlaybackSettings,
    VideoRenderer,
)
from substitute.infrastructure.video.mpv_options import local_video_options


class MpvPlayerProtocol(Protocol):
    """Describe the python-mpv surface used by the playback adapter."""

    pause: object
    loop_file: object
    mute: object
    volume: object
    video_zoom: object
    video_pan_x: object
    video_pan_y: object

    def command(self, name: str, *arguments: object) -> object:
        """Execute one libmpv client command."""

    def _get_property(self, name: str) -> object:
        """Read one native property synchronously on the caller's thread."""

    def terminate(self) -> None:
        """Release native player resources."""


def create_mpv_player(
    module: ModuleType,
    *,
    render_api: bool,
    settings: VideoPlaybackSettings,
) -> MpvPlayerProtocol:
    """Create one isolated player with safe libmpv-render fallbacks."""

    options = local_video_options(
        video_output=_video_output(settings.renderer, render_api=render_api),
        audio_output="auto" if render_api else "null",
    )
    options.update(
        {
            "start_event_thread": False,
            "hwdec": (
                "auto-safe"
                if settings.hardware_decoding is VideoHardwareDecoding.AUTO
                else "no"
            ),
            "idle": "yes",
            "keep_open": "always",
            "pause": True,
            "loop_file": "inf",
            "volume": 100,
            "mute": True,
        }
    )
    constructor = cast(Callable[..., MpvPlayerProtocol], getattr(module, "MPV"))
    player = constructor(**options)
    _release_unused_event_client(module, player)
    return player


def _release_unused_event_client(
    module: ModuleType,
    player: MpvPlayerProtocol,
) -> None:
    """Release python-mpv's undrained client so termination cannot deadlock."""

    event_client = getattr(player, "_event_handle")
    destroy_client = cast(Callable[[object], None], getattr(module, "_mpv_destroy"))
    destroy_client(event_client)
    setattr(player, "_event_handle", None)


def _video_output(renderer: VideoRenderer, *, render_api: bool) -> str:
    """Map one validated renderer policy to libmpv's ordered output list."""

    if not render_api:
        return "null"
    return "libmpv"


__all__ = ["MpvPlayerProtocol", "create_mpv_player"]
