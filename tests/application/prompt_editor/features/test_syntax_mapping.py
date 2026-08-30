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

"""Test prompt feature profile syntax mapping."""

from __future__ import annotations

from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptFeatureDisabledReason,
)
from substitute.domain.prompt.preferences.models import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
)
from tests.application.prompt_editor.features.support import (
    profile_service,
)


def test_featureprofile_service_maps_legacy_prompt_syntaxes() -> None:
    """Legacy prompt_syntaxes style should map into feature ids."""

    service = profile_service()

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


def test_featureprofile_service_prompt_syntaxes_respects_ghost_text_preference() -> (
    None
):
    """Prompt syntax metadata should not field-disable autocomplete ghost text."""

    enabled_profile = profile_service(
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
    disabled_profile = profile_service(
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


def test_featureprofile_service_lora_autocomplete_depends_on_lora_syntax() -> None:
    """Dependency resolution should keep split LoRA features coherent."""

    service = profile_service()
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
