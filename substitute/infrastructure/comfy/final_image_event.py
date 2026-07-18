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

"""Define the neutral final-image event consumed by output persistence."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact


@dataclass(frozen=True, slots=True)
class FinalImageSource:
    """Identify one visual source independently from its transport event."""

    node_id: str
    source_key: str
    source_label: str
    cube_alias: str


@dataclass(frozen=True, slots=True)
class FinalImageScene:
    """Carry optional scene routing facts for one final image event."""

    run_id: str | None = None
    key: str | None = None
    title: str | None = None
    order: int | None = None
    count: int | None = None


@dataclass(frozen=True, slots=True)
class FinalImageEvent:
    """Carry validated Comfy image artifacts into shared final-output handling."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    workflow_payload: dict[str, object]
    source: FinalImageSource
    artifacts: tuple[ComfyImageArtifact, ...]
    list_index: int
    scene: FinalImageScene = FinalImageScene()


__all__ = ["FinalImageEvent", "FinalImageScene", "FinalImageSource"]
