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

"""Own autocomplete session lifecycle, retargeting, and selection state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryState,
    PromptAutocompleteResultSnapshot,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextSourceSnapshot,
)

PromptAutocompleteLifecycleState = Literal["idle", "active", "refreshing"]
PromptAutocompleteDismissReason = Literal[
    "accepted",
    "escape",
    "focus_lost",
    "editor_hidden",
    "caret_left_query",
    "selection_started",
    "incompatible_query",
    "no_query",
]


@dataclass(slots=True)
class PromptAutocompleteSessionState:
    """Store authoritative autocomplete lifecycle state for presentation owners."""

    lifecycle: PromptAutocompleteLifecycleState = "idle"
    session: AutocompleteSession | None = None
    source_identity: PromptCommandSourceIdentity | None = None
    ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None = None


def selected_autocomplete_suggestion(
    session: AutocompleteSession,
) -> PromptAutocompleteSuggestion | None:
    """Return the currently selected autocomplete suggestion when it exists."""

    if 0 <= session.selected_index < len(session.suggestions):
        return session.suggestions[session.selected_index]
    return None


def selected_lora_autocomplete_candidate(
    session: AutocompleteSession,
) -> PromptLoraAutocompleteCandidate | None:
    """Return the currently selected LoRA candidate when it exists."""

    if 0 <= session.selected_index < len(session.lora_candidates):
        return session.lora_candidates[session.selected_index]
    return None


class PromptAutocompleteSessionController:
    """Own active autocomplete session state and lifecycle transitions."""

    def __init__(self) -> None:
        """Initialize idle autocomplete lifecycle state."""

        self._state = PromptAutocompleteSessionState()

    @property
    def state(self) -> PromptAutocompleteSessionState:
        """Return the retained autocomplete lifecycle state."""

        return self._state

    @property
    def session(self) -> AutocompleteSession:
        """Return the current renderable autocomplete session."""

        return self.render_session()

    @property
    def source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the source identity that prepared the current session."""

        return self._state.source_identity

    @property
    def ghost_text_source_snapshot(
        self,
    ) -> PromptAutocompleteGhostTextSourceSnapshot | None:
        """Return the source snapshot used by ghost-text publication."""

        return self._state.ghost_text_source_snapshot

    def render_session(self) -> AutocompleteSession:
        """Return active or refreshing presentation state, or an empty session."""

        if self._state.session is None:
            return AutocompleteSession()
        return self._state.session

    def dismiss(self, reason: PromptAutocompleteDismissReason) -> None:
        """Dismiss autocomplete state for one explicit lifecycle reason."""

        _ = reason
        self._state = PromptAutocompleteSessionState()

    def replace_result(
        self,
        result: PromptAutocompleteResultSnapshot,
        *,
        source_identity: PromptCommandSourceIdentity | None,
        ghost_text_source_snapshot: PromptAutocompleteGhostTextSourceSnapshot | None,
    ) -> bool:
        """Replace retained state with one ready result while preserving selection."""

        session = self._session_from_result(result)
        if session is None:
            return False
        self._state = PromptAutocompleteSessionState(
            lifecycle="active",
            session=session,
            source_identity=source_identity,
            ghost_text_source_snapshot=ghost_text_source_snapshot,
        )
        return True

    def can_retarget(self, query_state: PromptAutocompleteQueryState) -> bool:
        """Return whether the active session can follow one compatible source edit."""

        if query_state.has_selection:
            return False
        session = self._state.session
        if session is None or not self.has_active_session():
            return False
        if query_state.lora_query is not None:
            return self._can_retarget_lora(session, query_state.lora_query)
        if query_state.wildcard_query is not None:
            return self._can_retarget_wildcard(session, query_state.wildcard_query)
        if query_state.scene_query is not None:
            return self._can_retarget_scene(session, query_state.scene_query)
        if query_state.tag_query is not None:
            return self._can_retarget_tag(session, query_state.tag_query)
        return False

    def retarget(self, query_state: PromptAutocompleteQueryState) -> bool:
        """Synchronously retarget retained state to a compatible query range."""

        if not self.can_retarget(query_state):
            return False
        session = self._state.session
        if session is None:
            return False
        next_session = self._retargeted_session(session, query_state)
        if next_session is None:
            return False
        self._state = PromptAutocompleteSessionState(
            lifecycle="refreshing",
            session=next_session,
            source_identity=cast(
                PromptCommandSourceIdentity | None, query_state.source_identity
            ),
            ghost_text_source_snapshot=PromptAutocompleteGhostTextSourceSnapshot(
                source_revision=query_state.source_revision,
                source_length=query_state.source_length,
                cursor_position=query_state.cursor_position,
                source_text=query_state.source_text,
            ),
        )
        return True

    def has_active_session(self) -> bool:
        """Return whether retained state has selectable presentation content."""

        session = self._state.session
        if session is None:
            return False
        if session.mode == "lora":
            return session.selected_index >= 0 and bool(session.lora_candidates)
        return session.selected_index >= 0 and bool(session.suggestions)

    def move_suggestion_selection(self, delta: int) -> bool:
        """Move selected suggestion by one wrapping delta when suggestions exist."""

        session = self._state.session
        if session is None or not session.suggestions:
            return False
        suggestion_count = len(session.suggestions)
        if session.selected_index < 0 or session.selected_index >= suggestion_count:
            session.selected_index = 0 if delta >= 0 else suggestion_count - 1
            return True
        session.selected_index = (session.selected_index + delta) % suggestion_count
        return True

    def move_lora_selection_linear(self, delta: int) -> bool:
        """Move selected LoRA candidate by one bounded delta."""

        session = self._state.session
        if session is None or not session.lora_candidates:
            return False
        session.selected_index = _clamped_index(
            session.selected_index + delta,
            item_count=len(session.lora_candidates),
        )
        return True

    def select_index(self, index: int) -> None:
        """Mirror presenter-owned selection or activation into the session."""

        session = self._state.session
        if session is not None:
            session.selected_index = index

    def _session_from_result(
        self,
        result: PromptAutocompleteResultSnapshot,
    ) -> AutocompleteSession | None:
        """Return a renderable session for one ready result."""

        if result.status != "ready":
            return None
        if result.mode == "tag" and result.suggestions:
            return AutocompleteSession(
                mode="tag",
                suggestions=result.suggestions,
                selected_index=self._preserved_suggestion_index(result.suggestions),
                word_start=result.word_start,
                word_end=result.word_end,
                active_tag_end=result.active_tag_end,
                prefix=result.prefix,
            )
        if result.mode == "scene" and result.suggestions:
            return AutocompleteSession(
                mode="scene",
                suggestions=result.suggestions,
                selected_index=self._preserved_suggestion_index(result.suggestions),
                word_start=result.word_start,
                word_end=result.word_end,
                prefix=result.prefix,
                scene_query=result.scene_query,
            )
        if result.mode == "wildcard" and result.suggestions:
            return AutocompleteSession(
                mode="wildcard",
                suggestions=result.suggestions,
                selected_index=self._preserved_suggestion_index(result.suggestions),
                word_start=result.word_start,
                word_end=result.word_end,
                prefix=result.prefix,
                wildcard_query=result.wildcard_query,
            )
        if result.mode == "lora" and result.lora_candidates:
            return AutocompleteSession(
                mode="lora",
                selected_index=self._preserved_lora_index(result.lora_candidates),
                lora_candidates=result.lora_candidates,
                lora_query=result.lora_query,
            )
        return None

    def _retargeted_session(
        self,
        session: AutocompleteSession,
        query_state: PromptAutocompleteQueryState,
    ) -> AutocompleteSession | None:
        """Return a retained session moved onto the latest compatible query."""

        if query_state.lora_query is not None:
            return AutocompleteSession(
                mode="lora",
                selected_index=session.selected_index,
                lora_candidates=session.lora_candidates,
                lora_query=query_state.lora_query,
            )
        if query_state.wildcard_query is not None:
            wildcard_query = query_state.wildcard_query
            return AutocompleteSession(
                mode="wildcard",
                suggestions=session.suggestions,
                selected_index=session.selected_index,
                word_start=wildcard_query.opener_start,
                word_end=wildcard_query.replacement_end,
                prefix=wildcard_query.prefix,
                wildcard_query=wildcard_query,
            )
        if query_state.scene_query is not None:
            scene_query = query_state.scene_query
            return AutocompleteSession(
                mode="scene",
                suggestions=session.suggestions,
                selected_index=session.selected_index,
                word_start=scene_query.title_start,
                word_end=scene_query.cursor_position,
                prefix=scene_query.prefix,
                scene_query=scene_query,
            )
        if query_state.tag_query is not None:
            tag_query = query_state.tag_query
            return AutocompleteSession(
                mode="tag",
                suggestions=session.suggestions,
                selected_index=session.selected_index,
                word_start=tag_query.word_start,
                word_end=tag_query.word_end,
                active_tag_end=tag_query.active_tag_end,
                prefix=tag_query.prefix,
            )
        return None

    @staticmethod
    def _can_retarget_tag(
        session: AutocompleteSession,
        query: PromptAutocompleteQuery,
    ) -> bool:
        """Return whether a tag session can follow the new tag query."""

        return (
            session.mode == "tag"
            and session.word_start == query.word_start
            and query.word_end >= query.word_start
        )

    @staticmethod
    def _can_retarget_scene(
        session: AutocompleteSession,
        query: PromptSceneAutocompleteQuery,
    ) -> bool:
        """Return whether a scene session can follow the new title query."""

        previous_query = session.scene_query
        return (
            session.mode == "scene"
            and previous_query is not None
            and previous_query.marker_start == query.marker_start
            and previous_query.title_start == query.title_start
        )

    @staticmethod
    def _can_retarget_wildcard(
        session: AutocompleteSession,
        query: PromptWildcardAutocompleteQuery,
    ) -> bool:
        """Return whether a wildcard session can follow the new wildcard query."""

        previous_query = session.wildcard_query
        return (
            session.mode == "wildcard"
            and previous_query is not None
            and previous_query.opener_start == query.opener_start
            and previous_query.content_start == query.content_start
        )

    @staticmethod
    def _can_retarget_lora(
        session: AutocompleteSession,
        query: PromptLoraAutocompleteQuery,
    ) -> bool:
        """Return whether a LoRA session can follow the new LoRA query."""

        previous_query = session.lora_query
        return (
            session.mode == "lora"
            and previous_query is not None
            and previous_query.token_start == query.token_start
            and previous_query.name_start == query.name_start
        )

    def _preserved_suggestion_index(
        self,
        suggestions: tuple[PromptAutocompleteSuggestion, ...],
    ) -> int:
        """Return the next suggestion index preserving selected tag identity."""

        previous_suggestion = selected_autocomplete_suggestion(self.render_session())
        if previous_suggestion is None:
            return 0
        return next(
            (
                index
                for index, suggestion in enumerate(suggestions)
                if suggestion.tag == previous_suggestion.tag
            ),
            0,
        )

    def _preserved_lora_index(
        self,
        candidates: tuple[PromptLoraAutocompleteCandidate, ...],
    ) -> int:
        """Return the next LoRA index preserving selected prompt-name identity."""

        previous_candidate = selected_lora_autocomplete_candidate(self.render_session())
        if previous_candidate is None:
            return 0
        return next(
            (
                index
                for index, candidate in enumerate(candidates)
                if candidate.item.prompt_name == previous_candidate.item.prompt_name
            ),
            0,
        )


def _clamped_index(index: int, *, item_count: int) -> int:
    """Return an index clamped to one non-empty collection."""

    return max(0, min(item_count - 1, index))


__all__ = [
    "PromptAutocompleteDismissReason",
    "PromptAutocompleteLifecycleState",
    "PromptAutocompleteSessionController",
    "PromptAutocompleteSessionState",
    "selected_autocomplete_suggestion",
    "selected_lora_autocomplete_candidate",
]
