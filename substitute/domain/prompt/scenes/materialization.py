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

"""Materialize universal and scene-local prompt text for generation."""

from __future__ import annotations


def materialize_scene_prompt(
    *,
    universal_text: str,
    scene_text: str,
) -> str:
    """Join universal and scene-local prompt text for one generation field."""

    universal = universal_text.strip()
    scene = scene_text.strip()
    if universal and scene:
        return f"{universal}\n\n{scene}"
    if universal:
        return universal
    return scene


__all__ = ["materialize_scene_prompt"]
