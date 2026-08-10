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

"""Own source ranges used by direct text mutations in the prompt viewport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from ..commands.source_service import PromptSourceCommandService
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from ..core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)

TPayload = TypeVar("TPayload")

_SYNTAX_SENSITIVE_REPLACEMENT_CHARACTERS = frozenset("(){}<>:\\")


@dataclass(frozen=True, slots=True)
class PromptProjectionTextMutationContext:
    """Capture authoritative caret and token state for one direct text edit."""

    selection: PromptProjectionSelection
    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState
    tokens: tuple[PromptProjectionToken, ...]
    editing_enabled: bool


@dataclass(frozen=True, slots=True)
class PromptProjectionTextMutationRequest:
    """Describe one source range requested by a viewport input path."""

    start: int
    end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionTextMutationRange:
    """Identify the authoritative source range for one viewport text edit."""

    start: int
    end: int


class PromptProjectionTextMutationContextProvider(Protocol):
    """Provide current projection state without exposing a concrete widget."""

    def projection_text_mutation_context(
        self,
    ) -> PromptProjectionTextMutationContext:
        """Return the state that owns the next direct text mutation."""


class PromptTextMutationActions(Protocol):
    """Expose direct viewport text mutations to input adapters."""

    def insert_text(
        self,
        text: str,
        *,
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.TYPED,
        command_name: str = "insert_viewport_text",
    ) -> None:
        """Replace the current projection-backed selection with text."""

    def replace_text(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str,
        record_undo: bool = True,
    ) -> None:
        """Replace an input-owned source range after boundary resolution."""


class PromptProjectionTextMutationRangeResolver:
    """Resolve direct text edits against visible token caret semantics."""

    def resolve(
        self,
        context: PromptProjectionTextMutationContext,
        request: PromptProjectionTextMutationRequest,
    ) -> PromptProjectionTextMutationRange:
        """Return the source range represented by the current visible edit target."""

        start, end = request.start, request.end
        selection = context.selection
        if selection.is_empty and (start, end) == (selection.start, selection.end):
            insertion_position = self._collapsed_insertion_position(
                context,
                requested_position=start,
            )
            start = insertion_position
            end = insertion_position
        syntax_range = self._syntax_selection_range(
            context,
            start=start,
            end=end,
            replacement_text=request.replacement_text,
        )
        if syntax_range is not None:
            return syntax_range
        return PromptProjectionTextMutationRange(start=start, end=end)

    @staticmethod
    def _collapsed_insertion_position(
        context: PromptProjectionTextMutationContext,
        *,
        requested_position: int,
    ) -> int:
        """Resolve a collapsed visible caret to its authoritative source boundary."""

        caret = context.cursor_state
        token = _token_by_id(context.tokens, caret.token_id)
        if token is None:
            return requested_position
        if token.navigation_mode is PromptProjectionTokenNavigationMode.ATOMIC:
            if caret.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE:
                return token.source_end
            return token.source_start
        if caret.placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE:
            return token.source_start
        if caret.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE:
            return token.source_end
        return requested_position

    @staticmethod
    def _syntax_selection_range(
        context: PromptProjectionTextMutationContext,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionTextMutationRange | None:
        """Preserve emphasis wrapper replacement for syntax-sensitive selections."""

        if not replacement_text or not any(
            character in _SYNTAX_SENSITIVE_REPLACEMENT_CHARACTERS
            for character in replacement_text
        ):
            return None
        token_ids = (context.cursor_state.token_id, context.anchor_state.token_id)
        for token_id in token_ids:
            token = _token_by_id(context.tokens, token_id)
            if (
                token is not None
                and token.kind is PromptProjectionTokenKind.EMPHASIS
                and token.content_range == (start, end)
            ):
                return PromptProjectionTextMutationRange(
                    start=token.source_start,
                    end=token.source_end,
                )
        return None


class PromptProjectionTextMutationController(Generic[TPayload]):
    """Commit all direct viewport text through one boundary-policy owner."""

    def __init__(
        self,
        *,
        context_provider: PromptProjectionTextMutationContextProvider,
        source_commands: PromptSourceCommandService[TPayload],
        range_resolver: PromptProjectionTextMutationRangeResolver | None = None,
    ) -> None:
        """Store the projection context and sole source-command collaborator."""

        self._context_provider = context_provider
        self._source_commands = source_commands
        self._range_resolver = (
            range_resolver or PromptProjectionTextMutationRangeResolver()
        )

    def insert_text(
        self,
        text: str,
        *,
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.TYPED,
        command_name: str = "insert_viewport_text",
    ) -> None:
        """Replace the current selection at its visible source boundary."""

        context = self._context_provider.projection_text_mutation_context()
        self._commit(
            context,
            PromptProjectionTextMutationRequest(
                start=context.selection.start,
                end=context.selection.end,
                replacement_text=text,
            ),
            origin=origin,
            command_name=command_name,
            record_undo=True,
        )

    def replace_text(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str,
        record_undo: bool = True,
    ) -> None:
        """Commit an input-owned range after visible-boundary resolution."""

        context = self._context_provider.projection_text_mutation_context()
        self._commit(
            context,
            PromptProjectionTextMutationRequest(start, end, replacement_text),
            origin=origin,
            command_name=command_name,
            record_undo=record_undo,
        )

    def _commit(
        self,
        context: PromptProjectionTextMutationContext,
        request: PromptProjectionTextMutationRequest,
        *,
        origin: PromptSourceEditOrigin,
        command_name: str,
        record_undo: bool,
    ) -> None:
        """Resolve and commit one direct text mutation exactly once."""

        if not context.editing_enabled:
            return
        source_range = self._range_resolver.resolve(context, request)
        self._source_commands.replace_source_range(
            start=source_range.start,
            end=source_range.end,
            replacement_text=request.replacement_text,
            origin=origin,
            command_name=command_name,
            record_undo=record_undo,
        )


def _token_by_id(
    tokens: tuple[PromptProjectionToken, ...],
    token_id: str | None,
) -> PromptProjectionToken | None:
    """Return the token matching one caret-owned identifier."""

    if token_id is None:
        return None
    return next((token for token in tokens if token.token_id == token_id), None)


__all__ = [
    "PromptProjectionTextMutationContext",
    "PromptProjectionTextMutationContextProvider",
    "PromptProjectionTextMutationController",
    "PromptProjectionTextMutationRange",
    "PromptProjectionTextMutationRangeResolver",
    "PromptProjectionTextMutationRequest",
    "PromptTextMutationActions",
]
