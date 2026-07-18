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

"""Own section-neutral access to mutable workflow graph buffers."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjectionService,
)
from substitute.domain.workflow import WorkflowState


@dataclass(frozen=True, slots=True)
class WorkflowGraphFieldMutation:
    """Describe one graph input mutation and its prior value."""

    changed: bool
    old_value: object = None


class WorkflowGraphSectionService:
    """Resolve and mutate cube or direct graph sections through one authority."""

    def __init__(
        self,
        editor_projection_service: WorkflowEditorProjectionService | None = None,
    ) -> None:
        """Capture the workflow document projection authority."""

        self._editor_projection_service = (
            editor_projection_service or WorkflowEditorProjectionService()
        )

    def section_state(self, workflow: WorkflowState, section_key: str) -> object | None:
        """Return one projected graph state by its stable section key."""

        return self._editor_projection_service.project(workflow).states.get(section_key)

    def section_keys(self, workflow: WorkflowState) -> tuple[str, ...]:
        """Return graph section keys in the shared editor projection order."""

        return self._editor_projection_service.project(workflow).order

    def graph(
        self, workflow: WorkflowState, section_key: str
    ) -> dict[str, object] | None:
        """Return one mutable projected graph buffer when its shape is valid."""

        state = self.section_state(workflow, section_key)
        graph = getattr(state, "buffer", None)
        return graph if isinstance(graph, dict) else None

    def input_value(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
    ) -> object | None:
        """Return one authored graph input value when the section path exists."""

        inputs = self._node_inputs(
            workflow,
            section_key=section_key,
            node_name=node_name,
        )
        return inputs.get(field_key) if inputs is not None else None

    def set_input_value(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
        value: object,
    ) -> WorkflowGraphFieldMutation:
        """Mutate one graph input and mark its owning state dirty."""

        inputs = self._node_inputs(
            workflow,
            section_key=section_key,
            node_name=node_name,
        )
        if inputs is None:
            return WorkflowGraphFieldMutation(changed=False)
        old_value = inputs.get(field_key)
        inputs[field_key] = value
        state = self.section_state(workflow, section_key)
        if state is not None and hasattr(state, "dirty"):
            setattr(state, "dirty", True)
        return WorkflowGraphFieldMutation(changed=True, old_value=old_value)

    def _node_inputs(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> dict[str, object] | None:
        """Return one node's mutable input mapping when structurally valid."""

        graph = self.graph(workflow, section_key)
        if graph is None:
            return None
        nodes = graph.get("nodes")
        if not isinstance(nodes, dict):
            return None
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            return None
        inputs = node.get("inputs")
        return inputs if isinstance(inputs, dict) else None


__all__ = ["WorkflowGraphFieldMutation", "WorkflowGraphSectionService"]
