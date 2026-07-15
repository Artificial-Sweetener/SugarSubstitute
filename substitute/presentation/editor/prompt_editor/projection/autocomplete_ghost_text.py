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

"""Own projection-facing autocomplete ghost-text state publication."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import PromptLoraAutocompleteCandidate
from substitute.application.prompt_editor.prompt_autocomplete_text import (
    autocomplete_completion_suffix,
    autocomplete_suffix_without_existing_right_text,
)

from ..debug_probe import log_prompt_editor_probe, preview_probe_state
from ..autocomplete_preview_state import PromptAutocompletePreviewState
from ..models import AutocompleteSession


@dataclass(frozen=True, slots=True)
class PromptAutocompleteGhostTextSourceSnapshot:
    """Carry prepared source state needed to compute ghost text without widget reads."""

    source_revision: int
    source_length: int
    cursor_position: int
    source_text: str

    @property
    def is_consistent(self) -> bool:
        """Return whether source identity agrees with the prepared source text."""

        return self.source_length == len(self.source_text)


@dataclass(frozen=True, slots=True)
class PromptAutocompleteGhostTextState:
    """Carry source-safe identity for projection autocomplete preview state."""

    source_revision: int
    source_length: int
    cursor_position: int
    query_identity: Hashable | None
    candidate_identity: Hashable | None
    preview_state: PromptAutocompletePreviewState | None


class PromptAutocompletePreviewStateSink(Protocol):
    """Publish computed autocomplete preview state to the projection surface."""

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the projection-owned autocomplete preview state."""


class PromptAutocompleteGhostTextPublisher:
    """Publish prepared autocomplete ghost text into projection preview state."""

    def __init__(self, *, preview_sink: PromptAutocompletePreviewStateSink) -> None:
        """Store the projection sink without owning source or query behavior."""

        self._preview_sink = preview_sink
        self._last_state: PromptAutocompleteGhostTextState | None = None

    def publish_for_session(
        self,
        session: AutocompleteSession,
        *,
        source_snapshot: PromptAutocompleteGhostTextSourceSnapshot,
    ) -> None:
        """Publish or clear the ghost text preview for one autocomplete session."""

        state = self._state_for_session(
            session,
            source_snapshot=source_snapshot,
        )
        log_prompt_editor_probe(
            "ghost_text.publish_for_session",
            mode=session.mode,
            prefix=session.prefix,
            selected_index=session.selected_index,
            preview=preview_probe_state(state.preview_state),
            source_revision=source_snapshot.source_revision,
            cursor_position=source_snapshot.cursor_position,
        )
        self._publish_state(state)

    def clear(self) -> None:
        """Clear any active projection ghost preview from the authoritative sink."""

        log_prompt_editor_probe(
            "ghost_text.clear",
            had_last_state=self._last_state is not None,
            last_preview=None
            if self._last_state is None
            else preview_probe_state(self._last_state.preview_state),
        )
        self._last_state = None
        self._preview_sink.set_autocomplete_preview_state(None)

    def _publish_state(self, state: PromptAutocompleteGhostTextState) -> None:
        """Publish one computed state only when its identity changes."""

        if state == self._last_state:
            log_prompt_editor_probe(
                "ghost_text.publish_state.noop",
                preview=preview_probe_state(state.preview_state),
            )
            return
        self._last_state = state
        log_prompt_editor_probe(
            "ghost_text.publish_state.apply",
            preview=preview_probe_state(state.preview_state),
        )
        self._preview_sink.set_autocomplete_preview_state(state.preview_state)

    def _state_for_session(
        self,
        session: AutocompleteSession,
        *,
        source_snapshot: PromptAutocompleteGhostTextSourceSnapshot,
    ) -> PromptAutocompleteGhostTextState:
        """Return the source-safe ghost text state for one prepared session."""

        cursor_position = source_snapshot.cursor_position
        preview_state: PromptAutocompletePreviewState | None
        query_identity: Hashable | None
        candidate_identity: Hashable | None
        if not source_snapshot.is_consistent:
            preview_state = None
            query_identity = _query_identity_for_session(session)
            candidate_identity = _candidate_identity_for_session(session)
        elif session.mode == "lora":
            preview_state, query_identity, candidate_identity = _lora_preview(
                session,
                cursor_position=cursor_position,
            )
        elif session.mode == "wildcard":
            preview_state, query_identity, candidate_identity = _wildcard_preview(
                session,
                cursor_position=cursor_position,
            )
        else:
            preview_state, query_identity, candidate_identity = _tag_preview(
                session,
                cursor_position=cursor_position,
                source_text=source_snapshot.source_text,
            )
        return PromptAutocompleteGhostTextState(
            source_revision=source_snapshot.source_revision,
            source_length=source_snapshot.source_length,
            cursor_position=cursor_position,
            query_identity=query_identity,
            candidate_identity=candidate_identity,
            preview_state=preview_state,
        )


def selected_autocomplete_suffix(session: AutocompleteSession) -> str:
    """Return the remaining ghost-text suffix for the selected suggestion."""

    suggestion = _selected_autocomplete_suggestion(session)
    if suggestion is None:
        return ""
    return autocomplete_completion_suffix(suggestion.tag, session.prefix)


def wildcard_completion_suffix(candidate_text: str, typed_prefix: str) -> str:
    """Return the remaining wildcard text plus its closing brace."""

    if not candidate_text.casefold().startswith(typed_prefix.casefold()):
        return ""
    return f"{candidate_text[len(typed_prefix) :]}}}"


def _query_identity_for_session(session: AutocompleteSession) -> Hashable | None:
    """Return a prompt-safe query identity for a session when preview is unavailable."""

    if session.mode == "lora":
        return _lora_query_identity(session)
    if session.mode == "wildcard":
        return _wildcard_query_identity(session)
    return _tag_query_identity(session)


def _candidate_identity_for_session(session: AutocompleteSession) -> Hashable | None:
    """Return a selected-candidate identity when preview is unavailable."""

    if session.mode == "lora":
        return _lora_candidate_identity(session)
    suggestion = _selected_autocomplete_suggestion(session)
    if suggestion is None:
        return None
    if session.mode == "wildcard":
        return ("wildcard", session.selected_index, suggestion.tag)
    return (
        session.mode,
        session.selected_index,
        suggestion.tag,
        suggestion.source_kind,
    )


def _tag_preview(
    session: AutocompleteSession,
    *,
    cursor_position: int,
    source_text: str,
) -> tuple[PromptAutocompletePreviewState | None, Hashable | None, Hashable | None]:
    """Return tag or scene ghost text state for the prepared cursor."""

    query_identity = _tag_query_identity(session)
    candidate_identity = _candidate_identity_for_session(session)
    if session.word_end != cursor_position:
        return None, query_identity, candidate_identity
    suffix = _selected_tag_preview_suffix(session, source_text=source_text)
    if not suffix or session.word_end is None:
        return None, query_identity, candidate_identity
    return (
        PromptAutocompletePreviewState(
            source_position=session.word_end,
            suffix_text=suffix,
        ),
        query_identity,
        candidate_identity,
    )


def _selected_tag_preview_suffix(
    session: AutocompleteSession,
    *,
    source_text: str,
) -> str:
    """Return tag ghost suffix without duplicating text right of the caret."""

    suffix = selected_autocomplete_suffix(session)
    if session.mode != "tag":
        return suffix
    word_end = session.word_end
    active_tag_end = session.active_tag_end
    if word_end is None or active_tag_end is None or active_tag_end <= word_end:
        return suffix
    return autocomplete_suffix_without_existing_right_text(
        suffix,
        source_text[word_end:active_tag_end],
    )


def _wildcard_preview(
    session: AutocompleteSession,
    *,
    cursor_position: int,
) -> tuple[PromptAutocompletePreviewState | None, Hashable | None, Hashable | None]:
    """Return wildcard ghost text state for the prepared cursor."""

    query = session.wildcard_query
    suggestion = _selected_autocomplete_suggestion(session)
    query_identity = _wildcard_query_identity(session)
    candidate_identity = _candidate_identity_for_session(session)
    if query is None or suggestion is None:
        return None, query_identity, candidate_identity
    if query.cursor_position != cursor_position:
        return None, query_identity, candidate_identity
    suffix = wildcard_completion_suffix(suggestion.tag, query.prefix)
    if not suffix:
        return None, query_identity, candidate_identity
    return (
        PromptAutocompletePreviewState(
            source_position=query.cursor_position,
            suffix_text=suffix,
        ),
        query_identity,
        candidate_identity,
    )


def _lora_preview(
    session: AutocompleteSession,
    *,
    cursor_position: int,
) -> tuple[PromptAutocompletePreviewState | None, Hashable | None, Hashable | None]:
    """Return LoRA ghost text state for the prepared cursor."""

    query = session.lora_query
    candidate = _selected_lora_autocomplete_candidate(session)
    query_identity = _lora_query_identity(session)
    candidate_identity = _lora_candidate_identity(session)
    if query is None or query.name_end != cursor_position:
        return None, query_identity, candidate_identity
    if candidate is None or not candidate.display_completion_suffix:
        return None, query_identity, candidate_identity
    return (
        PromptAutocompletePreviewState(
            source_position=query.name_end,
            suffix_text=candidate.display_completion_suffix,
        ),
        query_identity,
        candidate_identity,
    )


def _tag_query_identity(session: AutocompleteSession) -> Hashable:
    """Return the tag or scene preview query identity."""

    return (
        session.mode,
        session.prefix,
        session.word_start,
        session.word_end,
        session.active_tag_end,
    )


def _wildcard_query_identity(session: AutocompleteSession) -> Hashable:
    """Return the wildcard preview query identity."""

    query = session.wildcard_query
    return (
        "wildcard",
        None if query is None else query.prefix,
        None if query is None else query.opener_start,
        None if query is None else query.content_start,
        None if query is None else query.cursor_position,
        None if query is None else query.replacement_end,
    )


def _lora_query_identity(session: AutocompleteSession) -> Hashable:
    """Return the LoRA preview query identity."""

    query = session.lora_query
    return (
        "lora",
        None if query is None else query.query_text,
        None if query is None else query.token_start,
        None if query is None else query.token_end,
        None if query is None else query.name_start,
        None if query is None else query.name_end,
        None if query is None else query.replacement_start,
        None if query is None else query.replacement_end,
    )


def _lora_candidate_identity(session: AutocompleteSession) -> Hashable | None:
    """Return the selected LoRA preview candidate identity."""

    candidate = _selected_lora_autocomplete_candidate(session)
    if candidate is None:
        return None
    return (
        "lora",
        session.selected_index,
        candidate.item.prompt_name,
        candidate.item.backend_value,
        candidate.display_completion_suffix,
    )


def _selected_autocomplete_suggestion(
    session: AutocompleteSession,
) -> PromptAutocompleteSuggestion | None:
    """Return the currently selected autocomplete suggestion when it exists."""

    if 0 <= session.selected_index < len(session.suggestions):
        return session.suggestions[session.selected_index]
    return None


def _selected_lora_autocomplete_candidate(
    session: AutocompleteSession,
) -> PromptLoraAutocompleteCandidate | None:
    """Return the currently selected LoRA candidate when it exists."""

    if 0 <= session.selected_index < len(session.lora_candidates):
        return session.lora_candidates[session.selected_index]
    return None


__all__ = [
    "PromptAutocompleteGhostTextPublisher",
    "PromptAutocompleteGhostTextSourceSnapshot",
    "PromptAutocompleteGhostTextState",
    "PromptAutocompletePreviewStateSink",
    "selected_autocomplete_suffix",
    "wildcard_completion_suffix",
]
