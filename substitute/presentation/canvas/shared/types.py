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

"""Define presentation-layer canvas metadata protocols."""

from __future__ import annotations

from typing import Protocol


class OutputImageMeta(Protocol):
    """Describe output-image metadata consumed by canvas presentation widgets."""

    workflow_name: str
    cube_name: str
    image_number: int
    suffix: str
    path: str
    source_key: str
    source_label: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    scene_run_id: str
    scene_key: str
    scene_title: str
    scene_order: int | None
    scene_count: int | None
    width: int | None
    height: int | None
    cube_execution_duration_ms: float | None


__all__ = [
    "OutputImageMeta",
]
