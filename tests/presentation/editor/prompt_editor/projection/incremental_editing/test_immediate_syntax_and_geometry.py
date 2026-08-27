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

"""Tests for prompt projection incremental editing surface behavior."""

from __future__ import annotations

from typing import Any, cast


import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    apply_source_range_to_projection,
    install_lora_wildcard_prompt_state,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    projection_token_kinds,
    valid_transient_insertion_overlay,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
)


def test_projection_surface_caret_move_clears_stale_active_lora_paint(
    widgets: list[QWidget],
) -> None:
    """Caret movement should update active projection paint before source edits."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 260)
    widgets.append(surface)
    text = "1girl\n\n<lora:Anima\\style\\People:1.00>"
    plain_tag_end = len("1girl")
    install_lora_wildcard_prompt_state(surface, text)

    def active_layout_token_ranges() -> tuple[tuple[int, int], ...]:
        """Return active token ranges from layout-owned paint state."""

        layout = cast(Any, surface)._layout
        active_token_ids = layout.frame.paint_state.active_token_ids
        return tuple(
            (token.source_start, token.source_end)
            for token in layout.frame.output.projection_document.tokens
            if token.token_id in active_token_ids
        )

    assert active_layout_token_ranges() == ((len("1girl\n\n"), len(text)),)

    surface.set_cursor_positions(
        cursor_position=plain_tag_end,
        anchor_position=plain_tag_end,
    )

    assert active_layout_token_ranges() == ()


def test_projection_surface_immediate_syntax_insert_preserves_unaffected_semantics(
    widgets: list[QWidget],
) -> None:
    """Immediate syntax-sensitive typing should not blank unrelated decorations."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "(cat:1.05), {animal}, <lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )

    next_text = f"{text}<"
    apply_source_range_to_projection(
        surface,
        next_text,
        source_edit_start=len(text),
        source_edit_end=len(text),
        source_edit_replacement_text="<",
    )

    assert surface.projection_document().source_text == next_text
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )


def test_projection_surface_immediate_delete_preserves_shifted_semantics(
    widgets: list[QWidget],
) -> None:
    """Immediate backspace/delete before decorations should remap them in place."""

    ensure_qapp()
    surface = new_projection_surface()
    surface.resize(520, 180)
    widgets.append(surface)
    text = "x, {animal}, <lora:midna:1>, tail"
    install_lora_wildcard_prompt_state(surface, text)
    original_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )

    next_text = text[1:]
    apply_source_range_to_projection(
        surface,
        next_text,
        source_edit_start=0,
        source_edit_end=1,
        source_edit_replacement_text="",
    )

    shifted_lora_token = next(
        token
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )
    assert surface.projection_document().source_text == next_text
    assert projection_token_kinds(surface) == (
        PromptProjectionTokenKind.WILDCARD,
        PromptProjectionTokenKind.LORA,
    )
    assert shifted_lora_token.source_start == original_lora_token.source_start - 1
    assert shifted_lora_token.source_end == original_lora_token.source_end - 1


def test_projection_surface_middle_insert_before_blank_line_reflows_immediately(
    widgets: list[QWidget],
) -> None:
    """Middle insertion before a blank line should publish real caret geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n\nomega",
        width=360,
    )
    surface = surface_for(box)
    surface.set_cursor_positions(cursor_position=5, anchor_position=5)
    before_rect = surface._current_caret_document_rect()  # noqa: SLF001

    surface.textCursor().insertText("x")

    after_rect = surface._current_caret_document_rect()  # noqa: SLF001
    assert surface.toPlainText() == "alphax\n\nomega"
    assert surface.has_stale_projection_geometry() is False
    assert valid_transient_insertion_overlay(surface) is None
    assert after_rect.top() == pytest.approx(before_rect.top())
    assert after_rect.left() > before_rect.left()
