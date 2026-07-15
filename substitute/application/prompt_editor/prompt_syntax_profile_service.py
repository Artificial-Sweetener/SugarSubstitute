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

"""Resolve prompt syntax profiles from field-behavior style metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.domain.prompt.features import PromptEditorFeatureProfile

from .prompt_feature_registry import prompt_feature_definitions

_EMPHASIS_KIND = "emphasis"
_LORA_KIND = "lora"
_WILDCARD_KIND = "wildcard"
_PROFILE_STYLE_KEY = "prompt_syntaxes"
_DEFAULT_ENABLED_SYNTAXES = (_EMPHASIS_KIND, _WILDCARD_KIND, _LORA_KIND)
_KNOWN_SYNTAXES = frozenset({_EMPHASIS_KIND, _WILDCARD_KIND, _LORA_KIND})


@dataclass(frozen=True, slots=True)
class PromptSyntaxProfile:
    """Describe which prompt syntax families are active for one editor field."""

    enabled_syntaxes: tuple[str, ...]

    def supports(self, syntax_kind: str) -> bool:
        """Return whether one syntax kind is enabled for the current field."""

        return syntax_kind in self.enabled_syntaxes


class PromptSyntaxProfileService:
    """Build prompt syntax profiles from application-owned field style metadata."""

    def build_profile(
        self,
        style: Mapping[str, object] | None = None,
    ) -> PromptSyntaxProfile:
        """Return one syntax profile derived from field-behavior style metadata."""

        raw_style = style or {}
        raw_syntaxes = raw_style.get(_PROFILE_STYLE_KEY)
        if not isinstance(raw_syntaxes, list):
            return self.default_profile()

        enabled_syntaxes: list[str] = []
        for entry in raw_syntaxes:
            if not isinstance(entry, str):
                continue
            normalized_entry = entry.strip().lower()
            if (
                normalized_entry not in _KNOWN_SYNTAXES
                or normalized_entry in enabled_syntaxes
            ):
                continue
            enabled_syntaxes.append(normalized_entry)

        if not enabled_syntaxes:
            return self.default_profile()
        return PromptSyntaxProfile(enabled_syntaxes=tuple(enabled_syntaxes))

    def default_profile(self) -> PromptSyntaxProfile:
        """Return the default syntax profile used when field metadata omits one."""

        return PromptSyntaxProfile(enabled_syntaxes=_DEFAULT_ENABLED_SYNTAXES)


def prompt_syntax_profile_from_feature_profile(
    feature_profile: PromptEditorFeatureProfile,
) -> PromptSyntaxProfile:
    """Project a feature profile into renderer syntax support."""

    enabled_syntaxes: list[str] = []
    for definition in prompt_feature_definitions():
        if not feature_profile.supports(definition.feature):
            continue
        for syntax_kind in definition.renderer_syntax_kinds:
            if syntax_kind not in enabled_syntaxes:
                enabled_syntaxes.append(syntax_kind)
    return PromptSyntaxProfile(enabled_syntaxes=tuple(enabled_syntaxes))


__all__ = [
    "PromptSyntaxProfile",
    "PromptSyntaxProfileService",
    "prompt_syntax_profile_from_feature_profile",
]
