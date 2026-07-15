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

"""Tests for panel prompt profile policy preparation."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptSyntaxProfile,
)
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptProfilePolicy,
)


def _policy() -> PanelPromptProfilePolicy:
    """Return the prompt profile policy under test."""

    return PanelPromptProfilePolicy()


def test_policy_maps_legacy_prompt_syntaxes_to_fallback_features() -> None:
    """Legacy prompt syntax metadata should drive service-absent feature fallback."""

    decision = _policy().prepare_prompt_field_profile(
        field_style={"prompt_syntaxes": ["emphasis", "wildcard"]}
    )

    assert decision.feature_profile.supports(PromptEditorFeature.EMPHASIS)
    assert decision.feature_profile.supports(PromptEditorFeature.WILDCARD_SYNTAX)
    assert decision.feature_profile.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE)
    assert decision.feature_profile.supports(PromptEditorFeature.DANBOORU_URL_IMPORT)
    assert decision.feature_profile.supports(PromptEditorFeature.DANBOORU_WIKI_LOOKUP)
    assert decision.feature_profile.supports(
        PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT
    )
    assert decision.feature_profile.supports(PromptEditorFeature.SEGMENT_REORDER)
    assert decision.feature_profile.supports(PromptEditorFeature.SPELLCHECK)
    assert not decision.feature_profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert decision.syntax_profile.enabled_syntaxes == ("emphasis", "wildcard")


def test_policy_maps_lora_syntax_to_fallback_lora_features() -> None:
    """LoRA legacy syntax metadata should enable the full LoRA editor family."""

    decision = _policy().prepare_prompt_field_profile(
        field_style={"prompt_syntaxes": ["lora"]}
    )

    assert decision.feature_profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert decision.feature_profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert decision.feature_profile.supports(PromptEditorFeature.LORA_PICKER)
    assert decision.feature_profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS)
    assert decision.syntax_profile.enabled_syntaxes == ("lora",)


def test_policy_enables_all_features_without_legacy_prompt_syntaxes() -> None:
    """Missing prompt syntax metadata should preserve the broad fallback profile."""

    decision = _policy().prepare_prompt_field_profile(field_style={})

    assert all(
        decision.feature_profile.supports(feature) for feature in PromptEditorFeature
    )
    assert decision.syntax_profile.enabled_syntaxes == (
        "emphasis",
        "wildcard",
        "lora",
    )


def test_policy_preserves_prepared_feature_and_syntax_profiles() -> None:
    """Already resolved profile inputs should pass through unchanged."""

    feature_profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.EMPHASIS,
                enabled=True,
            ),
        )
    )
    syntax_profile = PromptSyntaxProfile(enabled_syntaxes=("emphasis",))

    decision = _policy().prepare_prompt_field_profile(
        field_style={"prompt_syntaxes": ["wildcard"]},
        feature_profile=feature_profile,
        syntax_profile=syntax_profile,
    )

    assert decision.feature_profile is feature_profile
    assert decision.syntax_profile is syntax_profile
