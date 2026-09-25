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

"""Capture changed paused frames from libmpv without affecting playback."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from substitute.application.ports.video import (
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoRepresentativeFrame,
)
from substitute.infrastructure.video.mpv_player_factory import MpvPlayerProtocol
from substitute.shared.logging.logger import get_logger, log_warning_exception

_LOGGER = get_logger("infrastructure.video.mpv_representative_frame")


class MpvRepresentativeFrameCapture:
    """Capture at most one source frame for each observed paused position."""

    def __init__(self) -> None:
        """Initialize without a previously published media position."""

        self._captured_position: tuple[UUID, float] | None = None

    def reset(self) -> None:
        """Allow a reloaded media generation to publish its current position."""

        self._captured_position = None

    def capture_if_changed(
        self,
        player: MpvPlayerProtocol,
        snapshot: VideoPlaybackSnapshot,
    ) -> VideoRepresentativeFrame | None:
        """Return a decoded source frame only for a new stable paused position."""

        media_id = snapshot.media_id
        time_seconds = snapshot.time_seconds
        if (
            media_id is None
            or time_seconds is None
            or not snapshot.paused
            or snapshot.state
            not in {VideoPlaybackState.READY, VideoPlaybackState.ENDED}
        ):
            return None
        position = (media_id, time_seconds)
        if position == self._captured_position:
            return None
        try:
            frame = _representative_frame(
                player.command("screenshot-raw", "video"),
                time_seconds=time_seconds,
            )
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "Could not capture paused video representative frame",
                error=error,
                media_id=str(media_id),
                time_seconds=time_seconds,
            )
            return None
        self._captured_position = position
        return frame


def _representative_frame(
    value: object,
    *,
    time_seconds: float,
) -> VideoRepresentativeFrame:
    """Normalize one python-mpv screenshot node into detached BGR0 bytes."""

    if not isinstance(value, Mapping) or value.get("format") != "bgr0":
        raise ValueError("libmpv returned an unsupported screenshot format")
    width = _positive_integer(value["w"], "width")
    height = _positive_integer(value["h"], "height")
    stride = _positive_integer(value["stride"], "stride")
    pixels = value["data"]
    if not isinstance(pixels, (bytes, bytearray, memoryview)):
        raise TypeError("libmpv screenshot pixels are not bytes")
    return VideoRepresentativeFrame(
        time_seconds=time_seconds,
        width=width,
        height=height,
        stride=stride,
        pixels=bytes(pixels),
    )


def _positive_integer(value: object, label: str) -> int:
    """Return one required positive integer screenshot field."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"libmpv screenshot {label} is not numeric")
    integer = int(value)
    if integer <= 0:
        raise ValueError(f"libmpv screenshot {label} is not positive")
    return integer


__all__ = ["MpvRepresentativeFrameCapture"]
