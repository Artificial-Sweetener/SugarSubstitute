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

"""Record bounded diagnostics for shared presentation motion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MotionTelemetry:
    """Record bounded preparation and paint evidence for one controller."""

    plans_started: int = 0
    plans_finished: int = 0
    plans_cancelled: int = 0
    plans_settled_immediately: int = 0
    preparation_ms: list[float] = field(default_factory=list)
    paint_ms: list[float] = field(default_factory=list)
    last_capture_target_count: int = 0
    last_capture_target_pixels: int = 0


__all__ = ["MotionTelemetry"]
