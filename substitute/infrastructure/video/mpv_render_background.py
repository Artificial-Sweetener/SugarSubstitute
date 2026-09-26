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

"""Project Output material colors into libmpv's rendered-frame margins."""

from __future__ import annotations

from substitute.infrastructure.video.mpv_player_factory import MpvPlayerProtocol


class MpvRenderBackground:
    """Own normalized and deduplicated libmpv background-color updates."""

    def __init__(self, player: MpvPlayerProtocol) -> None:
        """Retain the native player whose decoded-frame margins are filled."""

        self._player = player
        self._applied_color: tuple[int, int, int, int] | None = None

    def apply(self, color: tuple[int, int, int, int]) -> None:
        """Apply one bounded RGBA color unless the native value is current."""

        channels = tuple(min(255, max(0, int(channel))) for channel in color)
        normalized = (channels[0], channels[1], channels[2], channels[3])
        if normalized == self._applied_color:
            return
        red, green, blue, alpha = normalized
        self._player.background_color = f"#{alpha:02X}{red:02X}{green:02X}{blue:02X}"
        self._applied_color = normalized


__all__ = ["MpvRenderBackground"]
