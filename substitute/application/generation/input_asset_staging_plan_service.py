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
from substitute.application.workflows.input_asset_field_service import (
    AuthoredInputAssetField,
    InputAssetFieldService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.workflow import (
    InputAssetCardinality,
    InputAssetRole,
    WorkflowState,
)


@dataclass(frozen=True, slots=True)
class InputAssetStagingTarget:
    """Identify one executable upload field and its authored graph identity."""

    executable_node_id: str
    section_key: str
    node_name: str
    field_key: str
    role: InputAssetRole
    cardinality: InputAssetCardinality = InputAssetCardinality.SCALAR


class InputAssetStagingPlanService:
    """Map semantic authored upload endpoints onto one compiled API prompt."""

    def __init__(
        self,
        graph_section_service: WorkflowGraphSectionService,
        input_asset_field_service: InputAssetFieldService | None = None,
        *,
        node_definition_service: WorkflowNodeDefinitionService | None = None,
    ) -> None:
        """Capture asset-field discovery and graph projection authorities."""

        self._graph_section_service = graph_section_service
        self._input_asset_field_service = (
            input_asset_field_service
            or InputAssetFieldService(node_definition_service=node_definition_service)
        )

    def targets_for_prompt(
        self,
        workflow: WorkflowState,
        prompt: Mapping[str, object],
    ) -> tuple[InputAssetStagingTarget, ...]:
        """Return executable upload targets that correspond to authored endpoints."""

        authored: dict[tuple[str, str], list[AuthoredInputAssetField]] = {}
        for section_key in self._graph_section_service.section_keys(workflow):
            graph = self._graph_section_service.graph(workflow, section_key)
            if graph is None:
                continue
            for asset_field in self._input_asset_field_service.fields_for_graph(graph):
                authored.setdefault(
                    (section_key, asset_field.node_name),
                    [],
                ).append(asset_field)

        compiled_fields: dict[str, list[AuthoredInputAssetField]] = {}
        for field in self._input_asset_field_service.fields_for_graph(
            {"nodes": prompt}
        ):
            compiled_fields.setdefault(field.node_name, []).append(field)
        targets: list[InputAssetStagingTarget] = []
        for raw_node_id, raw_node in prompt.items():
            if not isinstance(raw_node, Mapping):
                continue
            node_id = str(raw_node_id)
            identity = _authored_identity(workflow, node_id, raw_node)
            selected_fields = authored.get(identity)
            if selected_fields is None:
                selected_fields = compiled_fields.get(node_id)
            if selected_fields is None:
                continue
            targets.extend(
                InputAssetStagingTarget(
                    executable_node_id=node_id,
                    section_key=identity[0],
                    node_name=identity[1],
                    field_key=asset_field.field_key,
                    role=asset_field.role,
                    cardinality=asset_field.cardinality,
                )
                for asset_field in selected_fields
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
