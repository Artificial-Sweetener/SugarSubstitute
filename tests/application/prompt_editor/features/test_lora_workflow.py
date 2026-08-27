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

"""Test workflow-aware LoRA feature resolution."""

from __future__ import annotations

from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptFeatureDisabledReason,
)
from tests.application.prompt_editor.features.support import (
    profile_service,
    workflow_context,
)


def test_featureprofile_service_maps_lora_prompt_syntaxes_when_supported() -> None:
    """LoRA prompt_syntaxes should enable split features for supported prompt paths."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "encode": {
                    "class_type": "PCLazyTextEncode",
                    "inputs": {"text": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)
    assert profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS)
    assert not profile.supports(PromptEditorFeature.EMPHASIS)


def test_featureprofile_service_keeps_lora_syntax_withoutworkflow_context() -> None:
    """LoRA syntax should render even when runtime LoRA actions are unavailable."""

    service = profile_service()

    profile = service.build_profile(
        field_style={},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="positive_prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert not profile.supports(PromptEditorFeature.LORA_PICKER)
    assert not profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS)
    assert (
        profile.decision_for(PromptEditorFeature.LORA_PICKER).disabled_reason
        is PromptFeatureDisabledReason.MISSING_SERVICE
    )


def test_featureprofile_service_keeps_lora_syntax_for_vanilla_clip_encode() -> None:
    """Plain CLIP encoders should render syntax without runtime LoRA actions."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "encode": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert not profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_enables_lora_syntax_for_prompt_control_wrapper() -> (
    None
):
    """Subgraph wrappers should prove LoRA support from their body node classes."""

    service = profile_service()
    wrapper_class = "94f725d5-39bf-4060-be68-f573214a2055"

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "schedule": {
                    "class_type": wrapper_class,
                    "inputs": {"positive_prompt": ["prompt", 0]},
                },
            },
            subgraphs=(
                {
                    "id": wrapper_class,
                    "nodes": ({"type": "PCLazyTextEncode"},),
                },
            ),
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_enables_lora_for_simple_syrup_positive_prompt() -> None:
    """SimpleSyrup scheduling nodes should support positive prompt LoRA scheduling."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "schedule": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {"positive_prompt": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_enables_lora_for_simple_syrup_negative_prompt() -> None:
    """SimpleSyrup scheduling nodes should support negative prompt LoRA scheduling."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "schedule": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {"negative_prompt": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_blocks_simple_syrup_non_prompt_inputs() -> None:
    """SimpleSyrup non-prompt inputs should not enable runtime LoRA actions."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "schedule": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {"encode_style": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert not profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_enables_lora_for_simple_syrup_direct_field() -> None:
    """Direct SimpleSyrup prompt fields should advertise their own LoRA support."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {
                "schedule": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {
                        "positive_prompt": "cat",
                        "negative_prompt": "bad anatomy",
                    },
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="schedule",
        prompt_field_key="positive_prompt",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)


def test_featureprofile_service_uses_restored_original_cube_graph() -> None:
    """Restored cube definitions should prove support when buffers are patch-like."""

    service = profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=workflow_context(
            {},
            original_cube={
                "nodes": {
                    "schedule": {
                        "class_type": (
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        "inputs": {
                            "positive_prompt": "cat",
                            "negative_prompt": "bad anatomy",
                        },
                    },
                },
            },
        ),
        cube_alias="Cube",
        prompt_node_name="schedule",
        prompt_field_key="positive_prompt",
    )

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert profile.supports(PromptEditorFeature.LORA_PICKER)
