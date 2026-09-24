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

"""Own mutable projected-caret state and visual navigation affinity."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)


class PromptProjectionCaretStateOwner:
    """Keep cursor, anchor, column, affinity, and one-shot movement state coherent."""

    def __init__(self, initial_state: PromptProjectionCaretState) -> None:
        """Create collapsed caret state at one projection-backed position."""
        self._cursor_state = initial_state
        self._anchor_state = initial_state
        self._preferred_x: float | None = None
        self._caret_rect_override: QRectF | None = None
        self._skip_next_same_source_soft_wrap_move = False

    @property
    def cursor_state(self) -> PromptProjectionCaretState:
        """Return the current projection-backed cursor state."""
        return self._cursor_state

    @property
    def anchor_state(self) -> PromptProjectionCaretState:
        """Return the current projection-backed selection anchor state."""
        return self._anchor_state

    @property
    def preferred_x(self) -> float | None:
        """Return the preserved visual column for vertical movement."""
        return self._preferred_x

    @property
    def caret_rect_override(self) -> QRectF | None:
        """Return the current visual-affinity rect, if logical geometry differs."""
        if self._caret_rect_override is None:
            return None
        return QRectF(self._caret_rect_override)

    def matches(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        caret_rect_override: QRectF | None,
    ) -> bool:
        """Return whether one complete requested caret publication is current."""
        return bool(
            self._cursor_state == cursor_state
            and self._anchor_state == anchor_state
            and self._caret_rect_override == caret_rect_override
        )

    def publish(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        caret_rect_override: QRectF | None,
        reset_preferred_x: bool,
    ) -> None:
        """Publish one interaction-resolved caret state and consume edit affinity."""
        self._cursor_state = cursor_state
        self._anchor_state = anchor_state
        self._caret_rect_override = (
            QRectF(caret_rect_override) if caret_rect_override is not None else None
        )
        if reset_preferred_x:
            self._preferred_x = None
        self._skip_next_same_source_soft_wrap_move = False

    def replace_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        clear_caret_rect_override: bool,
        reset_preferred_x: bool,
    ) -> None:
        """Replace source-driven states while preserving unrelated movement affinity."""
        self._cursor_state = cursor_state
        self._anchor_state = anchor_state
        if clear_caret_rect_override:
            self._caret_rect_override = None
        if reset_preferred_x:
            self._preferred_x = None

    def clear_visual_affinity(self, *, reset_preferred_x: bool) -> None:
        """Discard geometry that cannot survive a layout or viewport transition."""
        self._caret_rect_override = None
        if reset_preferred_x:
            self._preferred_x = None

    def set_preferred_x(self, preferred_x: float | None) -> None:
        """Retain the visual column used by successive vertical moves."""
        self._preferred_x = preferred_x

    def mark_source_edit_horizontal_movement_origin(self) -> None:
        """Make the next horizontal move consume same-source wrap affinity."""
        self._skip_next_same_source_soft_wrap_move = True

    def consume_source_edit_horizontal_movement_origin(self) -> bool:
        """Return and clear the one-shot same-source wrap movement marker."""
        skip = self._skip_next_same_source_soft_wrap_move
        self._skip_next_same_source_soft_wrap_move = False
        return skip

    def source_edit_horizontal_movement_origin_is_pending(self) -> bool:
        """Return whether an edit-origin horizontal movement marker is pending."""
        return self._skip_next_same_source_soft_wrap_move


__all__ = ["PromptProjectionCaretStateOwner"]
