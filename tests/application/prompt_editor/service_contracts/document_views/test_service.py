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
    blank_line_drop_offsets,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)


def test_prompt_document_service_builds_one_document_view_with_all_prompt_data() -> (
    None
):
    """Document views should expose segment, emphasis, syntax, and comma metadata together."""

    document_service = PromptDocumentService()

    document_view = document_service.build_document_view("alpha, ((cat:1.2) dog:1.1), ")

    assert document_view.source_text == "alpha, ((cat:1.2) dog:1.1), "
    assert document_view.has_trailing_comma is True
    assert [segment.display_text for segment in document_view.segments] == [
        "alpha",
        "((cat:1.2) dog:1.1)",
    ]
    assert [
        (span.kind, span.start, span.end, span.depth)
        for span in document_view.syntax_spans
    ] == [  # noqa: E501
        ("emphasis", 7, 26, 0),
        ("emphasis", 8, 17, 1),
    ]
    assert [
        (span.content_start, span.content_end, span.weight_text, span.depth)
        for span in document_view.emphasis_spans
    ] == [
        (8, 21, "1.1", 0),
        (9, 12, "1.2", 1),
    ]


def test_prompt_document_service_public_parse_and_projection_apis_round_trip_documents() -> (
    None
):
    """Public parse and projection APIs should rebuild the same immutable prompt snapshot."""

    document_service = PromptDocumentService()

    document = document_service.parse_document('alpha, "cat, dog", [bird, fish]')
    document_view = document_service.build_document_view_from_document(document)

    assert document.source_text == 'alpha, "cat, dog", [bird, fish]'
    assert document_view.source_text == document.source_text
    assert [segment.display_text for segment in document_view.segments] == [
        "alpha",
        '"cat, dog"',
        "[bird, fish]",
    ]


def test_prompt_document_service_projects_wildcard_views_from_domain_document() -> None:
    """Document views should expose parsed wildcard spans without leaking domain types."""

    document_service = PromptDocumentService()

    document_view = document_service.build_document_view(
        "({animal}:1.05), {csv:monster:color}"
    )

    assert [
        (
            span.outer_start,
            span.outer_end,
            span.wildcard_form,
            span.identifier,
            span.csv_column,
        )
        for span in document_view.wildcard_spans
    ] == [
        (1, 9, "simple", "animal", None),
        (17, 36, "csv", "monster", "color"),
    ]


def test_prompt_document_service_queries_positions_from_existing_document_view() -> (
    None
):
    """Position queries should inspect one cached application view instead of reparsing text."""

    document_service = PromptDocumentService()
    segment_document_view = document_service.build_document_view("red, blue, green")
    emphasis_document_view = document_service.build_document_view("((cat:1.2) dog:1.1)")

    segment = document_service.segment_at_position(segment_document_view, 6)
    emphasis = document_service.emphasis_at_position(emphasis_document_view, 3)

    assert segment is not None
    assert (
        segment.index,
        segment.display_text,
        segment.selection_start,
        segment.selection_end,
    ) == (1, "blue", 5, 9)
    assert emphasis is not None
    assert (
        emphasis.content_start,
        emphasis.content_end,
        emphasis.weight_text,
        emphasis.depth,
    ) == (2, 5, "1.2", 1)


def test_prompt_document_service_builds_chip_ready_segment_views_from_document_view() -> (
    None
):
    """Reorder chip views should preserve current trailing-comma intent."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha,beta,")

    segments = document_service.reorder_chips(document_view)

    assert [
        (segment.display_text, segment.has_separator_after) for segment in segments
    ] == [("alpha", True), ("beta", True)]


def test_prompt_document_service_splits_multi_tag_emphasis_shell_into_reorder_chips() -> (
    None
):
    """Exact chip-spanning emphasis shells should expose one chip per inner prompt tag."""

    document_service = PromptDocumentService()
    chips = document_service.reorder_chips(
        document_service.build_document_view("(1girl, solo:1.20)")
    )

    assert [chip.display_text for chip in chips] == ["1girl", "solo"]
    assert [chip.serialized_text for chip in chips] == [
        "(1girl:1.20)",
        "(solo:1.20)",
    ]


def test_prompt_document_service_preview_snapshot_preserves_grouped_emphasis_shell_text() -> (
    None
):
    """Preview serialization should keep adjacent emphasis chips grouped under one shell."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("(1girl, solo:1.20)")
    layout_view = document_service.build_reorder_layout_view(document_view)

    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        layout_view,
    )

    assert preview_snapshot.text == "(1girl, solo:1.20)"
    assert preview_snapshot.chip_ranges_by_index == {
        0: (1, 6),
        1: (8, 12),
    }
    assert preview_snapshot.chip_owned_ranges_by_index == {
        0: ((0, 6), (6, 8)),
        1: ((8, 18),),
    }


def test_prompt_document_service_preview_snapshot_exposes_chip_owned_ranges_without_disturbing_gaps() -> (
    None
):
    """Preview snapshots should carry explicit chip ownership alongside stable gap bookkeeping."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha,\n\nbeta, gamma")
    layout_view = document_service.build_reorder_layout_view(document_view)

    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        layout_view,
    )

    assert preview_snapshot.chip_owned_ranges_by_index == {
        0: ((0, 5), (5, 8)),
        1: ((8, 12), (12, 14)),
        2: ((14, 19),),
    }
    assert preview_snapshot.gap_ranges_by_index == {0: (5, 8)}


def test_prompt_document_service_preview_snapshot_preserves_owned_ranges_for_split_grouped_emphasis_chips() -> (
    None
):
    """Split grouped-emphasis preview snapshots should keep shell ownership explicit per chip."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("(1girl, solo:1.20), blush")
    layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        layout_view,
    )

    assert preview_snapshot.text == "(1girl:1.20), blush, (solo:1.20)"
    assert preview_snapshot.chip_owned_ranges_by_index == {
        0: ((0, 12), (12, 14)),
        2: ((14, 19), (19, 21)),
        1: ((21, 32),),
    }


def test_prompt_document_service_projects_exact_display_source_bounds_for_trimmed_segments() -> (
    None
):
    """Segment views should expose exact stripped source bounds for rich segment rendering."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("  (cat:1.20)  , beta")

    first_segment = document_view.segments[0]
    second_segment = document_view.segments[1]

    assert (
        first_segment.display_source_start,
        first_segment.display_source_end,
    ) == (2, 12)
    assert (
        document_view.source_text[
            first_segment.display_source_start : first_segment.display_source_end
        ]
        == "(cat:1.20)"
    )
    assert (
        second_segment.display_source_start,
        second_segment.display_source_end,
    ) == (16, 20)
    assert (
        document_view.source_text[
            second_segment.display_source_start : second_segment.display_source_end
        ]
        == "beta"
    )


def test_prompt_document_service_builds_chip_separator_metadata_for_final_segment() -> (
    None
):
    """Reorder chip views should distinguish final segments with and without commas."""

    document_service = PromptDocumentService()

    no_trailing_comma = document_service.reorder_chips(
        document_service.build_document_view("alpha, beta")
    )
    trailing_comma = document_service.reorder_chips(
        document_service.build_document_view("alpha, beta,")
    )

    assert [segment.has_separator_after for segment in no_trailing_comma] == [
        True,
        False,
    ]
    assert [segment.has_separator_after for segment in trailing_comma] == [True, True]


def test_prompt_document_service_preserves_exact_separator_text_for_reorder_views() -> (
    None
):
    """Reorder views should keep the exact separator text, including newline whitespace."""

    document_service = PromptDocumentService()
    segments = document_service.reorder_chips(
        document_service.build_document_view("alpha,\n beta, gamma")
    )

    assert [segment.separator_text_after for segment in segments] == [",\n ", ", ", ""]


def test_prompt_document_service_exposes_blank_line_offsets_for_multiline_separators() -> (
    None
):
    """Blank-line helper should expose each empty row inside a multiline separator."""

    document_service = PromptDocumentService()
    segments = document_service.reorder_chips(
        document_service.build_document_view("alpha,\n\n\n\n\nbeta")
    )

    assert blank_line_drop_offsets(segments[0].separator_text_after) == (
        2,
        3,
        4,
        5,
    )


def test_prompt_document_service_does_not_treat_region_markers_as_blank_targets() -> (
    None
):
    """Structural separator rows must not become empty-row drag destinations."""

    assert blank_line_drop_offsets("\n[SEP]\n") == ()
    assert blank_line_drop_offsets("\n\n[SEP]\n\n") == (1, 8)


def test_prompt_document_service_builds_row_gap_layout_views_from_multiline_prompts() -> (
    None
):
    """Reorder layout views should expose derived rows and newline gaps deterministically."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta,\n\ngamma, delta")

    layout_view = document_service.build_reorder_layout_view(document_view)

    assert layout_view == PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0, 1)),
            PromptReorderRowView(row_index=1, chip_indices=(2, 3)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )


def test_prompt_document_service_builds_base_drag_layout_view_from_hidden_segment_state() -> (
    None
):
    """Base-drag layout views should come from the hidden-segment separator-slot state."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("a, b, c,\nd, e, f")

    base_drag_layout = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )

    assert base_drag_layout == PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0, 2)),
            PromptReorderRowView(row_index=1, chip_indices=(3, 4, 5)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n",
                blank_line_count=0,
            ),
        ),
    )
