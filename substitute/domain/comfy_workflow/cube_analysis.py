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

"""Model SugarCubes-owned canonical workflow analysis results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.common import JsonObject


class CubeGraphEdgeOrigin(StrEnum):
    """Identify whether a Cube edge is persisted or proximity-derived."""

    EXPLICIT = "explicit"
    PROXIMITY = "proximity"


@dataclass(frozen=True, slots=True)
class AnalyzedCubeInstance:
    """Identify one real Cube node in the canonical Comfy graph."""

    instance_id: str
    node_id: str
    definition_id: str
    cube_id: str
    cube_version: str
    alias: str
    execution_mode: int


@dataclass(frozen=True, slots=True)
class AnalyzedCubeEdge:
    """Describe one effective Cube boundary connection."""

    source_instance_id: str
    source_binding: str
    target_instance_id: str
    target_binding: str
    origin: CubeGraphEdgeOrigin


@dataclass(frozen=True, slots=True)
class AnalyzedCubeSegment:
    """Describe one stack-visible Cube segment and its mutation boundary."""

    instance_ids: tuple[str, ...]
    reorderable: bool
    boundary_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalCubeGraphAnalysis:
    """Carry a complete immutable projection returned by SugarCubes."""

    workflow_semantic_hash: str
    instances: tuple[AnalyzedCubeInstance, ...]
    edges: tuple[AnalyzedCubeEdge, ...]
    proximity_edges: tuple[AnalyzedCubeEdge, ...]
    segments: tuple[AnalyzedCubeSegment, ...]
    workflow: JsonObject


__all__ = [
    "AnalyzedCubeEdge",
    "AnalyzedCubeInstance",
    "AnalyzedCubeSegment",
    "CanonicalCubeGraphAnalysis",
    "CubeGraphEdgeOrigin",
]
