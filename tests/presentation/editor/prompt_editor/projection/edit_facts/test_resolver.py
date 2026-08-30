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

"""Tests for bounded prompt edit fact resolution."""

from __future__ import annotations

from dataclasses import replace

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.edit_fact_resolver import (
    PromptEditFactResolver,
)


def _document_with_token() -> PromptProjectionDocument:
    """Return a minimal document with one focused projected token."""

    token = PromptProjectionToken(
        token_id="token",
        kind=PromptProjectionTokenKind.LORA,
        source_start=4,
        source_end=12,
        display_text="lora",
    )
    return replace(PromptProjectionDocument.empty(), tokens=(token,))


def test_edit_fact_resolver_keeps_plain_comma_fast_outside_tokens() -> None:
    """A plain comma insertion should remain eligible for deferred projection."""

    assert not PromptEditFactResolver().typed_character_requires_projection(
        ",",
        start=2,
        end=2,
        document=_document_with_token(),
        cursor_state=PromptProjectionCaretState(source_position=2),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        reorder_preview_active=False,
        expanded_source_range_active=False,
        exact_weight_edit_active=False,
    )


def test_edit_fact_resolver_forces_comma_inside_focused_token() -> None:
    """A comma inside focused syntax should require immediate projection."""

    assert PromptEditFactResolver().typed_character_requires_projection(
        ",",
        start=8,
        end=8,
        document=_document_with_token(),
        cursor_state=PromptProjectionCaretState(
            source_position=8,
            token_id="token",
        ),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        reorder_preview_active=False,
        expanded_source_range_active=False,
        exact_weight_edit_active=False,
    )


def test_edit_fact_resolver_forces_comma_when_projection_mode_is_blocked() -> None:
    """Reorder preview should prevent comma edits from remaining deferred."""

    assert PromptEditFactResolver().typed_character_requires_projection(
        ",",
        start=2,
        end=2,
        document=_document_with_token(),
        cursor_state=PromptProjectionCaretState(source_position=2),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        reorder_preview_active=True,
        expanded_source_range_active=False,
        exact_weight_edit_active=False,
    )


def test_edit_fact_resolver_uses_focused_token_for_prefix_and_intersection() -> None:
    """Focused-token and document-token queries should share one bounded owner."""

    resolver = PromptEditFactResolver()
    document = _document_with_token()
    cursor_state = PromptProjectionCaretState(
        source_position=8,
        token_id="token",
    )

    assert not resolver.can_defer_syntax_autocomplete_prefix(
        start=8,
        end=8,
        replacement_text=":",
        normalized_text="<lora:x:",
        document=document,
        cursor_state=cursor_state,
    )
    assert resolver.source_range_intersects_tokens(
        start=3,
        end=5,
        document=document,
    )
    assert resolver.source_insertion_is_inside_token(8, document=document)
