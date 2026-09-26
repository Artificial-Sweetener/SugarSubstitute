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

"""Assess persisted workflow nodes against authoritative live Comfy metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.ports import NodeDefinitionGateway, NodeDefinitionHydrator
from substitute.domain.comfy_workflow.node_inventory import (
    WorkflowNodeInventoryItem,
    workflow_node_inventory,
)


@dataclass(frozen=True, slots=True)
class WorkflowNodeDefinitionAssessment:
    """Partition saved workflow nodes by observed live-definition availability."""

    available: tuple[WorkflowNodeInventoryItem, ...]
    missing: tuple[WorkflowNodeInventoryItem, ...]

    @property
    def missing_class_types(self) -> tuple[str, ...]:
        """Return distinct missing class names in stable order."""

        return tuple(sorted({node.class_type for node in self.missing}))


class WorkflowNodeDefinitionAssessmentUnavailable(RuntimeError):
    """Report that authoritative live metadata cannot currently be assessed."""


class WorkflowNodeDefinitionAssessmentService:
    """Hydrate and classify every executable node saved in one workflow."""

    def __init__(self, gateway: NodeDefinitionGateway) -> None:
        """Store the live metadata gateway and require its hydration contract."""

        self._gateway = gateway

    def assess(
        self,
        workflow: Mapping[str, object],
    ) -> WorkflowNodeDefinitionAssessment:
        """Return complete node-level availability after one bounded hydration pass."""

        inventory = workflow_node_inventory(workflow)
        if not inventory:
            return WorkflowNodeDefinitionAssessment(available=(), missing=())
        if not isinstance(self._gateway, NodeDefinitionHydrator):
            raise WorkflowNodeDefinitionAssessmentUnavailable(
                "Live Comfy node definitions cannot be refreshed in this session."
            )
        class_types = tuple(sorted({node.class_type for node in inventory}))
        hydration = self._gateway.ensure_node_definitions(class_types)
        unavailable = set(hydration.unavailable)
        available: list[WorkflowNodeInventoryItem] = []
        missing: list[WorkflowNodeInventoryItem] = []
        for node in inventory:
            payload = self._gateway.get_node_definition(node.class_type)
            definition = payload.get(node.class_type)
            target = (
                missing
                if node.class_type in unavailable or not isinstance(definition, Mapping)
                else available
            )
            target.append(node)
        return WorkflowNodeDefinitionAssessment(
            available=tuple(available),
            missing=tuple(missing),
        )


__all__ = [
    "WorkflowNodeDefinitionAssessment",
    "WorkflowNodeDefinitionAssessmentService",
    "WorkflowNodeDefinitionAssessmentUnavailable",
]
