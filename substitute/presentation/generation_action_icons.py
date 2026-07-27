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

"""Define the shared visual language for generation action controls."""

from __future__ import annotations

from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.resources.app_icon import AppIcon


GENERATE_ACTION_ICON = FIF.PLAY_SOLID
CONTINUOUS_GENERATION_ACTION_ICON = AppIcon.INFINITY_HIGH_CONTRAST
SKIP_GENERATION_ACTION_ICON = AppIcon.NEXT_24_FILLED
STOP_GENERATION_ACTION_ICON = AppIcon.STOP_SOLID


__all__ = [
    "CONTINUOUS_GENERATION_ACTION_ICON",
    "GENERATE_ACTION_ICON",
    "SKIP_GENERATION_ACTION_ICON",
    "STOP_GENERATION_ACTION_ICON",
]
