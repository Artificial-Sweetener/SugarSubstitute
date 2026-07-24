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

"""Own projection-aware Backspace and Delete source mutations."""

from __future__ import annotations

from typing import Protocol

from substitute.presentation.text_coordinates import TextCoordinateMap

from ..projection.freshness_controller import PromptProjectionFreshnessController
from ..projection.model import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionDocument,
    PromptProjectionSelection,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from ..projection.session import PromptProjectionSession


class PromptSurfaceDeletionHost(Protocol):
    """Expose source and projection state required by deletion semantics."""

    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _session: PromptProjectionSession
    _projection_freshness_controller: PromptProjectionFreshnessController

    @property
    def cursor_position(self) -> int:
        """Return the current source cursor boundary."""
        ...

    def toPlainText(self) -> str:
        """Return the exact current prompt source."""
        ...

    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed projection document."""
        ...

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token owning the current logical caret state."""
        ...

    def _selection(self) -> PromptProjectionSelection:
        """Return the current projection selection."""
        ...

    def _delete_viewport_selection(self) -> None:
        """Delete the selected source through the canonical mutation boundary."""
        ...

    def _replace_viewport_range(self, start: int, end: int, text: str) -> None:
        """Replace one exact source range through the canonical edit command."""
        ...

    def _flush_pending_projection_update(self, *, reason: str) -> None:
        """Commit pending projection work before token-sensitive deletion."""
        ...

    def _cancel_stale_safe_projection_update(self, *, reason: str) -> bool:
        """Cancel stale-safe projection work when raw deletion remains safe."""
        ...

    def _rebuild_projection(self) -> None:
        """Rebuild projection after expanding an existing inline token."""
        ...

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> object:
        """Persist source-backed cursor and anchor positions."""
        ...


class PromptSurfaceDeletionController:
    """Apply grapheme-safe deletion with explicit structural-token edge behavior."""

    def __init__(self, host: PromptSurfaceDeletionHost) -> None:
        """Bind deletion behavior to one prompt surface effect sink."""

        self._host = host

    def backspace(self) -> None:
        """Delete the previous raw source boundary or selection."""

        host = self._host
        selection = host._selection()
        if not selection.is_empty:
            host._flush_pending_projection_update(reason="backspace")
            host._delete_viewport_selection()
            return
        if host.cursor_position <= 0:
            host._flush_pending_projection_update(reason="backspace_at_start")
            return
        previous_grapheme_boundary = TextCoordinateMap(
            host.toPlainText()
        ).previous_grapheme_boundary(host.cursor_position)
        if self._can_delete_raw_boundary_from_stale_projection(
            start=previous_grapheme_boundary,
            end=host.cursor_position,
        ):
            host._replace_viewport_range(
                previous_grapheme_boundary,
                host.cursor_position,
                "",
            )
            return
        if not host._cancel_stale_safe_projection_update(reason="backspace"):
            host._flush_pending_projection_update(reason="backspace")
        token = host.focused_token()
        if self._delete_region_separator_trailing_edge(token):
            return
        previous_state = host.projection_document().caret_map.previous_state(
            host._cursor_state
        )
        if (
            token is not None
            and not host._session.is_expanded(token)
            and host._cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and previous_state.token_id == token.token_id
            and previous_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        ):
            host._replace_viewport_range(
                previous_state.source_position,
                host.cursor_position,
                "",
            )
            return
        if token is not None and not host._session.is_expanded(token):
            host._session.expand_token(token)
            host._rebuild_projection()
            host.set_cursor_positions(
                cursor_position=token.source_end,
                anchor_position=token.source_start,
            )
            return
        if previous_state.source_position >= host.cursor_position:
            return
        host._replace_viewport_range(
            previous_state.source_position,
            host.cursor_position,
            "",
        )

    def delete(self) -> None:
        """Delete the next raw source boundary or selection."""

        host = self._host
        selection = host._selection()
        if not selection.is_empty:
            host._flush_pending_projection_update(reason="delete")
            host._delete_viewport_selection()
            return
        if host.cursor_position >= len(host.toPlainText()):
            host._flush_pending_projection_update(reason="delete_at_end")
            return
        next_grapheme_boundary = TextCoordinateMap(
            host.toPlainText()
        ).next_grapheme_boundary(host.cursor_position)
        if self._can_delete_raw_boundary_from_stale_projection(
            start=host.cursor_position,
            end=next_grapheme_boundary,
        ):
            host._replace_viewport_range(
                host.cursor_position,
                next_grapheme_boundary,
                "",
            )
            return
        if not host._cancel_stale_safe_projection_update(reason="delete"):
            host._flush_pending_projection_update(reason="delete")
        token = host.focused_token()
        if self._delete_region_separator_leading_edge(token):
            return
        next_state = host.projection_document().caret_map.next_state(host._cursor_state)
        if (
            token is not None
            and not host._session.is_expanded(token)
            and host._cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and next_state.token_id == token.token_id
            and next_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        ):
            host._replace_viewport_range(
                host.cursor_position,
                next_state.source_position,
                "",
            )
            return
        if token is not None and not host._session.is_expanded(token):
            host._session.expand_token(token)
            host._rebuild_projection()
            host.set_cursor_positions(
                cursor_position=token.source_end,
                anchor_position=token.source_start,
            )
            return
        if next_state.source_position <= host.cursor_position:
            return
        host._replace_viewport_range(
            host.cursor_position,
            next_state.source_position,
            "",
        )

    def _delete_region_separator_trailing_edge(
        self,
        token: PromptProjectionToken | None,
    ) -> bool:
        """Delete only `]` when Backspace targets a separator's trailing edge."""

        host = self._host
        if (
            token is None
            or token.kind is not PromptProjectionTokenKind.REGION_SEPARATOR
            or host._cursor_state.placement
            is not PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
        ):
            return False
        host._replace_viewport_range(token.source_end - 1, token.source_end, "")
        return True

    def _delete_region_separator_leading_edge(
        self,
        token: PromptProjectionToken | None,
    ) -> bool:
        """Delete only `[` when Delete targets a separator's leading edge."""

        host = self._host
        if (
            token is None
            or token.kind is not PromptProjectionTokenKind.REGION_SEPARATOR
            or host._cursor_state.placement
            is not PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
        ):
            return False
        host._replace_viewport_range(token.source_start, token.source_start + 1, "")
        return True

    def _can_delete_raw_boundary_from_stale_projection(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether deletion can avoid flushing a pending projection first."""

        host = self._host
        source_text = host.toPlainText()
        if start < 0 or end > len(source_text):
            return False
        if source_text[start:end] in {"\n", "\r", "\t"}:
            return False
        projection_source_is_stale = (
            host.projection_document().source_text != source_text
        )
        return bool(
            (
                projection_source_is_stale
                or host._projection_freshness_controller.has_stale_projection_geometry()
            )
            and host._cursor_state.token_id is None
            and host._anchor_state.token_id is None
        )


__all__ = ["PromptSurfaceDeletionController", "PromptSurfaceDeletionHost"]
