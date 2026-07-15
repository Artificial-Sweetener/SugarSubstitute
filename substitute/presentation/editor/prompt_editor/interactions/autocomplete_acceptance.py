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

"""Own command-backed autocomplete acceptance preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from substitute.presentation.editor.prompt_editor.commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession

from .autocomplete_session import (
    selected_autocomplete_suggestion,
    selected_lora_autocomplete_candidate,
)

PromptAutocompleteAcceptanceStatus = Literal["accepted", "rejected"]


@dataclass(frozen=True, slots=True)
class PromptAutocompleteAcceptanceOutcome:
    """Report whether one autocomplete acceptance reached the command boundary."""

    status: PromptAutocompleteAcceptanceStatus
    command_result: PromptCommandResult[object] | None = None
    reason: str | None = None

    @classmethod
    def accepted(
        cls,
        command_result: PromptCommandResult[object],
    ) -> "PromptAutocompleteAcceptanceOutcome":
        """Create an outcome for an acceptance handled by command execution."""

        return cls(
            status="accepted" if command_result.status != "rejected" else "rejected",
            command_result=command_result,
            reason=command_result.reason,
        )

    @classmethod
    def rejected(cls, reason: str) -> "PromptAutocompleteAcceptanceOutcome":
        """Create an outcome for an acceptance rejected before command execution."""

        return cls(status="rejected", reason=reason)


class PromptAutocompleteAcceptanceCursor(Protocol):
    """Describe read-only cursor behavior needed during acceptance fallback."""

    def position(self) -> int:
        """Return the current cursor position."""


class PromptAutocompleteAcceptanceCommandFactory(Protocol):
    """Execute prepared autocomplete acceptances through the command boundary."""

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Execute one prepared autocomplete acceptance through commands."""


class PromptAutocompleteAcceptanceEditor(
    PromptAutocompleteAcceptanceCommandFactory,
    Protocol,
):
    """Describe editor behavior consumed by autocomplete acceptance only."""

    def textCursor(self) -> PromptAutocompleteAcceptanceCursor:
        """Return the editor's live cursor for bounded acceptance fallback."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity used to reject stale commands."""

    def commit_lora_autocomplete_replacement(self) -> None:
        """Publish syntax state after accepting one complete LoRA replacement."""


class PromptAutocompleteAcceptanceController:
    """Build prepared autocomplete acceptances and execute them through commands."""

    def __init__(self, *, editor: PromptAutocompleteAcceptanceEditor) -> None:
        """Store the command-capable editor without taking source ownership."""

        self._editor = editor

    def accept_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        add_comma: bool,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept the selected row for the active autocomplete session mode."""

        if session.mode == "lora":
            return self.accept_lora_session(
                session,
                source_identity=source_identity,
            )
        if session.mode == "scene":
            return self.accept_scene_session(
                session,
                source_identity=source_identity,
            )
        if session.mode == "wildcard":
            return self.accept_wildcard_session(
                session,
                source_identity=source_identity,
            )
        return self.accept_tag_session(
            session,
            source_identity=source_identity,
            add_comma=add_comma,
        )

    def accept_tag_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        add_comma: bool,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected tag or trigger-word autocomplete suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        if suggestion is None or session.word_start is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        word_end = session.word_end or self._editor.textCursor().position()
        command_result = self._editor.execute_autocomplete_acceptance(
            PromptTagAutocompleteAcceptance(
                tag=suggestion.tag,
                prefix=session.prefix,
                word_start=session.word_start,
                word_end=word_end,
                active_tag_end=session.active_tag_end or word_end,
                add_comma=add_comma,
                source_identity=source_identity,
            )
        )
        return PromptAutocompleteAcceptanceOutcome.accepted(command_result)

    def accept_scene_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected workflow scene title suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        query = session.scene_query
        if suggestion is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._editor.execute_autocomplete_acceptance(
            PromptSceneAutocompleteAcceptance(
                title=suggestion.tag,
                title_start=query.title_start,
                replacement_end=query.replacement_end,
                source_identity=source_identity,
            )
        )
        return PromptAutocompleteAcceptanceOutcome.accepted(command_result)

    def accept_wildcard_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected wildcard placeholder suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        query = session.wildcard_query
        if suggestion is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._editor.execute_autocomplete_acceptance(
            PromptWildcardAutocompleteAcceptance(
                wildcard_name=suggestion.tag,
                opener_start=query.opener_start,
                replacement_end=query.replacement_end,
                source_identity=source_identity,
            )
        )
        return PromptAutocompleteAcceptanceOutcome.accepted(command_result)

    def accept_lora_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected scheduler-safe LoRA autocomplete candidate."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        candidate = selected_lora_autocomplete_candidate(session)
        query = session.lora_query
        if candidate is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._editor.execute_autocomplete_acceptance(
            PromptLoraAutocompleteAcceptance(
                replacement_text=candidate.replacement_text,
                replacement_start=query.replacement_start,
                replacement_end=query.replacement_end,
                source_identity=source_identity,
            )
        )
        if command_result.status != "rejected":
            self._editor.commit_lora_autocomplete_replacement()
        return PromptAutocompleteAcceptanceOutcome.accepted(command_result)

    def _prepared_identity_is_current(
        self,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> bool:
        """Return whether the prepared query still matches current source identity."""

        if source_identity is None:
            return True
        current_identity = self._editor.prompt_command_source_identity()
        if current_identity is None:
            return False
        return source_identity.matches(
            source_revision=current_identity.source_revision,
            source_length=current_identity.source_length,
        )


__all__ = [
    "PromptAutocompleteAcceptanceCommandFactory",
    "PromptAutocompleteAcceptanceController",
    "PromptAutocompleteAcceptanceCursor",
    "PromptAutocompleteAcceptanceEditor",
    "PromptAutocompleteAcceptanceOutcome",
    "PromptAutocompleteAcceptanceStatus",
]
