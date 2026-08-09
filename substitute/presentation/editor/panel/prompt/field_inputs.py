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

"""Prepare immutable prompt-field construction inputs for node-card projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.node_behavior import FieldPresentation, ResolvedFieldSpec
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    PromptConditioningContextService,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.presentation.editor.panel.panel_workflow_projection import (
    workflow_for_panel,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
)


class PromptFieldInputsHost(Protocol):
    """Describe panel services needed to prepare one prompt field snapshot."""

    node_definition_gateway: NodeDefinitionGateway | None

    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
        """Return a resolver bound to one prompt field."""

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return feature and syntax profiles for one prompt field."""


@dataclass(frozen=True, slots=True)
class NodeCardPromptFieldInputs:
    """Carry all immutable context prepared for one prompt-editor field."""

    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]] | None = (
        None
    )
    prompt_field_profile: PanelPromptFieldProfileDecision | None = None
    conditioning_context: PromptConditioningContext | None = None


def build_node_card_prompt_field_inputs(
    host: PromptFieldInputsHost,
    *,
    node_name: str,
    field_specs: Mapping[str, ResolvedFieldSpec],
    alias: str | None,
    conditioning_contexts: PromptConditioningContextService | None = None,
) -> dict[str, NodeCardPromptFieldInputs]:
    """Prepare all prompt-specific construction state before node-card assembly."""

    context_service = conditioning_contexts or PromptConditioningContextService(
        RegionalPromptTopologyService(
            input_endpoints=InputAssetEndpointService(
                WorkflowNodeDefinitionService(host.node_definition_gateway)
            )
        )
    )
    workflow = workflow_for_panel(host)
    prompt_inputs: dict[str, NodeCardPromptFieldInputs] = {}
    for field_key, field_spec in field_specs.items():
        field_behavior = field_spec.field_behavior
        if field_behavior.presentation != FieldPresentation.PROMPT_BOX:
            continue
        prompt_behavior = field_behavior.prompt
        conditioning_context = (
            context_service.resolve(
                workflow,
                PromptEndpoint(
                    cube_alias=alias or "",
                    role=prompt_behavior.role,
                    node_name=node_name,
                    field_key=field_key,
                    linkable=prompt_behavior.linkable,
                ),
            )
            if prompt_behavior is not None
            else None
        )
        prompt_inputs[field_key] = NodeCardPromptFieldInputs(
            scheduled_lora_resolver=host.scheduled_lora_resolver_for_prompt(
                alias,
                node_name,
                field_key,
            ),
            prompt_field_profile=host.prompt_field_profile_for_prompt(
                alias,
                node_name,
                field_key,
                field_behavior.style,
            ),
            conditioning_context=conditioning_context,
        )
    return prompt_inputs


__all__ = ["NodeCardPromptFieldInputs", "build_node_card_prompt_field_inputs"]
