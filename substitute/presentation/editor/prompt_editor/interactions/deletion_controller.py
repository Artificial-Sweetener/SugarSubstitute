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

"""Resolve projection-aware deletion into one immutable source intent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Protocol, TypeVar

from substitute.presentation.text_coordinates import TextCoordinateMap

from ..commands.source_service import PromptSourceCommandService
from ..core.editing.source_commands import PromptSourceEditOrigin
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)

TPayload = TypeVar("TPayload")


class PromptDeletionDirection(Enum):
    """Identify which adjacent source boundary a deletion targets."""

    BACKWARD = "backward"
    FORWARD = "forward"


@dataclass(frozen=True, slots=True)
class PromptDeletionContext:
    """Capture the source and projection values needed for one deletion."""

    source_text: str
    cursor_position: int
    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState
    selection: PromptProjectionSelection
    projection_document: PromptProjectionDocument
    focused_token: PromptProjectionToken | None
    focused_token_expanded: bool
    stale_projection_geometry: bool


@dataclass(frozen=True, slots=True)
class PromptDeletionIntent:
    """Describe one exact source deletion or token-expansion interaction."""

    start: int | None = None
    end: int | None = None
    token_to_expand: PromptProjectionToken | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous or invalid deletion outcomes."""

        has_range = self.start is not None or self.end is not None
        if has_range and (self.start is None or self.end is None):
            raise ValueError("A deletion range requires both boundaries.")
        if has_range and self.start is not None and self.end is not None:
            if self.start < 0 or self.end <= self.start:
                raise ValueError("A deletion range must be non-empty and ordered.")
        if has_range == (self.token_to_expand is not None):
            raise ValueError("A deletion intent must select exactly one action.")

    @classmethod
    def delete_range(cls, start: int, end: int) -> "PromptDeletionIntent":
        """Return one exact half-open source deletion."""

        return cls(start=start, end=end)

    @classmethod
    def expand_token(cls, token: PromptProjectionToken) -> "PromptDeletionIntent":
        """Return one structural-token expansion interaction."""

        return cls(token_to_expand=token)


class PromptDeletionContextProvider(Protocol):
    """Provide one immutable view of live deletion state."""

    def deletion_context(self) -> PromptDeletionContext:
        """Return source and projection state captured at one instant."""


class PromptDeletionProjectionEffects(Protocol):
    """Apply projection-only preparation and token expansion effects."""

    def synchronize_deletion_projection(
        self,
        *,
        reason: str,
        cancel_stale_safe_first: bool,
    ) -> None:
        """Make token geometry authoritative before projected deletion."""

    def expand_token_for_deletion(self, token: PromptProjectionToken) -> None:
        """Expand and select one structural token without changing source."""


class PromptDeletionActions(Protocol):
    """Expose direction-specific deletion actions to key decoding."""

    def backspace(self) -> None:
        """Delete the previous source unit."""

    def delete(self) -> None:
        """Delete the next source unit."""


class PromptDeletionResolver:
    """Resolve immutable deletion contexts without mutating editor state."""

    def raw_boundary_intent(
        self,
        context: PromptDeletionContext,
        direction: PromptDeletionDirection,
    ) -> PromptDeletionIntent | None:
        """Return a grapheme deletion that is safe against stale projection."""

        start, end = self.adjacent_grapheme_range(context, direction)
        if start == end or not self._can_use_stale_raw_boundary(context, start, end):
            return None
        return PromptDeletionIntent.delete_range(start, end)

    def projected_intent(
        self,
        context: PromptDeletionContext,
        direction: PromptDeletionDirection,
    ) -> PromptDeletionIntent | None:
        """Resolve one deletion against authoritative projection geometry."""

        token = context.focused_token
        separator_intent = self._separator_edge_intent(context, direction)
        if separator_intent is not None:
            return separator_intent
        adjacent_state = (
            context.projection_document.caret_map.previous_state(context.cursor_state)
            if direction is PromptDeletionDirection.BACKWARD
            else context.projection_document.caret_map.next_state(context.cursor_state)
        )
        if (
            token is not None
            and not context.focused_token_expanded
            and context.cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and adjacent_state.token_id == token.token_id
            and adjacent_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        ):
            return PromptDeletionIntent.delete_range(
                min(adjacent_state.source_position, context.cursor_position),
                max(adjacent_state.source_position, context.cursor_position),
            )
        if token is not None and not context.focused_token_expanded:
            return PromptDeletionIntent.expand_token(token)
        adjacent_position = adjacent_state.source_position
        if (
            direction is PromptDeletionDirection.BACKWARD
            and adjacent_position < context.cursor_position
        ):
            return PromptDeletionIntent.delete_range(
                adjacent_position,
                context.cursor_position,
            )
        if (
            direction is PromptDeletionDirection.FORWARD
            and adjacent_position > context.cursor_position
        ):
            return PromptDeletionIntent.delete_range(
                context.cursor_position,
                adjacent_position,
            )
        return None

    @staticmethod
    def adjacent_grapheme_range(
        context: PromptDeletionContext,
        direction: PromptDeletionDirection,
    ) -> tuple[int, int]:
        """Return the adjacent grapheme range in source coordinates."""

        coordinates = TextCoordinateMap(context.source_text)
        if direction is PromptDeletionDirection.BACKWARD:
            return (
                coordinates.previous_grapheme_boundary(context.cursor_position),
                context.cursor_position,
            )
        return (
            context.cursor_position,
            coordinates.next_grapheme_boundary(context.cursor_position),
        )

    @staticmethod
    def _can_use_stale_raw_boundary(
        context: PromptDeletionContext,
        start: int,
        end: int,
    ) -> bool:
        """Return whether raw deletion can bypass a pending projection flush."""

        if start < 0 or end > len(context.source_text):
            return False
        if context.source_text[start:end] in {"\n", "\r", "\t"}:
            return False
        projection_source_is_stale = (
            context.projection_document.source_text != context.source_text
        )
        return bool(
            (projection_source_is_stale or context.stale_projection_geometry)
            and context.cursor_state.token_id is None
            and context.anchor_state.token_id is None
        )

    @staticmethod
    def _separator_edge_intent(
        context: PromptDeletionContext,
        direction: PromptDeletionDirection,
    ) -> PromptDeletionIntent | None:
        """Return the single-bracket edit that invalidates a separator token."""

        token = context.focused_token
        if (
            token is None
            or token.kind is not PromptProjectionTokenKind.REGION_SEPARATOR
        ):
            return None
        if (
            direction is PromptDeletionDirection.BACKWARD
            and context.cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
        ):
            return PromptDeletionIntent.delete_range(
                token.source_end - 1,
                token.source_end,
            )
        if (
            direction is PromptDeletionDirection.FORWARD
            and context.cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
        ):
            return PromptDeletionIntent.delete_range(
                token.source_start,
                token.source_start + 1,
            )
        return None


class PromptSurfaceDeletionController(Generic[TPayload]):
    """Submit one resolved deletion through the focused source command owner."""

    def __init__(
        self,
        *,
        context_provider: PromptDeletionContextProvider,
        projection_effects: PromptDeletionProjectionEffects,
        source_commands: PromptSourceCommandService[TPayload],
        resolver: PromptDeletionResolver | None = None,
    ) -> None:
        """Store focused read, projection-effect, and source-command owners."""

        self._context_provider = context_provider
        self._projection_effects = projection_effects
        self._source_commands = source_commands
        self._resolver = resolver if resolver is not None else PromptDeletionResolver()

    def backspace(self) -> None:
        """Delete the previous grapheme, selection, or structural edge."""

        self._delete(PromptDeletionDirection.BACKWARD)

    def delete(self) -> None:
        """Delete the next grapheme, selection, or structural edge."""

        self._delete(PromptDeletionDirection.FORWARD)

    def _delete(self, direction: PromptDeletionDirection) -> None:
        """Resolve and apply one direction-specific deletion interaction."""

        context = self._context_provider.deletion_context()
        reason = (
            "backspace" if direction is PromptDeletionDirection.BACKWARD else "delete"
        )
        if not context.selection.is_empty:
            self._projection_effects.synchronize_deletion_projection(
                reason=reason,
                cancel_stale_safe_first=False,
            )
            self._apply_intent(
                PromptDeletionIntent.delete_range(
                    context.selection.start,
                    context.selection.end,
                ),
                command_name=f"{reason}_selection",
            )
            return
        at_boundary = (
            context.cursor_position <= 0
            if direction is PromptDeletionDirection.BACKWARD
            else context.cursor_position >= len(context.source_text)
        )
        if at_boundary:
            self._projection_effects.synchronize_deletion_projection(
                reason=f"{reason}_at_{'start' if direction is PromptDeletionDirection.BACKWARD else 'end'}",
                cancel_stale_safe_first=False,
            )
            return
        raw_intent = self._resolver.raw_boundary_intent(context, direction)
        if raw_intent is not None:
            self._apply_intent(raw_intent, command_name=reason)
            return
        self._projection_effects.synchronize_deletion_projection(
            reason=reason,
            cancel_stale_safe_first=True,
        )
        projected_intent = self._resolver.projected_intent(
            self._context_provider.deletion_context(),
            direction,
        )
        if projected_intent is not None:
            self._apply_intent(projected_intent, command_name=reason)

    def _apply_intent(
        self,
        intent: PromptDeletionIntent,
        *,
        command_name: str,
    ) -> None:
        """Apply exactly one source command or one projection expansion."""

        token = intent.token_to_expand
        if token is not None:
            self._projection_effects.expand_token_for_deletion(token)
            return
        if intent.start is None or intent.end is None:
            raise RuntimeError("Resolved source deletion is missing its range.")
        self._source_commands.replace_source_range(
            start=intent.start,
            end=intent.end,
            replacement_text="",
            origin=PromptSourceEditOrigin.TYPED,
            command_name=command_name,
            finish_pending_key_edits=False,
        )


__all__ = [
    "PromptDeletionContext",
    "PromptDeletionContextProvider",
    "PromptDeletionActions",
    "PromptDeletionDirection",
    "PromptDeletionIntent",
    "PromptDeletionProjectionEffects",
    "PromptDeletionResolver",
    "PromptSurfaceDeletionController",
]
