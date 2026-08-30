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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)


def test_prompt_mutation_service_returns_refreshed_document_view_after_emphasis_increase() -> (
    None
):
    """Emphasis increases should return editor data plus refreshed prompt semantics."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis(
        "cat",
        selection_start=0,
        selection_end=3,
        delta=0.05,
    )

    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.05)", 1, 4, "(cat:1.05)")
    assert len(result.document_view.emphasis_spans) == 1
    assert result.document_view.emphasis_spans[0].weight_text == "1.05"


def test_prompt_mutation_service_returns_refreshed_document_view_after_emphasis_decrease() -> (
    None
):
    """Emphasis decreases should update both text and the returned semantic snapshot."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis(
        "(cat:1.20)",
        selection_start=1,
        selection_end=4,
        delta=-0.05,
    )

    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.15)", 1, 4, "(cat:1.15)")
    assert len(result.document_view.emphasis_spans) == 1
    assert result.document_view.emphasis_spans[0].weight_text == "1.15"


def test_prompt_mutation_service_adjusts_emphasis_for_exact_outer_range_increase() -> (
    None
):
    """Outer-range targeting should increase only the matched emphasis span."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis_for_outer_range(
        "(cat:1.05)",
        outer_start=0,
        outer_end=10,
        delta=0.05,
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.10)", 1, 4, "(cat:1.10)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.10"


def test_prompt_mutation_service_adjusts_emphasis_for_exact_outer_range_decrease() -> (
    None
):
    """Outer-range targeting should decrease the matched emphasis shell."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis_for_outer_range(
        "(cat:1.20)",
        outer_start=0,
        outer_end=10,
        delta=-0.05,
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.15)", 1, 4, "(cat:1.15)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.15"


def test_prompt_mutation_service_adjusts_emphasis_for_exact_outer_range_unwrap() -> (
    None
):
    """Outer-range targeting should unwrap shells that return to neutral weight."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis_for_outer_range(
        "(cat:1.05)",
        outer_start=0,
        outer_end=10,
        delta=-0.05,
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("cat", 0, 3, "cat")
    assert result.document_view.emphasis_spans == ()


def test_prompt_mutation_service_adjust_emphasis_for_outer_range_returns_none_for_stale_range() -> (
    None
):
    """Missing outer ranges should fail closed without mutating the prompt."""

    mutation_service = PromptMutationService()

    result = mutation_service.adjust_emphasis_for_outer_range(
        "(cat:1.05)",
        outer_start=0,
        outer_end=9,
        delta=0.05,
    )

    assert result is None


def test_prompt_mutation_service_adjusts_only_requested_nested_outer_range() -> None:
    """Nested outer-range targeting should mutate only the matched emphasis span."""

    document_service = PromptDocumentService()
    mutation_service = PromptMutationService()
    document_view = document_service.build_document_view("((cat:1.20) dog:1.10)")
    inner_span = document_view.emphasis_spans[1]

    result = mutation_service.adjust_emphasis_for_outer_range(
        document_view.source_text,
        outer_start=inner_span.outer_start,
        outer_end=inner_span.outer_end,
        delta=0.05,
    )

    assert result is not None
    assert result.text == "((cat:1.25) dog:1.10)"
    assert [
        (span.weight_text, span.depth) for span in result.document_view.emphasis_spans
    ] == [("1.10", 0), ("1.25", 1)]
