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

"""Define cube-owned runtime state consumed by node behavior resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from substitute.domain.comfy_workflow import NodeActivationStorage
from substitute.domain.node_behavior import PackageBehaviorPatch


class CubeStateProtocol(Protocol):
    """Describe the cube-state shape consumed by node behavior resolution."""

    buffer: dict[str, object]
    ui: dict[str, object]
    dirty: bool

    @property
    def activation_storage(self) -> NodeActivationStorage | str:
        """Return the graph's authoritative node activation storage mode."""

    @property
    def uses_node_titles_as_card_labels(self) -> bool:
        """Return whether source node titles own visible card labels."""


@dataclass
class NodeBehaviorRuntimeState:
    """Store per-cube runtime behavior state outside serialized recipe buffers."""

    node_instance_patch: PackageBehaviorPatch = field(
        default_factory=PackageBehaviorPatch
    )


__all__ = ["CubeStateProtocol", "NodeBehaviorRuntimeState"]
