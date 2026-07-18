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

"""Project authored input upload endpoints onto executable Comfy nodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import InputAssetRole, WorkflowState


@dataclass(frozen=True, slots=True)
class InputAssetStagingTarget:
    """Identify one executable upload field and its authored graph identity."""

    executable_node_id: str
    section_key: str
    node_name: str
    field_key: str
    role: InputAssetRole


class InputAssetStagingPlanService:
    """Map semantic authored upload endpoints onto one compiled API prompt."""

    def __init__(
        self,
        input_asset_endpoint_service: InputAssetEndpointService,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Capture shared endpoint discovery and graph projection authorities."""

        self._input_asset_endpoint_service = input_asset_endpoint_service
        self._graph_section_service = graph_section_service

    def targets_for_prompt(
        self,
        workflow: WorkflowState,
        prompt: Mapping[str, object],
    ) -> tuple[InputAssetStagingTarget, ...]:
        """Return executable upload targets that correspond to authored endpoints."""

        authored: dict[tuple[str, str], tuple[str, InputAssetRole]] = {}
        for section_key in self._graph_section_service.section_keys(workflow):
            graph = self._graph_section_service.graph(workflow, section_key)
            if graph is None:
                continue
            index = self._input_asset_endpoint_service.build_index(section_key, graph)
            for endpoint in index.endpoints:
                authored[(section_key, endpoint.node_name)] = (
                    endpoint.field_key,
                    endpoint.role,
                )

        targets: list[InputAssetStagingTarget] = []
        for raw_node_id, raw_node in prompt.items():
            if not isinstance(raw_node, Mapping):
                continue
            node_id = str(raw_node_id)
            identity = _authored_identity(workflow, node_id, raw_node)
            authored_endpoint = authored.get(identity)
            if authored_endpoint is None:
                continue
            field_key, role = authored_endpoint
            targets.append(
                InputAssetStagingTarget(
                    executable_node_id=node_id,
                    section_key=identity[0],
                    node_name=identity[1],
                    field_key=field_key,
                    role=role,
                )
            )
        return tuple(targets)


def _authored_identity(
    workflow: WorkflowState,
    node_id: str,
    node_data: Mapping[str, object],
) -> tuple[str, str]:
    """Resolve direct node IDs or compiled cube metadata to authored identity."""

    if workflow.is_direct_workflow:
        return (DIRECT_WORKFLOW_SECTION_KEY, node_id)
    meta = node_data.get("_meta")
    title = meta.get("title") if isinstance(meta, Mapping) else None
    if isinstance(title, str):
        section_key, separator, node_name = title.partition(".")
        if section_key and separator and node_name:
            return (section_key, node_name)
    return ("", node_id)


__all__ = ["InputAssetStagingPlanService", "InputAssetStagingTarget"]
