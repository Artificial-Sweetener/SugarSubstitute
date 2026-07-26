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

"""Define focused presentation ports used while publishing source commits."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF, SignalInstance
from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)

from .freshness_controller import PromptProjectionFreshnessBlockers


class PromptSourceReplacementPointerSink(Protocol):
    """Clear pointer state made invalid by a committed source replacement."""

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Clear pointer state after a committed source replacement."""


class PromptSourceChangeEffectSink(Protocol):
    """Expose source-revision and presentation effects outside core state."""

    textChanged: SignalInstance
    cursorPositionChanged: SignalInstance
    _caret_visibility_prompt_state_revision: int | None

    def font(self) -> QFont:
        """Return the current surface font."""

    def clear_autocomplete_preview_state(self) -> None:
        """Clear autocomplete preview through its authoritative owner."""

    def notify_implicit_parenthesis_authored(self, nesting_depth: int) -> None:
        """Publish authored nested implicit emphasis education."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return active modes that block deferred projection work."""

    def _mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_snapshot: PromptSourceSnapshot,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Publish a committed source identity and its invalidation effects."""

    def _mark_source_edit_horizontal_movement_origin(self) -> None:
        """Make horizontal movement leave same-source wrap affinity after edits."""


class PromptSourceChangeCaretSink(Protocol):
    """Publish caret state after source and projection state change together."""

    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_rect_override: QRectF | None
    _preferred_x: float | None

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> object:
        """Set source cursor and anchor positions through the caret owner."""

    def _set_deferred_source_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Set caret states while wrap reflow remains pending."""

    def _set_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        reset_preferred_x: bool = True,
        caret_rect_override: QRectF | None = None,
        collapse_expanded_token: bool = True,
        reason: str = "generic",
        preserve_unmapped_source_positions: bool = False,
    ) -> None:
        """Publish committed projection caret states."""

    def _sync_editing_session_to_caret_states(self) -> object:
        """Synchronize editing-session positions from current caret states."""

    def _ensure_caret_visible(self) -> None:
        """Ensure the current caret is visible."""

    def _restart_caret_blink_cycle(self) -> None:
        """Restart the caret blink cycle."""


__all__ = [
    "PromptSourceChangeCaretSink",
    "PromptSourceChangeEffectSink",
    "PromptSourceReplacementPointerSink",
]
