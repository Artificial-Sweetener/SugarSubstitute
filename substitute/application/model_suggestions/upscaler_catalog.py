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

"""Define the reviewed upscale-model recommendation policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CuratedUpscaler:
    """Identify one reviewed OpenModelDB model and its recommendation purpose."""

    model_id: str
    purpose: str


CURATED_UPSCALERS = (
    CuratedUpscaler("4x-realesrgan-x4plus-anime-6b", "anime-fast"),
    CuratedUpscaler("4x-Remacri", "general-balanced"),
    CuratedUpscaler("2x-LiveActionV1-SPAN", "live-action"),
    CuratedUpscaler("1x-DeJPG-realplksr-otf", "jpeg-restoration"),
    CuratedUpscaler("4x-WTP-UDS-Esrgan", "general-detail"),
    CuratedUpscaler("4x-realesrgan-x4plus", "general-photographic"),
    CuratedUpscaler("2x-AnimeSharpV3", "anime-detail"),
    CuratedUpscaler("2x-realesrgan-x2plus", "general-two-times"),
)


__all__ = ["CURATED_UPSCALERS", "CuratedUpscaler"]
