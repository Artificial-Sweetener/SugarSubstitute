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

"""Resolve bounded projection facts consumed by source-edit policy."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)

from .source_edit_projection_policy import PromptSourceEditProjectionPolicy
from .source_edit_syntax import is_deferred_syntax_autocomplete_prefix


class PromptEditFactResolver:
    """Derive edit-policy facts from immutable projection state and blockers."""

    def __init__(
        self,
        policy: PromptSourceEditProjectionPolicy | None = None,
    ) -> None:
        """Store the stateless policy that owns source-edit rules."""

        self._policy = policy or PromptSourceEditProjectionPolicy()

    def typed_character_requires_projection(
        self,
        character: str,
        *,
        start: int,
        end: int,
        document: PromptProjectionDocument,
        cursor_state: PromptProjectionCaretState,
        display_mode: PromptProjectionDisplayMode,
        reorder_preview_active: bool,
        expanded_source_range_active: bool,
        exact_weight_edit_active: bool,
    ) -> bool:
        """Return whether one character changes immediate projection semantics."""

        focused_token = document.token_by_id(cursor_state.token_id)
        comma_requires_projection = (
            start != end
            or display_mode is not PromptProjectionDisplayMode.PROJECTED
            or reorder_preview_active
            or expanded_source_range_active
            or exact_weight_edit_active
            or (
                focused_token is not None
                and focused_token.source_start < start < focused_token.source_end
            )
        )
        return self._policy.typed_character_requires_projection(
            character,
            comma_requires_projection=comma_requires_projection,
        )

    def can_defer_syntax_autocomplete_prefix(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
        document: PromptProjectionDocument,
        cursor_state: PromptProjectionCaretState,
    ) -> bool:
        """Return whether syntax text remains an incomplete LoRA prefix."""

        focused_token = document.token_by_id(cursor_state.token_id)
        focused_token_range = (
            None
            if focused_token is None
            else (focused_token.source_start, focused_token.source_end)
        )
        return is_deferred_syntax_autocomplete_prefix(
            start=start,
            end=end,
            replacement_text=replacement_text,
            normalized_text=normalized_text,
            focused_token_range=focused_token_range,
        )

    def source_range_intersects_tokens(
        self,
        *,
        start: int,
        end: int,
        document: PromptProjectionDocument,
    ) -> bool:
        """Return whether one source range touches projected token syntax."""

        return self._policy.source_range_intersects_tokens(
            start=start,
            end=end,
            tokens=document.tokens,
        )

    def source_insertion_is_inside_token(
        self,
        source_position: int,
        *,
        document: PromptProjectionDocument,
    ) -> bool:
        """Return whether one insertion sits inside projected token syntax."""

        return self._policy.source_insertion_is_inside_token(
            source_position=source_position,
            tokens=document.tokens,
        )
