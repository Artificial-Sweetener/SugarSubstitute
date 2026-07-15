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

"""Own prompt-editor presentation feature gates and shared feature snapshots."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptSyntaxProfile,
    prompt_syntax_field_features,
    prompt_syntax_profile_from_feature_profile,
)
from substitute.presentation.editor.prompt_editor.commands.feature_commands import (
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
)

TPayload = TypeVar("TPayload")

_DEFAULT_LEGACY_SYNTAXES = frozenset({"emphasis", "wildcard", "lora"})


@dataclass(frozen=True, slots=True)
class PromptFeatureActionState(Generic[TPayload]):
    """Describe a presentation-ready feature action for menus or overlays."""

    action_id: str
    label: str
    ready: bool
    disabled_reason: str | None = None
    command_request: PromptFeatureCommandRequest[TPayload] | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous action readiness state before UI owners consume it."""

        if not self.action_id.strip():
            raise ValueError("action_id must not be blank.")
        if not self.label.strip():
            raise ValueError("label must not be blank.")
        if self.ready and self.disabled_reason is not None:
            raise ValueError("ready actions must not carry a disabled reason.")


@dataclass(frozen=True, slots=True)
class PromptFeatureGateSnapshot:
    """Publish presentation feature gates without exposing controller ownership."""

    identity: PromptFeatureSnapshotIdentity
    decisions: tuple[PromptFeatureDecision, ...]

    @property
    def enabled_features(self) -> frozenset[PromptEditorFeature]:
        """Return the enabled features in this prepared gate snapshot."""

        return frozenset(
            decision.feature for decision in self.decisions if decision.enabled
        )

    def supports(self, feature: PromptEditorFeature) -> bool:
        """Return whether this snapshot enables one feature."""

        return self.decision_for(feature).enabled

    def decision_for(self, feature: PromptEditorFeature) -> PromptFeatureDecision:
        """Return the prepared decision for one feature."""

        for decision in self.decisions:
            if decision.feature is feature:
                return decision
        return PromptEditorFeatureProfile(self.decisions).decision_for(feature)


class PromptFeatureProfileController:
    """Own presentation-facing feature gates for one prompt editor instance."""

    def __init__(
        self,
        feature_profile: PromptEditorFeatureProfile,
        *,
        source_revision: int | None = None,
        stale: bool = False,
        scene_context_id: Hashable | None = None,
        cube_context_id: Hashable | None = None,
        query_identity: Hashable | None = None,
    ) -> None:
        """Store the resolved profile and its prepared identity."""

        self._profile = feature_profile
        self._identity = PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=prompt_feature_profile_identity(feature_profile),
            stale=stale,
            scene_context_id=scene_context_id,
            cube_context_id=cube_context_id,
            query_identity=query_identity,
        )
        self._snapshot = PromptFeatureGateSnapshot(
            identity=self._identity,
            decisions=feature_profile.decisions,
        )

    @classmethod
    def from_legacy_syntax(
        cls,
        syntax_profile: PromptSyntaxProfile | None,
    ) -> "PromptFeatureProfileController":
        """Build a controller from legacy syntax support."""

        return cls(prompt_feature_profile_from_legacy_syntax(syntax_profile))

    @property
    def profile(self) -> PromptEditorFeatureProfile:
        """Return the resolved domain feature profile."""

        return self._profile

    @property
    def identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the identity shared by feature snapshots from this profile."""

        return self._identity

    @property
    def snapshot(self) -> PromptFeatureGateSnapshot:
        """Return the prepared gate snapshot for foreground consumers."""

        return self._snapshot

    def supports(self, feature: PromptEditorFeature) -> bool:
        """Return whether the current prompt editor supports one feature."""

        return self._profile.supports(feature)

    def decision_for(self, feature: PromptEditorFeature) -> PromptFeatureDecision:
        """Return the resolved decision for one feature."""

        return self._profile.decision_for(feature)

    def syntax_profile(self) -> PromptSyntaxProfile:
        """Return renderer syntax support derived from the feature profile."""

        return prompt_syntax_profile_from_feature_profile(self._profile)

    @property
    def emphasis_enabled(self) -> bool:
        """Return whether emphasis editing is available."""

        return self.supports(PromptEditorFeature.EMPHASIS)

    @property
    def danbooru_url_import_enabled(self) -> bool:
        """Return whether Danbooru URL paste import is available."""

        return self.supports(PromptEditorFeature.DANBOORU_URL_IMPORT)

    @property
    def danbooru_wiki_lookup_enabled(self) -> bool:
        """Return whether Danbooru wiki lookup is available."""

        return self.supports(PromptEditorFeature.DANBOORU_WIKI_LOOKUP)

    @property
    def wildcard_syntax_enabled(self) -> bool:
        """Return whether wildcard syntax rendering is available."""

        return self.supports(PromptEditorFeature.WILDCARD_SYNTAX)

    @property
    def wildcard_autocomplete_enabled(self) -> bool:
        """Return whether wildcard autocomplete is available."""

        return self.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE)

    @property
    def autocomplete_ghost_text_enabled(self) -> bool:
        """Return whether inline autocomplete ghost text is available."""

        return self.supports(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)

    @property
    def lora_syntax_enabled(self) -> bool:
        """Return whether LoRA syntax rendering is available."""

        return self.supports(PromptEditorFeature.LORA_SYNTAX)

    @property
    def lora_autocomplete_enabled(self) -> bool:
        """Return whether LoRA autocomplete is available."""

        return self.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)

    @property
    def lora_picker_enabled(self) -> bool:
        """Return whether the LoRA picker action is available."""

        return self.supports(PromptEditorFeature.LORA_PICKER)

    @property
    def lora_trigger_words_enabled(self) -> bool:
        """Return whether LoRA trigger-word actions are available."""

        return self.supports(PromptEditorFeature.LORA_TRIGGER_WORDS)

    @property
    def segment_reorder_enabled(self) -> bool:
        """Return whether segment reorder editing is available."""

        return self.supports(PromptEditorFeature.SEGMENT_REORDER)

    @property
    def spellcheck_enabled(self) -> bool:
        """Return whether spellcheck diagnostics are available."""

        return self.supports(PromptEditorFeature.SPELLCHECK)

    @property
    def duplicate_segment_diagnostics_enabled(self) -> bool:
        """Return whether duplicate segment diagnostics are available."""

        return self.supports(PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS)


def prompt_feature_profile_identity(
    feature_profile: PromptEditorFeatureProfile,
) -> tuple[tuple[str, bool, str, str], ...]:
    """Return a stable hashable identity for one feature profile."""

    return tuple(
        (
            decision.feature.value,
            decision.enabled,
            "" if decision.disabled_reason is None else decision.disabled_reason.value,
            decision.detail,
        )
        for decision in feature_profile.decisions
    )


def prompt_feature_profile_from_legacy_syntax(
    syntax_profile: PromptSyntaxProfile | None,
) -> PromptEditorFeatureProfile:
    """Build the direct-widget fallback profile from legacy syntax support."""

    enabled_syntaxes = (
        frozenset(syntax_profile.enabled_syntaxes)
        if syntax_profile is not None
        else _DEFAULT_LEGACY_SYNTAXES
    )
    enabled_features = prompt_syntax_field_features(
        tuple(enabled_syntaxes),
        include_spellcheck=False,
    )
    return PromptEditorFeatureProfile(
        decisions=tuple(
            PromptFeatureDecision(feature=feature, enabled=feature in enabled_features)
            for feature in PromptEditorFeature
        )
    )


__all__ = [
    "PromptFeatureActionState",
    "PromptFeatureGateSnapshot",
    "PromptFeatureProfileController",
    "prompt_feature_profile_from_legacy_syntax",
    "prompt_feature_profile_identity",
]
