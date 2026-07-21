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

"""Tests for resolved prompt editor feature profiles."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from substitute.application.prompt_editor import (
    PromptEditorPreferenceService,
    PromptFeatureProfileService,
    WorkflowPromptContext,
)
from substitute.domain.prompt import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorFeature,
    PromptEditorPreferences,
    PromptFeatureDisabledReason,
)


def test_feature_profile_service_disables_user_disabled_feature() -> None:
    """User preferences should suppress otherwise allowed features."""

    service = _profile_service(
        preferences=PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={PromptEditorFeature.EMPHASIS: False},
        )
    )

    profile = service.build_profile(
        field_style={},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert not profile.supports(PromptEditorFeature.EMPHASIS)
    assert (
        profile.decision_for(PromptEditorFeature.EMPHASIS).disabled_reason
        is PromptFeatureDisabledReason.USER_DISABLED
    )


def test_library_profile_respects_preferences_without_workflow_lora_gating() -> None:
    """Library editors should enable preferred LoRA features without a workflow."""

    preferences = {feature: True for feature in PromptEditorFeature}
    preferences[PromptEditorFeature.SPELLCHECK] = False
    service = _profile_service(
        preferences=PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features=preferences,
        )
    )

    profile = service.build_library_profile()

    assert profile.supports(PromptEditorFeature.LORA_SYNTAX) is True
    assert profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE) is True
    assert profile.supports(PromptEditorFeature.LORA_PICKER) is True
    assert profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS) is True
    assert profile.supports(PromptEditorFeature.SPELLCHECK) is False


def test_feature_profile_service_disables_user_disabled_ghost_text() -> None:
    """User preferences should suppress autocomplete ghost text independently."""

    service = _profile_service(
        preferences=PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={
                PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT: False,
            },
        )
    )

    profile = service.build_profile(
        field_style={},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert not profile.supports(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)
    assert (
        profile.decision_for(
            PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT
        ).disabled_reason
        is PromptFeatureDisabledReason.USER_DISABLED
    )


def test_feature_profile_service_maps_legacy_prompt_syntaxes() -> None:
    """Legacy prompt_syntaxes style should map into feature ids."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["wildcard"]},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert profile.supports(PromptEditorFeature.WILDCARD_SYNTAX)
    assert profile.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE)
    assert profile.supports(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)
    assert profile.supports(PromptEditorFeature.SEGMENT_REORDER)
    assert profile.supports(PromptEditorFeature.SPELLCHECK)
    assert not profile.supports(PromptEditorFeature.EMPHASIS)


def test_feature_profile_service_prompt_syntaxes_respects_ghost_text_preference() -> (
    None
):
    """Prompt syntax metadata should not field-disable autocomplete ghost text."""

    enabled_profile = _profile_service(
        preferences=PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT: True},
        )
    ).build_profile(
        field_style={"prompt_syntaxes": ["wildcard"]},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )
    disabled_profile = _profile_service(
        preferences=PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT: False},
        )
    ).build_profile(
        field_style={"prompt_syntaxes": ["wildcard"]},
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert enabled_profile.supports(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)
    assert not disabled_profile.supports(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)
    assert (
        disabled_profile.decision_for(
            PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT
        ).disabled_reason
        is PromptFeatureDisabledReason.USER_DISABLED
    )


def test_feature_profile_service_maps_lora_prompt_syntaxes_when_supported() -> None:
    """LoRA prompt_syntaxes should enable split features for supported prompt paths."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_keeps_lora_syntax_without_workflow_context() -> None:
    """LoRA syntax should render even when runtime LoRA actions are unavailable."""

    service = _profile_service()

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


def test_feature_profile_service_keeps_lora_syntax_for_vanilla_clip_encode() -> None:
    """Plain CLIP encoders should render syntax without runtime LoRA actions."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_enables_lora_syntax_for_prompt_control_wrapper() -> (
    None
):
    """Subgraph wrappers should prove LoRA support from their body node classes."""

    service = _profile_service()
    wrapper_class = "94f725d5-39bf-4060-be68-f573214a2055"

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_enables_lora_for_simple_syrup_positive_prompt() -> (
    None
):
    """SimpleSyrup scheduling nodes should support positive prompt LoRA scheduling."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_enables_lora_for_simple_syrup_negative_prompt() -> (
    None
):
    """SimpleSyrup scheduling nodes should support negative prompt LoRA scheduling."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_blocks_simple_syrup_non_prompt_inputs() -> None:
    """SimpleSyrup non-prompt inputs should not enable runtime LoRA actions."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_enables_lora_for_simple_syrup_direct_field() -> None:
    """Direct SimpleSyrup prompt fields should advertise their own LoRA support."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_uses_restored_original_cube_graph() -> None:
    """Restored cube definitions should prove support when buffers are patch-like."""

    service = _profile_service()

    profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
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


def test_feature_profile_service_lora_autocomplete_depends_on_lora_syntax() -> None:
    """Dependency resolution should keep split LoRA features coherent."""

    service = _profile_service()
    profile = service.build_profile(
        field_style={"prompt_features": ["lora_autocomplete"]},
        workflow_context=None,
        cube_alias=None,
        prompt_node_name="prompt",
        prompt_field_key="text",
    )

    assert not profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert (
        profile.decision_for(PromptEditorFeature.LORA_AUTOCOMPLETE).disabled_reason
        is PromptFeatureDisabledReason.FIELD_DISABLED
    )


def _profile_service(
    *,
    preferences: PromptEditorPreferences | None = None,
) -> PromptFeatureProfileService:
    """Return a profile service wired to test doubles."""

    return PromptFeatureProfileService(
        preference_service=PromptEditorPreferenceService(
            _MemoryPreferenceRepository(preferences)
        ),
    )


def _workflow_context(
    nodes: dict[str, dict[str, Any]],
    *,
    original_cube: dict[str, Any] | None = None,
    subgraphs: tuple[dict[str, Any], ...] = (),
) -> WorkflowPromptContext:
    """Return a workflow context containing one cube graph."""

    return WorkflowPromptContext(
        cube_states={
            "Cube": SimpleNamespace(
                original_cube=original_cube or {},
                buffer={
                    "nodes": nodes,
                    "subgraphs": subgraphs,
                },
            )
        },
        stack_order=("Cube",),
        workflow_overrides={},
        behavior_snapshot=None,
    )


class _MemoryPreferenceRepository:
    """In-memory repository for feature profile tests."""

    def __init__(self, preferences: PromptEditorPreferences | None) -> None:
        """Store an optional test preference snapshot."""

        self._preferences = preferences or PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={feature: True for feature in PromptEditorFeature},
        )

    def load(self) -> PromptEditorPreferences:
        """Return the stored preference snapshot."""

        return self._preferences

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Replace the stored preference snapshot."""

        self._preferences = preferences
