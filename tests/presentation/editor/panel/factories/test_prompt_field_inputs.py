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

"""Contract tests for prompt-field construction context assembly."""

from __future__ import annotations

from types import SimpleNamespace
from collections.abc import Callable, Mapping
from typing import cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.application.prompt_editor.conditioning import PromptConditioningMode
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.node_behavior.models import (
    FieldBehavior,
    FieldPresentation,
    PromptFieldBehavior,
    PromptRole,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.editor.panel.prompt.field_inputs import (
    PromptFieldInputsHost,
    build_node_card_prompt_field_inputs,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
    PanelPromptProfilePolicy,
)


class _PromptFieldHost:
    """Provide prompt preparation methods and exact workflow ownership."""

    def __init__(self, workflow: WorkflowState) -> None:
        """Attach this host to one workflow session entry."""

        self.node_definition_gateway = None
        self.mainwindow = SimpleNamespace(
            editor_panels={"workflow": self},
            workflow_session_service=SimpleNamespace(
                workflows={"workflow": workflow},
            ),
        )

    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
        """Return no scheduled LoRA resolver for this construction test."""

        _ = (cube_alias, prompt_node_name, prompt_field_key)
        return None

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return a complete profile decision for this construction test."""

        _ = (cube_alias, prompt_node_name, prompt_field_key)
        return PanelPromptProfilePolicy().prepare_prompt_field_profile(
            field_style=field_style
        )


def test_prompt_field_inputs_capture_exact_graph_conditioning_context() -> None:
    """Node-card construction should resolve regional mode before widget creation."""

    workflow = _workflow()
    host = cast(PromptFieldInputsHost, _PromptFieldHost(workflow))
    field_spec = ResolvedFieldSpec(
        cube_alias="Region",
        node_name="positive",
        class_type="PrimitiveStringMultiline",
        field_key="value",
        field_type="STRING",
        constraints={},
        meta_info={},
        field_info=None,
        value="global\n[SEP]\nregion",
        field_behavior=FieldBehavior(
            field_key="value",
            presentation=FieldPresentation.PROMPT_BOX,
            prompt=PromptFieldBehavior(role=PromptRole.POSITIVE),
        ),
    )

    inputs = build_node_card_prompt_field_inputs(
        host,
        node_name="positive",
        field_specs={"value": field_spec},
        alias="Region",
    )

    context = inputs["value"].conditioning_context
    assert context is not None
    assert context.mode is PromptConditioningMode.REGIONAL
    assert context.endpoint.node_name == "positive"
    assert context.endpoint.field_key == "value"


def _workflow() -> WorkflowState:
    """Build one materialized ordered-mask graph for field-input resolution."""

    workflow = WorkflowState()
    workflow.cubes["Region"] = CubeState(
        cube_id="Prompt by Region.cube",
        version="3.2.0",
        alias="Region",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "masks": {"class_type": "MaskBatch", "inputs": {}},
                "positive": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": "global\n[SEP]\nregion"},
                },
                "encode": {
                    "class_type": "SchedulePrompts",
                    "inputs": {"positive": ["positive", 0]},
                },
                "sampler": {
                    "class_type": "RegionalSampler",
                    "inputs": {
                        "masks": ["masks", 0],
                        "positive": ["encode", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Region")
    workflow.canvas.ensure_regional_mask_collection(("Region", "masks"))
    return workflow
