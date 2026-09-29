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

"""Apply bounded Output viewport presentation to python-mpv properties."""

from __future__ import annotations

from math import log2

from substitute.application.ports.video import VideoPresentationSampling
from substitute.infrastructure.video.mpv_player_factory import MpvPlayerProtocol


class MpvViewportPresentation:
    """Own native viewport bounds, logarithmic scale, pan, and sampling."""

    def __init__(self, player: MpvPlayerProtocol) -> None:
        """Store the isolated player property surface."""

        self._player = player

    def apply(
        self,
        *,
        zoom: float,
        pan_x: float,
        pan_y: float,
        sampling: VideoPresentationSampling,
    ) -> VideoPresentationSampling:
        """Apply bounded geometry and return the active sampling policy."""

        bounded_zoom = min(max(float(zoom), 1.0 / 64.0), 64.0)
        self._player.video_zoom = log2(bounded_zoom)
        self._player.video_pan_x = min(max(float(pan_x), -1.0), 1.0)
        self._player.video_pan_y = min(max(float(pan_y), -1.0), 1.0)
        self._player.scale = sampling.value
        return sampling


__all__ = ["MpvViewportPresentation"]
