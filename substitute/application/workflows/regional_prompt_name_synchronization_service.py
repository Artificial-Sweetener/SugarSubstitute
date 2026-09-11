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

"""Synchronize authored regional names across related canonical prompt values."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.editing.region_name_identity import (
    PromptRegionNameIdentityService,
)
from substitute.application.workflows.regional_prompt_name_models import (
    RegionalPromptNameSynchronization,
    RegionalPromptSourceUpdate,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopology,
    RegionalPromptTopologyService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger(
    "application.workflows.regional_prompt_name_synchronization_service"
)


@dataclass(frozen=True, slots=True)
class _PromptEndpoint:
    """Bind one topology prompt node to its canonical editable value."""

    node_name: str
    field_key: str
    source_text: str


class RegionalPromptNameSynchronizationService:
    """Keep ordinal SEP names identical in related canonical prompt node values."""

    def __init__(
        self,
        *,
        graph_sections: WorkflowGraphSectionService | None = None,
        topology: RegionalPromptTopologyService | None = None,
        identity: PromptRegionNameIdentityService | None = None,
    ) -> None:
        """Store canonical graph, topology, parsing, and SEP syntax authorities."""

        self._graph_sections = graph_sections or WorkflowGraphSectionService()
        self._topology = topology or RegionalPromptTopologyService(self._graph_sections)
        self._identity = identity or PromptRegionNameIdentityService()

    def normalize_for_prompt(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        prompt_node_name: str,
    ) -> RegionalPromptNameSynchronization:
        """Normalize existing related SEP names in stable topology prompt order."""

        topology = self._topology_for_prompt(
            workflow,
            section_key,
            prompt_node_name,
        )
        return self._normalize(workflow, topology)

    def normalize_for_mask(
        self,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
    ) -> RegionalPromptNameSynchronization:
        """Normalize SEP names related to one ordered mask endpoint."""

        return self._normalize(
            workflow,
            self._topology.topology_for_mask(workflow, association_key),
        )

    def synchronize_prompt_edit(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        prompt_node_name: str,
        previous_source_text: str,
        current_source_text: str,
    ) -> RegionalPromptNameSynchronization:
        """Propagate SEP-name edits while preserving every prompt's distinct content."""

        topology = self._topology_for_prompt(
            workflow,
            section_key,
            prompt_node_name,
        )
        if topology is None:
            return RegionalPromptNameSynchronization(section_key=section_key)
        endpoints = list(self._endpoints(workflow, topology))
        source_index = next(
            (
                index
                for index, endpoint in enumerate(endpoints)
                if endpoint.node_name == prompt_node_name
            ),
            None,
        )
        if source_index is None:
            return RegionalPromptNameSynchronization(section_key=section_key)
        source_endpoint = endpoints[source_index]
        endpoints[source_index] = _PromptEndpoint(
            node_name=source_endpoint.node_name,
            field_key=source_endpoint.field_key,
            source_text=current_source_text,
        )
        explicit_names = self._identity.changed_names(
            previous_source_text,
            current_source_text,
        )
        return self._apply_canonical_names(
            workflow,
            topology,
            tuple(endpoints),
            explicit_names=explicit_names,
        )

    def _normalize(
        self,
        workflow: WorkflowState,
        topology: RegionalPromptTopology | None,
    ) -> RegionalPromptNameSynchronization:
        """Apply deterministic first-authored names when no edit claims precedence."""

        if topology is None:
            return RegionalPromptNameSynchronization(section_key="")
        return self._apply_canonical_names(
            workflow,
            topology,
            self._endpoints(workflow, topology),
            explicit_names={},
        )

    def _apply_canonical_names(
        self,
        workflow: WorkflowState,
        topology: RegionalPromptTopology,
        endpoints: tuple[_PromptEndpoint, ...],
        *,
        explicit_names: dict[int, str],
    ) -> RegionalPromptNameSynchronization:
        """Resolve shared names and atomically commit changed prompt node values."""

        section_key = topology.association_key[0]
        canonical_names = self._identity.first_authored_names(
            tuple(endpoint.source_text for endpoint in endpoints)
        )
        canonical_names.update(explicit_names)
        updates: list[RegionalPromptSourceUpdate] = []
        for endpoint in endpoints:
            source_text, prepared = self._identity.apply_names(
                endpoint.source_text,
                canonical_names,
            )
            if not prepared:
                continue
            updates.append(
                RegionalPromptSourceUpdate(
                    node_name=endpoint.node_name,
                    field_key=endpoint.field_key,
                    source_text=source_text,
                    replacements=prepared,
                )
            )
        if not updates:
            return RegionalPromptNameSynchronization(section_key=section_key)
        mutation = self._graph_sections.set_input_values_atomic(
            workflow,
            section_key=section_key,
            values=tuple(
                (update.node_name, update.field_key, update.source_text)
                for update in updates
            ),
        )
        if not mutation.changed:
            return RegionalPromptNameSynchronization(section_key=section_key)
        log_info(
            _LOGGER,
            "Synchronized regional prompt names",
            section_key=section_key,
            source_count=len(endpoints),
            updated_source_count=len(updates),
            synchronized_region_count=len(canonical_names),
        )
        return RegionalPromptNameSynchronization(
            section_key=section_key,
            updates=tuple(updates),
        )

    def _topology_for_prompt(
        self,
        workflow: WorkflowState,
        section_key: str,
        prompt_node_name: str,
    ) -> RegionalPromptTopology | None:
        """Resolve prompt topology before or after ordered masks are materialized."""

        graph = self._graph_sections.graph(workflow, section_key)
        if graph is None:
            return None
        raw_nodes = graph.get("nodes")
        node = raw_nodes.get(prompt_node_name) if isinstance(raw_nodes, dict) else None
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            return None
        field_key = next(
            (
                candidate
                for candidate in ("value", "text")
                if isinstance(inputs.get(candidate), str)
            ),
            None,
        )
        if field_key is None:
            return None
        return self._topology.topology_for_prompt_endpoint(
            workflow,
            section_key,
            prompt_node_name,
            field_key,
        )

    def _endpoints(
        self,
        workflow: WorkflowState,
        topology: RegionalPromptTopology,
    ) -> tuple[_PromptEndpoint, ...]:
        """Return editable primitive prompt values in stable topology order."""

        graph = self._graph_sections.graph(workflow, topology.association_key[0])
        if graph is None:
            return ()
        raw_nodes = graph.get("nodes")
        if not isinstance(raw_nodes, dict):
            return ()
        endpoints: list[_PromptEndpoint] = []
        for node_name in topology.prompt_node_names:
            node = raw_nodes.get(node_name)
            if not isinstance(node, dict) or node.get("class_type") != (
                "PrimitiveStringMultiline"
            ):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for field_key in ("value", "text"):
                source_text = inputs.get(field_key)
                if isinstance(source_text, str):
                    endpoints.append(_PromptEndpoint(node_name, field_key, source_text))
                    break
        return tuple(endpoints)


__all__ = [
    "RegionalPromptNameSynchronizationService",
]
