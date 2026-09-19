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

"""Materialize Substitute convenience values into detached Cube documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Protocol

from substitute.domain.common import JsonObject
from substitute.domain.cubes import project_editable_cube_document


class CubeStateLike(Protocol):
    """Describe editable Cube state used during generation materialization."""

    @property
    def cube_id(self) -> str:
        """Return the canonical Cube id."""

    @property
    def version(self) -> str:
        """Return the canonical Cube version."""

    @property
    def alias(self) -> str:
        """Return the workflow instance alias."""

    @property
    def buffer(self) -> JsonObject:
        """Return the editable implementation buffer."""

    @property
    def ui(self) -> dict[str, object] | None:
        """Return runtime UI metadata when available."""

    @property
    def bypassed(self) -> bool:
        """Return whether this Cube is bypassed."""


class CubeWorkflowLike(Protocol):
    """Describe ordered Cube state without depending on presentation owners."""

    @property
    def stack_order(self) -> Sequence[str]:
        """Return aliases in stack order."""

    @property
    def cubes(self) -> Mapping[str, CubeStateLike]:
        """Return Cube state by alias."""


class CubeConvenienceMaterializer:
    """Resolve transient Substitute conveniences into executable Cube buffers."""

    def materialize_buffers(
        self,
        workflow: CubeWorkflowLike,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
    ) -> dict[str, JsonObject]:
        """Return detached buffers with per-run prompt preprocessing resolved."""

        ordered = [
            workflow.cubes[alias]
            for alias in workflow.stack_order
            if alias in workflow.cubes
        ]
        buffers = {cube.alias: deepcopy(dict(cube.buffer)) for cube in ordered}
        self._materialize_prompt_overrides(buffers, prompt_field_overrides or {})
        return buffers

    def cube_document(
        self,
        cube: CubeStateLike,
        buffer: Mapping[str, object],
    ) -> JsonObject:
        """Build a compiler-ready canonical Cube document from editor state."""

        canonical = cube.ui.get("canonical_cube") if isinstance(cube.ui, dict) else None
        return project_editable_cube_document(
            cube_id=cube.cube_id,
            version=cube.version,
            buffer=buffer,
            canonical_metadata=canonical if isinstance(canonical, Mapping) else None,
        )

    @staticmethod
    def _materialize_prompt_overrides(
        buffers: Mapping[str, JsonObject],
        overrides: Mapping[tuple[str, str, str], object],
    ) -> None:
        """Apply scene and wildcard values before linked followers are resolved."""

        for (alias, node_name, field_key), value in overrides.items():
            buffer = buffers.get(alias)
            if buffer is None:
                continue
            node = _nodes(buffer, alias).get(node_name)
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if isinstance(inputs, dict):
                inputs[field_key] = deepcopy(value)


def _nodes(buffer: Mapping[str, object], label: str) -> dict[str, object]:
    """Return one mutable materialized node map."""

    nodes = buffer.get("nodes")
    if not isinstance(nodes, dict):
        raise ValueError(f"Cube {label!r} has invalid nodes.")
    return nodes


__all__ = [
    "CubeConvenienceMaterializer",
    "CubeStateLike",
    "CubeWorkflowLike",
]
