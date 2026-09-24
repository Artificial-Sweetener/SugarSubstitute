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

ObservedMpvCallback = Callable[[str, object], None]


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

    def observe_property(self, name: str, callback: ObservedMpvCallback) -> None:
        """Observe one player property on the native event thread."""

    def unobserve_property(self, name: str, callback: ObservedMpvCallback) -> None:
        """Remove one registered property observation."""

    def terminate(self) -> None:
        """Release native player resources."""


def create_mpv_player(
    module: ModuleType,
    *,
    native_window_id: int | None,
    settings: VideoPlaybackSettings,
) -> MpvPlayerProtocol:
    """Create one isolated native player with safe renderer fallbacks."""

    options = local_video_options(
        video_output=_video_output(
            settings.renderer, embedded=native_window_id is not None
        ),
        audio_output="auto" if native_window_id is not None else "null",
    )
    options.update(
        {
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
    if native_window_id is not None:
        options["wid"] = str(native_window_id)
    constructor = cast(Callable[..., MpvPlayerProtocol], getattr(module, "MPV"))
    return constructor(**options)


def _video_output(renderer: VideoRenderer, *, embedded: bool) -> str:
    """Map one validated renderer policy to libmpv's ordered output list."""

    if not embedded:
        return "null"
    if renderer is VideoRenderer.GPU_NEXT:
        return "gpu-next"
    if renderer is VideoRenderer.GPU:
        return "gpu"
    return "gpu-next,gpu"


__all__ = ["MpvPlayerProtocol", "ObservedMpvCallback", "create_mpv_player"]
