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

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from substitute.presentation.editor.prompt_editor.commands.autocomplete_commands import (
    PromptAutocompleteAcceptance,
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
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


class PromptAutocompleteAcceptanceController:
    """Build prepared autocomplete acceptances and execute them through commands."""

    def __init__(
        self,
        *,
        cursor_position: Callable[[], int],
        current_source_identity: Callable[[], PromptSourceIdentity | None],
        execute_acceptance: Callable[
            [PromptAutocompleteAcceptance],
            PromptCommandResult[object],
        ],
        complete_lora_replacement: Callable[[], None],
    ) -> None:
        """Store the four focused commands required by autocomplete acceptance."""

        self._cursor_position = cursor_position
        self._current_source_identity = current_source_identity
        self._execute_acceptance = execute_acceptance
        self._complete_lora_replacement = complete_lora_replacement

    def accept_session(
        self,
        session: AutocompleteSession,
        *,
        source_identity: PromptSourceIdentity | None,
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
        source_identity: PromptSourceIdentity | None,
        add_comma: bool,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected tag or trigger-word autocomplete suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        if suggestion is None or session.word_start is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        word_end = session.word_end or self._cursor_position()
        command_result = self._execute_acceptance(
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
        source_identity: PromptSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected workflow scene title suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        query = session.scene_query
        if suggestion is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._execute_acceptance(
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
        source_identity: PromptSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected wildcard placeholder suggestion."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        suggestion = selected_autocomplete_suggestion(session)
        query = session.wildcard_query
        if suggestion is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._execute_acceptance(
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
        source_identity: PromptSourceIdentity | None,
    ) -> PromptAutocompleteAcceptanceOutcome:
        """Accept a selected scheduler-safe LoRA autocomplete candidate."""

        if not self._prepared_identity_is_current(source_identity):
            return PromptAutocompleteAcceptanceOutcome.rejected("stale_source")
        candidate = selected_lora_autocomplete_candidate(session)
        query = session.lora_query
        if candidate is None or query is None:
            return PromptAutocompleteAcceptanceOutcome.rejected("missing_selection")
        command_result = self._execute_acceptance(
            PromptLoraAutocompleteAcceptance(
                replacement_text=candidate.replacement_text,
                replacement_start=query.replacement_start,
                replacement_end=query.replacement_end,
                source_identity=source_identity,
            )
        )
        if command_result.status != "rejected":
            self._complete_lora_replacement()
        return PromptAutocompleteAcceptanceOutcome.accepted(command_result)

    def _prepared_identity_is_current(
        self,
        source_identity: PromptSourceIdentity | None,
    ) -> bool:
        """Return whether the prepared query still matches current source identity."""

        if source_identity is None:
            return True
        current_identity = self._current_source_identity()
        if current_identity is None:
            return False
        return source_identity.matches(
            source_revision=current_identity.source_revision,
            source_length=current_identity.source_length,
        )


__all__ = [
    "PromptAutocompleteAcceptanceController",
    "PromptAutocompleteAcceptanceOutcome",
    "PromptAutocompleteAcceptanceStatus",
]
