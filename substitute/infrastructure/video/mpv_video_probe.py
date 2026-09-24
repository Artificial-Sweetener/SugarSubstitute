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

"""Validate generated videos and extract bounded first-frame posters via mpv."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

from PIL import Image

from substitute.application.ports.video import VideoProbeResult
from substitute.infrastructure.video.mpv_options import local_video_options
from substitute.infrastructure.video.mpv_runtime import MpvRuntime


_POSTER_MAX_EDGE = 1024
_LOAD_TIMEOUT_SECONDS = 15.0


class VideoProbeError(RuntimeError):
    """Report a generated artifact that libmpv could not validate."""


class _MpvProbePlayer(Protocol):
    """Describe the python-mpv surface used by the probe."""

    duration: object
    width: object
    height: object
    video_codec: object
    video_format: object
    pause: object

    def play(self, filename: str) -> None:
        """Load and start one local file."""

    def wait_until_playing(self, timeout: float) -> None:
        """Wait until the first displayable frame has decoded."""

    def screenshot_raw(self) -> Image.Image:
        """Return the currently displayed frame."""

    def terminate(self) -> None:
        """Release native probe resources."""


class MpvVideoProbe:
    """Probe one local artifact with an isolated headless libmpv instance."""

    def __init__(self, runtime: MpvRuntime) -> None:
        """Store the deterministic native runtime owner."""

        self._runtime = runtime

    def probe(self, path: Path) -> VideoProbeResult:
        """Validate media and return metadata plus a bounded PNG poster."""

        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise VideoProbeError(f"Video artifact is unavailable: {resolved.name}")
        player: _MpvProbePlayer | None = None
        try:
            player = self._create_player(self._runtime.load_module())
            player.play(str(resolved))
            player.wait_until_playing(timeout=_LOAD_TIMEOUT_SECONDS)
            player.pause = True
            poster = player.screenshot_raw()
            width = _positive_integer(player.width, "width")
            height = _positive_integer(player.height, "height")
            return VideoProbeResult(
                width=width,
                height=height,
                duration_seconds=_optional_nonnegative_float(player.duration),
                mime_type=_mime_type(resolved.suffix),
                poster_bytes=_encode_poster(poster),
                codec=_optional_string(player.video_codec),
                pixel_format=_optional_string(player.video_format),
            )
        except VideoProbeError:
            raise
        except Exception as error:
            raise VideoProbeError(
                f"Video artifact could not be decoded: {resolved.name}"
            ) from error
        finally:
            if player is not None:
                player.terminate()

    @staticmethod
    def _create_player(module: ModuleType) -> _MpvProbePlayer:
        """Create one closed headless player from the loaded binding."""

        constructor = cast(
            Callable[..., _MpvProbePlayer],
            getattr(module, "MPV"),
        )
        return constructor(
            **local_video_options(video_output="null", audio_output="null")
        )


def _encode_poster(source: Image.Image) -> bytes:
    """Normalize one decoded frame to a bounded deterministic RGB PNG."""

    poster = source.convert("RGB")
    poster.thumbnail(
        (_POSTER_MAX_EDGE, _POSTER_MAX_EDGE),
        Image.Resampling.LANCZOS,
    )
    output = BytesIO()
    poster.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _positive_integer(value: object, label: str) -> int:
    """Return one required positive integer media property."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VideoProbeError(f"Video {label} is unavailable.")
    integer = int(value)
    if integer <= 0:
        raise VideoProbeError(f"Video {label} is invalid.")
    return integer


def _optional_nonnegative_float(value: object) -> float | None:
    """Return one optional finite nonnegative numeric media property."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if converted >= 0.0 else None


def _optional_string(value: object) -> str | None:
    """Return one nonempty optional media string."""

    return value if isinstance(value, str) and value else None


def _mime_type(suffix: str) -> str | None:
    """Return the supported container MIME type for one local suffix."""

    return {
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".gif": "image/gif",
    }.get(suffix.casefold())


__all__ = ["MpvVideoProbe", "VideoProbeError"]
