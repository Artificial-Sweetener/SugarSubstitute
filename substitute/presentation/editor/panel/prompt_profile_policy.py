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

"""Prepare panel prompt-editor feature and syntax profile decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptSyntaxProfile,
    prompt_syntax_field_features,
    prompt_syntax_profile_from_feature_profile,
)


@dataclass(frozen=True, slots=True)
class PanelPromptFieldProfileDecision:
    """Carry prepared prompt feature and renderer syntax profiles."""

    feature_profile: PromptEditorFeatureProfile
    syntax_profile: PromptSyntaxProfile


class PanelPromptProfilePolicy:
    """Prepare prompt-editor profile inputs before widget construction."""

    def prepare_prompt_field_profile(
        self,
        *,
        field_style: Mapping[str, object],
        feature_profile: PromptEditorFeatureProfile | None = None,
        syntax_profile: PromptSyntaxProfile | None = None,
    ) -> PanelPromptFieldProfileDecision:
        """Return the complete prompt profile decision for one prompt field."""

        resolved_feature_profile = feature_profile or self.fallback_feature_profile(
            field_style
        )
        resolved_syntax_profile = (
            syntax_profile
            if syntax_profile is not None
            else prompt_syntax_profile_from_feature_profile(resolved_feature_profile)
        )
        return PanelPromptFieldProfileDecision(
            feature_profile=resolved_feature_profile,
            syntax_profile=resolved_syntax_profile,
        )

    def fallback_feature_profile(
        self,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile:
        """Build the service-absent prompt feature fallback from field style."""

        raw_syntaxes = field_style.get("prompt_syntaxes")
        if isinstance(raw_syntaxes, list):
            enabled_features = prompt_syntax_field_features(raw_syntaxes)
        else:
            enabled_features = frozenset(PromptEditorFeature)
        return PromptEditorFeatureProfile(
            decisions=tuple(
                PromptFeatureDecision(
                    feature=feature,
                    enabled=feature in enabled_features,
                )
                for feature in PromptEditorFeature
            )
        )


__all__ = [
    "PanelPromptFieldProfileDecision",
    "PanelPromptProfilePolicy",
]
