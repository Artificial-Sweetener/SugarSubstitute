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

"""Represent image artifacts exposed through Comfy's view endpoint."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComfyImageArtifact:
    """Describe one image artifact referenced by a Comfy event."""

    filename: str
    subfolder: str
    type: str
    media_kind: str = "image"
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None


__all__ = ["ComfyImageArtifact"]
