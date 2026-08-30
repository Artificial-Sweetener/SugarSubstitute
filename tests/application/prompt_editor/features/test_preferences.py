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

"""Test prompt feature profile preference resolution."""

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


def test_featureprofile_service_disables_user_disabled_feature() -> None:
    """User preferences should suppress otherwise allowed features."""

    service = profile_service(
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
    service = profile_service(
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


def test_featureprofile_service_disables_user_disabled_ghost_text() -> None:
    """User preferences should suppress autocomplete ghost text independently."""

    service = profile_service(
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
