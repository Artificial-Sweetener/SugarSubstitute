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

"""Expose canonical SugarCube document validation and materialization helpers."""

from __future__ import annotations

from substitute.domain.cubes.canonical_document import (
    CanonicalCubeDocument,
    CanonicalCubeError,
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)
from substitute.domain.cubes.subgraph_wrappers import (
    SubgraphWrapperDefinitionIndex,
    UUID_CLASS_PATTERN,
    is_subgraph_wrapper_class_type,
)

__all__ = [
    "CanonicalCubeDocument",
    "CanonicalCubeError",
    "SubgraphWrapperDefinitionIndex",
    "UUID_CLASS_PATTERN",
    "is_subgraph_wrapper_class_type",
    "materialize_cube_runtime_graph",
    "validate_canonical_cube_document",
]
