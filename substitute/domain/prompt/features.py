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

"""Define prompt editor feature decisions independent of Qt presentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromptEditorFeature(str, Enum):
    """Identify user-controllable prompt editor capabilities."""

    EMPHASIS = "emphasis"
    DANBOORU_URL_IMPORT = "danbooru_url_import"
    DANBOORU_WIKI_LOOKUP = "danbooru_wiki_lookup"
    WILDCARD_SYNTAX = "wildcard_syntax"
    WILDCARD_AUTOCOMPLETE = "wildcard_autocomplete"
    AUTOCOMPLETE_GHOST_TEXT = "autocomplete_ghost_text"
    LORA_SYNTAX = "lora_syntax"
    LORA_AUTOCOMPLETE = "lora_autocomplete"
    LORA_PICKER = "lora_picker"
    LORA_TRIGGER_WORDS = "lora_trigger_words"
    SEGMENT_REORDER = "segment_reorder"
    SPELLCHECK = "spellcheck"
    DUPLICATE_SEGMENT_DIAGNOSTICS = "duplicate_segment_diagnostics"


class PromptFeatureDisabledReason(str, Enum):
    """Explain why a prompt editor feature is not available."""

    USER_DISABLED = "user_disabled"
    FIELD_DISABLED = "field_disabled"
    MISSING_SERVICE = "missing_service"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class PromptFeatureDecision:
    """Capture one resolved prompt feature availability decision."""

    feature: PromptEditorFeature
    enabled: bool
    disabled_reason: PromptFeatureDisabledReason | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PromptEditorFeatureProfile:
    """Group resolved prompt feature decisions for one prompt editor field."""

    decisions: tuple[PromptFeatureDecision, ...]

    @classmethod
    def enabled_profile(
        cls,
        features: tuple[PromptEditorFeature, ...],
    ) -> PromptEditorFeatureProfile:
        """Build a profile that enables each supplied feature."""

        return cls(
            decisions=tuple(
                PromptFeatureDecision(feature=feature, enabled=True)
                for feature in features
            )
        )

    def supports(self, feature: PromptEditorFeature) -> bool:
        """Return whether the feature is enabled in this profile."""

        return self.decision_for(feature).enabled

    def decision_for(self, feature: PromptEditorFeature) -> PromptFeatureDecision:
        """Return the decision for one feature or a default disabled decision."""

        for decision in self.decisions:
            if decision.feature is feature:
                return decision
        return PromptFeatureDecision(
            feature=feature,
            enabled=False,
            disabled_reason=PromptFeatureDisabledReason.FIELD_DISABLED,
            detail="Feature is not present in this prompt profile.",
        )


__all__ = [
    "PromptEditorFeature",
    "PromptEditorFeatureProfile",
    "PromptFeatureDecision",
    "PromptFeatureDisabledReason",
]
