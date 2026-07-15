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

"""Define autocomplete acceptance commands for prompt editing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from substitute.application.prompt_editor.prompt_autocomplete_query_service import (
    autocomplete_replacement_text,
)
from substitute.application.prompt_editor.prompt_autocomplete_text import (
    autocomplete_characters_match,
    autocomplete_completion_suffix,
    autocomplete_suffix_without_existing_right_text,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)

from . import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
)

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptTagAutocompleteAcceptance:
    """Describe one prepared plain-tag autocomplete acceptance."""

    tag: str
    prefix: str
    word_start: int
    word_end: int
    active_tag_end: int
    add_comma: bool
    source_identity: PromptCommandSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptSceneAutocompleteAcceptance:
    """Describe one prepared scene-title autocomplete acceptance."""

    title: str
    title_start: int
    replacement_end: int
    source_identity: PromptCommandSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteAcceptance:
    """Describe one prepared wildcard autocomplete acceptance."""

    wildcard_name: str
    opener_start: int
    replacement_end: int
    source_identity: PromptCommandSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptLoraAutocompleteAcceptance:
    """Describe one prepared LoRA autocomplete acceptance."""

    replacement_text: str
    replacement_start: int
    replacement_end: int
    source_identity: PromptCommandSourceIdentity | None = None


PromptAutocompleteAcceptance: TypeAlias = (
    PromptTagAutocompleteAcceptance
    | PromptSceneAutocompleteAcceptance
    | PromptWildcardAutocompleteAcceptance
    | PromptLoraAutocompleteAcceptance
)


@dataclass(frozen=True, slots=True)
class _SourceReplacement:
    """Describe an autocomplete source replacement after accept-time checks."""

    start: int
    end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PromptAcceptTagAutocompleteCommand(Generic[TPayload]):
    """Accept one prepared plain-tag autocomplete suggestion."""

    acceptance: PromptTagAutocompleteAcceptance
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "accept_tag_autocomplete"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this autocomplete acceptance through the supplied session."""

        replacement = _tag_replacement_for_source(
            self.acceptance,
            source_text=session.source_text,
        )
        return _execute_autocomplete_replacement(
            command_name=self.name,
            session=session,
            source_identity=self.acceptance.source_identity,
            replacement=replacement,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptAcceptSceneAutocompleteCommand(Generic[TPayload]):
    """Accept one prepared scene-title autocomplete suggestion."""

    acceptance: PromptSceneAutocompleteAcceptance
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "accept_scene_autocomplete"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this scene autocomplete acceptance through the supplied session."""

        replacement = _SourceReplacement(
            start=self.acceptance.title_start,
            end=self.acceptance.replacement_end,
            replacement_text=self.acceptance.title,
        )
        return _execute_autocomplete_replacement(
            command_name=self.name,
            session=session,
            source_identity=self.acceptance.source_identity,
            replacement=replacement,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptAcceptWildcardAutocompleteCommand(Generic[TPayload]):
    """Accept one prepared wildcard autocomplete suggestion."""

    acceptance: PromptWildcardAutocompleteAcceptance
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "accept_wildcard_autocomplete"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this wildcard autocomplete acceptance through the supplied session."""

        replacement = _SourceReplacement(
            start=self.acceptance.opener_start,
            end=self.acceptance.replacement_end,
            replacement_text=f"{{{self.acceptance.wildcard_name}}}",
        )
        return _execute_autocomplete_replacement(
            command_name=self.name,
            session=session,
            source_identity=self.acceptance.source_identity,
            replacement=replacement,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptAcceptLoraAutocompleteCommand(Generic[TPayload]):
    """Accept one prepared LoRA autocomplete suggestion."""

    acceptance: PromptLoraAutocompleteAcceptance
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "accept_lora_autocomplete"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this LoRA autocomplete acceptance through the supplied session."""

        replacement = _SourceReplacement(
            start=self.acceptance.replacement_start,
            end=self.acceptance.replacement_end,
            replacement_text=self.acceptance.replacement_text,
        )
        return _execute_autocomplete_replacement(
            command_name=self.name,
            session=session,
            source_identity=self.acceptance.source_identity,
            replacement=replacement,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


def build_autocomplete_acceptance_command(
    acceptance: PromptAutocompleteAcceptance,
    *,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> (
    PromptAcceptTagAutocompleteCommand[TPayload]
    | PromptAcceptSceneAutocompleteCommand[TPayload]
    | PromptAcceptWildcardAutocompleteCommand[TPayload]
    | PromptAcceptLoraAutocompleteCommand[TPayload]
):
    """Return the executable command for one prepared autocomplete acceptance."""

    if isinstance(acceptance, PromptTagAutocompleteAcceptance):
        return PromptAcceptTagAutocompleteCommand(
            acceptance=acceptance,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    if isinstance(acceptance, PromptSceneAutocompleteAcceptance):
        return PromptAcceptSceneAutocompleteCommand(
            acceptance=acceptance,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    if isinstance(acceptance, PromptWildcardAutocompleteAcceptance):
        return PromptAcceptWildcardAutocompleteCommand(
            acceptance=acceptance,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    return PromptAcceptLoraAutocompleteCommand(
        acceptance=acceptance,
        normalizer=normalizer,
        exact_source=exact_source,
        undo_snapshot=undo_snapshot,
    )


def _execute_autocomplete_replacement(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    source_identity: PromptCommandSourceIdentity | None,
    replacement: _SourceReplacement,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> PromptCommandResult[TPayload]:
    """Validate and apply one autocomplete replacement."""

    if source_identity is not None and not source_identity.matches(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    ):
        return PromptCommandResult.rejected(command_name, reason="stale_source")
    if (
        replacement.start < 0
        or replacement.end < replacement.start
        or replacement.end > len(session.source_text)
    ):
        return PromptCommandResult.rejected(command_name, reason="invalid_source_range")

    source_change = session.replace_source_range(
        start=replacement.start,
        end=replacement.end,
        replacement_text=replacement.replacement_text,
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.AUTOCOMPLETE,
        exact_source=exact_source,
        record_undo=True,
        undo_snapshot=undo_snapshot,
    )
    return PromptCommandResult.from_source_change(command_name, source_change)


def _tag_replacement_for_source(
    acceptance: PromptTagAutocompleteAcceptance,
    *,
    source_text: str,
) -> _SourceReplacement:
    """Return the replacement range/text for one tag autocomplete acceptance."""

    replacement_text = autocomplete_replacement_text(acceptance.tag)
    if acceptance.add_comma:
        replacement_text = f"{replacement_text}, "
    replacement_end = _tag_replacement_end_for_source(
        acceptance,
        replacement_text=autocomplete_replacement_text(acceptance.tag),
        source_text=source_text,
    )
    return _SourceReplacement(
        start=acceptance.word_start,
        end=replacement_end,
        replacement_text=replacement_text,
    )


def _tag_replacement_end_for_source(
    acceptance: PromptTagAutocompleteAcceptance,
    *,
    replacement_text: str,
    source_text: str,
) -> int:
    """Return the accept-time replacement end after safe suffix consumption."""

    if acceptance.active_tag_end <= acceptance.word_end:
        return acceptance.word_end
    completion_suffix = autocomplete_completion_suffix(
        replacement_text,
        acceptance.prefix,
    )
    right_text = source_text[acceptance.word_end : acceptance.active_tag_end]
    if (
        right_text
        and autocomplete_suffix_without_existing_right_text(
            completion_suffix,
            right_text,
        )
        != completion_suffix
    ):
        return acceptance.active_tag_end
    return acceptance.word_end


__all__ = [
    "PromptAcceptLoraAutocompleteCommand",
    "PromptAcceptSceneAutocompleteCommand",
    "PromptAcceptTagAutocompleteCommand",
    "PromptAcceptWildcardAutocompleteCommand",
    "PromptAutocompleteAcceptance",
    "PromptLoraAutocompleteAcceptance",
    "PromptSceneAutocompleteAcceptance",
    "PromptTagAutocompleteAcceptance",
    "PromptWildcardAutocompleteAcceptance",
    "autocomplete_characters_match",
    "autocomplete_completion_suffix",
    "autocomplete_suffix_without_existing_right_text",
    "build_autocomplete_acceptance_command",
]
