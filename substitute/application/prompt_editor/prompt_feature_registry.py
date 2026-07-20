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

"""Register prompt editor features and their product-facing metadata."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

from collections.abc import Sequence
from dataclasses import dataclass

from substitute.domain.prompt.features import PromptEditorFeature


@dataclass(frozen=True, slots=True)
class PromptFeatureDefinition:
    """Describe one prompt editor feature for settings and resolution."""

    feature: PromptEditorFeature
    label: str
    description: str
    default_user_allowed: bool
    field_style_aliases: tuple[str, ...] = ()
    dependencies: tuple[PromptEditorFeature, ...] = ()
    conflicts_with: tuple[PromptEditorFeature, ...] = ()
    renderer_syntax_kinds: tuple[str, ...] = ()


PROMPT_FEATURE_DEFINITIONS: tuple[PromptFeatureDefinition, ...] = (
    PromptFeatureDefinition(
        feature=PromptEditorFeature.EMPHASIS,
        label=app_text("Emphasis weights"),
        description=app_text("Adjust weighted prompt text and show emphasis controls."),
        default_user_allowed=True,
        field_style_aliases=("emphasis",),
        renderer_syntax_kinds=("emphasis",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.DANBOORU_URL_IMPORT,
        label=app_text("Danbooru URL import"),
        description=app_text(
            "Paste supported Danbooru post or image URLs as prompt tags."
        ),
        default_user_allowed=True,
        field_style_aliases=("danbooru_url_import",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
        label=app_text("Danbooru wiki lookup"),
        description=app_text(
            "Open selected prompt text as an in-app Danbooru wiki definition."
        ),
        default_user_allowed=True,
        field_style_aliases=("danbooru_wiki_lookup",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.WILDCARD_SYNTAX,
        label=app_text("Wildcard syntax"),
        description=app_text("Highlight and resolve wildcard tokens."),
        default_user_allowed=True,
        field_style_aliases=("wildcard", "wildcard_syntax"),
        renderer_syntax_kinds=("wildcard",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
        label=app_text("Wildcard autocomplete"),
        description=app_text("Suggest wildcard completions while editing prompts."),
        default_user_allowed=True,
        field_style_aliases=("wildcard", "wildcard_autocomplete"),
        dependencies=(PromptEditorFeature.WILDCARD_SYNTAX,),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT,
        label=app_text("Autocomplete ghost text"),
        description=app_text(
            "Preview the selected autocomplete suffix inline while editing prompts."
        ),
        default_user_allowed=True,
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.LORA_SYNTAX,
        label=app_text("LoRA syntax"),
        description=(
            app_text(
                "Parse and decorate Prompt Control LoRA schedule tokens in prompts."
            )
        ),
        default_user_allowed=True,
        field_style_aliases=("lora", "lora_syntax"),
        renderer_syntax_kinds=("lora",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.LORA_AUTOCOMPLETE,
        label=app_text("LoRA autocomplete"),
        description=app_text(
            "Suggest LoRA names from the model catalog while editing prompts."
        ),
        default_user_allowed=True,
        field_style_aliases=("lora", "lora_autocomplete"),
        dependencies=(PromptEditorFeature.LORA_SYNTAX,),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.LORA_PICKER,
        label=app_text("LoRA picker"),
        description=app_text(
            "Insert Prompt Control LoRA schedule tokens from the prompt menu."
        ),
        default_user_allowed=True,
        field_style_aliases=("lora", "lora_picker"),
        dependencies=(PromptEditorFeature.LORA_SYNTAX,),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.LORA_TRIGGER_WORDS,
        label=app_text("LoRA trigger words"),
        description=app_text(
            "Suggest trigger words for LoRAs that affect this prompt."
        ),
        default_user_allowed=True,
        field_style_aliases=("lora", "lora_trigger_words"),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.SEGMENT_REORDER,
        label=app_text("Segment reorder"),
        description=app_text(
            "Reorder prompt lines and comma-separated prompt segments."
        ),
        default_user_allowed=True,
        field_style_aliases=("segment_reorder",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.SPELLCHECK,
        label=app_text("Spellcheck"),
        description=app_text(
            "Underline prompt prose spelling issues and offer corrections."
        ),
        default_user_allowed=True,
        field_style_aliases=("spellcheck",),
    ),
    PromptFeatureDefinition(
        feature=PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,
        label=app_text("Duplicate segment warnings"),
        description=app_text(
            "Underline repeated prompt segments and offer cleanup actions."
        ),
        default_user_allowed=True,
        field_style_aliases=("duplicate_segment_diagnostics",),
    ),
)
_PROMPT_SYNTAX_BASE_FEATURES = frozenset(
    {
        PromptEditorFeature.DANBOORU_URL_IMPORT,
        PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
        PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,
        PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT,
        PromptEditorFeature.SEGMENT_REORDER,
        PromptEditorFeature.SPELLCHECK,
    }
)


def prompt_feature_definitions() -> tuple[PromptFeatureDefinition, ...]:
    """Return prompt feature definitions in deterministic priority order."""

    return PROMPT_FEATURE_DEFINITIONS


def prompt_feature_definition(
    feature: PromptEditorFeature,
) -> PromptFeatureDefinition:
    """Return the definition for one feature."""

    for definition in PROMPT_FEATURE_DEFINITIONS:
        if definition.feature is feature:
            return definition
    raise KeyError(feature)


def default_prompt_feature_preferences() -> dict[PromptEditorFeature, bool]:
    """Return default user preference values keyed by feature."""

    return {
        definition.feature: definition.default_user_allowed
        for definition in PROMPT_FEATURE_DEFINITIONS
    }


def prompt_syntax_field_features(
    syntaxes: Sequence[object],
    *,
    include_spellcheck: bool = True,
) -> frozenset[PromptEditorFeature]:
    """Return features field-allowed by host `prompt_syntaxes` metadata."""

    enabled_features: set[PromptEditorFeature] = set(_PROMPT_SYNTAX_BASE_FEATURES)
    if not include_spellcheck:
        enabled_features.discard(PromptEditorFeature.SPELLCHECK)
    normalized_syntaxes = {
        entry.strip().lower() for entry in syntaxes if isinstance(entry, str)
    }
    for definition in PROMPT_FEATURE_DEFINITIONS:
        if normalized_syntaxes.intersection(definition.field_style_aliases):
            enabled_features.add(definition.feature)
    return frozenset(enabled_features)


__all__ = [
    "PROMPT_FEATURE_DEFINITIONS",
    "PromptFeatureDefinition",
    "default_prompt_feature_preferences",
    "prompt_feature_definition",
    "prompt_feature_definitions",
    "prompt_syntax_field_features",
]
