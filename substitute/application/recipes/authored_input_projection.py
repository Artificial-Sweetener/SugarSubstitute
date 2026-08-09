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

"""Project canonical surface-owned cube values into recipe serialization inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from substitute.domain.common import JsonValue
from substitute.domain.cubes.authoring_contract import (
    CubeAuthoringContract,
    CubeInputField,
)
from substitute.domain.recipes.authored_inputs import AuthoredRecipeInput


class RecipeAuthoredInputProjector:
    """Exclude structural graph values through the cube's explicit authoring contract."""

    def project(
        self,
        *,
        buffers: Mapping[str, Mapping[str, JsonValue]],
        ordered_aliases: Iterable[str],
    ) -> dict[str, tuple[AuthoredRecipeInput, ...]]:
        """Return authored inputs in stable graph order for every recipe cube."""

        projected: dict[str, tuple[AuthoredRecipeInput, ...]] = {}
        for alias in ordered_aliases:
            buffer = buffers[alias]
            contract = CubeAuthoringContract.from_graph(buffer)
            authored_fields = frozenset(contract.authored_fields)
            assignments: list[AuthoredRecipeInput] = []
            nodes = buffer.get("nodes")
            if isinstance(nodes, Mapping):
                for node_key, node in nodes.items():
                    if not isinstance(node_key, str) or not isinstance(node, Mapping):
                        continue
                    inputs = node.get("inputs")
                    if not isinstance(inputs, Mapping):
                        continue
                    for input_key, value in inputs.items():
                        if not isinstance(input_key, str):
                            continue
                        field = CubeInputField(node_key=node_key, input_key=input_key)
                        if field not in authored_fields:
                            continue
                        assignments.append(
                            AuthoredRecipeInput(
                                node_key=node_key,
                                input_key=input_key,
                                value=value,
                            )
                        )
            projected[alias] = tuple(assignments)
        return projected


__all__ = ["RecipeAuthoredInputProjector"]
