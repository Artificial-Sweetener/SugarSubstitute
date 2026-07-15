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

"""Tests for prompt projection session state decisions."""

from __future__ import annotations

from substitute.application.prompt_editor import PromptDocumentService
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


def test_token_collapse_decision_refuses_caret_inside_expanded_token() -> None:
    """Caret positions inside expanded token source should keep it raw."""

    document_view = PromptDocumentService().build_document_view("<lora:midna:1.00>")
    session = PromptProjectionSession(
        expanded_source_range=(0, len(document_view.source_text))
    )

    decision = session.collapse_decision(
        document_view,
        selection_start=5,
        selection_end=5,
    )

    assert decision.collapsed is False
    assert decision.reason == "selection_inside_or_on_boundary"
    assert decision.matching_syntax_span_present is True


def test_token_collapse_decision_collapses_when_caret_moves_before_token() -> None:
    """Caret positions before expanded token source should collapse valid syntax."""

    document_view = PromptDocumentService().build_document_view("x <lora:midna:1.00>")
    session = PromptProjectionSession(
        expanded_source_range=(2, len(document_view.source_text))
    )

    collapsed = session.collapse_if_cursor_left_token(
        document_view,
        selection_start=0,
        selection_end=0,
    )

    assert collapsed is True
    assert session.expanded_source_range is None


def test_token_collapse_decision_collapses_when_caret_moves_after_token() -> None:
    """Caret positions after expanded token source should collapse valid syntax."""

    document_view = PromptDocumentService().build_document_view(
        "<lora:midna:1.00> tail"
    )
    token_end = len("<lora:midna:1.00>")
    session = PromptProjectionSession(expanded_source_range=(0, token_end))

    collapsed = session.collapse_if_cursor_left_token(
        document_view,
        selection_start=len(document_view.source_text),
        selection_end=len(document_view.source_text),
    )

    assert collapsed is True
    assert session.expanded_source_range is None


def test_token_collapse_decision_refuses_caret_on_token_end_boundary() -> None:
    """Caret exactly at token end is currently treated as still inside the token."""

    document_view = PromptDocumentService().build_document_view("<lora:midna:1.00>")
    token_end = len(document_view.source_text)
    session = PromptProjectionSession(expanded_source_range=(0, token_end))

    decision = session.collapse_decision(
        document_view,
        selection_start=token_end,
        selection_end=token_end,
    )

    assert decision.collapsed is False
    assert decision.reason == "selection_inside_or_on_boundary"
    assert decision.matching_syntax_span_present is True
