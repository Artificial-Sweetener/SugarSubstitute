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

import pytest

from substitute.application.prompt_editor import (
    autocomplete_replacement_text,
    clear_prompt_document_caches,
    clear_prompt_scene_projection_cache,
    clear_prompt_syntax_render_plan_cache,
    effective_prompt_text_at_source_position,
    filter_noop_autocomplete_suggestions,
    parse_prompt_scene_projection_document,
    PromptAdjustEmphasisAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptConsumeSyntaxAction,
    PromptDocumentService,
    PromptEmphasisRendererView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptLoraAutocompleteQuery,
    PromptLoraAutocompleteService,
    PromptLoraCatalogItem,
    PromptLoraResolutionStatus,
    PromptLoraThumbnailVariant,
    PromptLoraRendererView,
    PromptMutationService,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptSyntaxService,
    PromptSyntaxProfileService,
    PromptWildcardRendererView,
    prompt_syntax_profile_from_feature_profile,
    blank_line_drop_offsets,
)
from substitute.application.prompt_editor.prompt_syntax_service import (
    _lora_render_plan_summary,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.domain.prompt import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
)


def test_prompt_syntax_profile_from_feature_profile_enables_lora_syntax() -> None:
    """LoRA renderer support should come from the split LoRA syntax feature."""

    profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.LORA_SYNTAX,
                enabled=True,
            ),
        )
    )

    syntax_profile = prompt_syntax_profile_from_feature_profile(profile)

    assert syntax_profile.supports("lora")


class _StaticPromptWildcardCatalogGateway:
    """Return deterministic wildcard resolution rows for prompt syntax-service tests."""

    def __init__(
        self,
        resolutions_by_reference: dict[
            tuple[str, str, str | None],
            PromptWildcardResolution,
        ],
    ) -> None:
        """Store fixed wildcard resolution rows keyed by reference shape."""

        self._resolutions_by_reference = dict(resolutions_by_reference)
        self.calls: list[tuple[PromptWildcardReference, ...]] = []
        self.cache_revision = 0

    def bump_revision(self) -> None:
        """Advance the fake catalog revision used by syntax cache tests."""

        self.cache_revision += 1

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Record one batched lookup and return deterministic resolution data."""

        self.calls.append(references)
        return tuple(
            self._resolutions_by_reference.get(
                (
                    reference.identifier,
                    reference.wildcard_form,
                    reference.csv_column,
                ),
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                ),
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


class _StaticPromptLoraCatalogService:
    """Return deterministic LoRA catalog rows for prompt syntax-service tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store fixed LoRA catalog rows."""

        self._items = items
        self.calls = 0
        self.cache_revision = 0

    def bump_revision(self) -> None:
        """Advance the fake catalog revision used by syntax cache tests."""

        self.cache_revision += 1

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Record one catalog lookup and return fixed LoRA rows."""

        self.calls += 1
        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return fixed LoRA rows without recording a render-plan lookup."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Record one catalog lookup and return the matching LoRA row."""

        self.calls += 1
        normalized_prompt_name = _test_lora_lookup_key(prompt_name)
        bare_matches: list[PromptLoraCatalogItem] = []
        for item in self._items:
            if _test_lora_lookup_key(item.prompt_name) == normalized_prompt_name:
                return item
            if _test_lora_lookup_key(item.backend_value) == normalized_prompt_name:
                return item
            if "\\" not in prompt_name and "/" not in prompt_name:
                if item.collision_key == _test_lora_basename_key(prompt_name):
                    bare_matches.append(item)
        if len(bare_matches) == 1:
            return bare_matches[0]
        return None


class _FailingPromptLoraCatalogService:
    """Raise from LoRA lookup to exercise fallback renderer behavior."""

    cache_revision = "failing"

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return no picker rows for tests that do not exercise picker lookup."""

        return ()

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached rows for failing lookup tests."""

        return ()

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Fail one catalog lookup with the requested prompt name in context."""

        raise RuntimeError(f"catalog unavailable for {prompt_name}")


class _BootstrapPromptLoraCatalogService(_StaticPromptLoraCatalogService):
    """Return non-authoritative LoRA misses for startup bootstrap tests."""

    def can_report_lora_absence(self) -> bool:
        """Return that catalog misses are not authoritative yet."""

        return False


def _lora_item(
    *,
    display_name: str,
    basename: str,
    prompt_name: str,
    collision_count: int = 1,
    model_page_url: str | None = None,
    display_subtitle: str | None = None,
) -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item for application tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=display_subtitle,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=("trained token",),
        tags=("character",),
        model_page_url=model_page_url,
        collision_key=basename.casefold(),
        collision_count=collision_count,
        has_collision=collision_count > 1,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )


def _test_lora_lookup_key(value: str) -> str:
    """Return an extensionless lookup key for test LoRA catalog rows."""

    normalized = value.replace("\\", "/").casefold()
    if normalized.endswith(".safetensors"):
        return normalized[: -len(".safetensors")]
    return normalized


def _test_lora_basename_key(value: str) -> str:
    """Return the extensionless basename lookup key for test LoRA rows."""

    return _test_lora_lookup_key(value).rsplit("/", maxsplit=1)[-1]


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


def test_prompt_document_service_builds_prompt_aware_autocomplete_queries() -> None:
    """Autocomplete queries should use parsed segment bounds instead of raw comma scanning."""

    document_service = PromptDocumentService()
    text = "1girl, long ha"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert (query.prefix, query.word_start, query.word_end, query.active_tag_end) == (
        "long ha",
        7,
        14,
        14,
    )
    assert query.fallback_query == PromptAutocompleteFallbackQuery(
        prefix="ha",
        word_start=12,
        word_end=14,
        active_tag_end=14,
    )


def test_prompt_document_service_autocomplete_query_ignores_nested_commas() -> None:
    """Quoted and bracketed commas should not split the active autocomplete segment."""

    document_service = PromptDocumentService()
    text = '"cat, dog", [bird, fish], long ha'
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == len(text)
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_ignores_commas_inside_braces() -> (
    None
):
    """Brace placeholders should preserve the active segment boundary for autocomplete."""

    document_service = PromptDocumentService()
    text = "{animal, texture}, long ha"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == len(text)
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_fails_closed_for_selections_or_mid_segment_cursors() -> (
    None
):
    """Autocomplete queries should fail closed for selections while allowing mid-tag carets."""

    document_service = PromptDocumentService()
    text = "1girl, long hair"
    document_view = document_service.build_document_view(text)

    assert (
        document_service.autocomplete_query_at_cursor(
            document_view,
            text=text,
            cursor_position=len(text),
            has_selection=True,
            minimum_prefix_length=2,
        )
        is None
    )
    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("hair") + len("ha"),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long hair")
    assert query.word_end == text.index("hair") + len("ha")
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_allows_end_of_line_before_later_text() -> (
    None
):
    """Later physical lines should not block autocomplete at the current line end."""

    document_service = PromptDocumentService()
    text = "alpha\nlong ha\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("\nbeta")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_allows_mid_line_before_text() -> (
    None
):
    """Text ahead on the same physical line should be replaceable at accept time."""

    document_service = PromptDocumentService()
    text = "alpha\nlong hair\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("hair") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long hair")
    assert query.word_end == cursor_position
    assert query.active_tag_end == text.index("\nbeta")


def test_prompt_document_service_autocomplete_query_builds_no_comma_suffix_fallback() -> (
    None
):
    """No-comma prompt prose should keep the primary range and expose a suffix fallback."""

    document_service = PromptDocumentService()
    text = "1girl blue ha solo"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("ha") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "1girl blue ha"
    assert query.word_start == 0
    assert query.word_end == cursor_position
    assert query.active_tag_end == len(text)
    assert query.fallback_query == PromptAutocompleteFallbackQuery(
        prefix="ha",
        word_start=text.index("ha"),
        word_end=cursor_position,
        active_tag_end=cursor_position,
    )


def test_prompt_document_service_autocomplete_query_uses_emphasis_content_bounds() -> (
    None
):
    """Weighted prompt spans should query content text without entering weight suffixes."""

    document_service = PromptDocumentService()
    text = "(blue ha:1.2), solo"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("ha") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )
    weight_query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("1.") + len("1."),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "blue ha"
    assert query.word_start == text.index("blue")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position
    assert weight_query is None


def test_prompt_document_service_autocomplete_query_uses_current_line_visible_start() -> (
    None
):
    """Indented prompt lines should preserve indentation outside the replacement range."""

    document_service = PromptDocumentService()
    text = "alpha\n  long ha\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("\nbeta")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_allows_whitespace_before_line_break() -> (
    None
):
    """Whitespace after the caret on the same line should not block line-end autocomplete."""

    document_service = PromptDocumentService()
    text = "alpha\nlong ha   \nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("   ")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_ignores_blank_line_without_prefix() -> (
    None
):
    """Blank physical lines should not produce autocomplete queries without typed text."""

    document_service = PromptDocumentService()
    text = "alpha\n\nbeta"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("\n\n") + 1,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is None


def test_prompt_document_service_builds_wildcard_query_after_curly_opener() -> None:
    """Typing the curly opener should immediately produce a wildcard query."""

    document_service = PromptDocumentService()

    query = document_service.wildcard_autocomplete_query_at_cursor(
        text="{",
        cursor_position=1,
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == ""
    assert query.opener_start == 0
    assert query.replacement_end == 1


def test_prompt_document_service_builds_scene_query_after_line_start_marker() -> None:
    """Typing a line-start scene marker should produce a scene title query."""

    document_service = PromptDocumentService()
    text = "quality\n  **por"

    query = document_service.scene_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == "por"
    assert query.marker_start == text.index("**")
    assert query.title_start == text.index("por")
    assert query.replacement_end == len(text)


def test_prompt_document_service_scene_query_requires_line_start_marker() -> None:
    """Scene autocomplete should not trigger for inline marker text."""

    document_service = PromptDocumentService()

    inline_query = document_service.scene_autocomplete_query_at_cursor(
        text="quality **por",
        cursor_position=len("quality **por"),
        has_selection=False,
    )
    legacy_query = document_service.scene_autocomplete_query_at_cursor(
        text="@por",
        cursor_position=len("@por"),
        has_selection=False,
    )

    assert inline_query is None
    assert legacy_query is None


def test_prompt_document_service_wildcard_query_replaces_existing_closer() -> None:
    """Wildcard completion should own the existing placeholder shell when present."""

    document_service = PromptDocumentService()
    text = "{ani}"

    query = document_service.wildcard_autocomplete_query_at_cursor(
        text=text,
        cursor_position=text.index("}"),
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == "ani"
    assert query.replacement_end == len(text)


def test_autocomplete_replacement_text_formats_prompt_safe_inserted_tag_text() -> None:
    """Autocomplete replacement text should normalize booru tags into prompt-safe text."""

    assert autocomplete_replacement_text("looking_at_viewer") == "looking at viewer"
    assert autocomplete_replacement_text("cat_(animal)") == r"cat \(animal\)"


def test_filter_noop_autocomplete_suggestions_drops_semantically_identical_tags() -> (
    None
):
    """Autocomplete should suppress suggestions that already match the current prompt slice."""

    query = PromptAutocompleteQuery(
        prefix="looking at viewer",
        word_start=0,
        word_end=17,
        active_tag_end=17,
    )
    suggestions = (
        PromptAutocompleteSuggestion("looking_at_viewer", 100),
        PromptAutocompleteSuggestion("looking_away", 50),
    )

    filtered_suggestions = filter_noop_autocomplete_suggestions(
        text="looking at viewer",
        query=query,
        suggestions=suggestions,
    )

    assert filtered_suggestions == (PromptAutocompleteSuggestion("looking_away", 50),)


def test_filter_noop_autocomplete_suggestions_keeps_partial_completions() -> None:
    """Autocomplete should keep suggestions that extend the current prompt slice."""

    query = PromptAutocompleteQuery(
        prefix="looking at vi",
        word_start=0,
        word_end=13,
        active_tag_end=13,
    )
    suggestions = (PromptAutocompleteSuggestion("looking_at_viewer", 100),)

    filtered_suggestions = filter_noop_autocomplete_suggestions(
        text="looking at vi",
        query=query,
        suggestions=suggestions,
    )

    assert filtered_suggestions == suggestions


def test_prompt_document_service_builds_empty_lora_autocomplete_query() -> None:
    """Typing the LoRA token prefix should activate LoRA autocomplete immediately."""

    document_service = PromptDocumentService()
    text = "<lora:"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query == PromptLoraAutocompleteQuery(
        query_text="",
        token_start=0,
        token_end=len(text),
        name_start=len("<lora:"),
        name_end=len(text),
        replacement_start=0,
        replacement_end=len(text),
        typed_weight_text=None,
        has_closing_bracket=False,
    )


def test_prompt_document_service_builds_lora_autocomplete_query_for_name_prefix() -> (
    None
):
    """LoRA autocomplete should expose the typed name prefix and token bounds."""

    document_service = PromptDocumentService()
    text = r"<lora:Min"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "Min"
    assert query.name_start == len("<lora:")
    assert query.name_end == len(text)
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)
    assert query.typed_weight_text is None


def test_prompt_document_service_preserves_lora_path_fragment_query() -> None:
    """Directory-qualified LoRA fragments should remain intact for matching."""

    document_service = PromptDocumentService()
    text = r"<lora:illustrious\characters\Min"

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"illustrious\characters\Min"


def test_prompt_document_service_builds_lora_query_inside_closed_name_slot() -> None:
    """Editing a closed LoRA name should still allow replacing the whole token."""

    document_service = PromptDocumentService()
    text = "<lora:Mineru:0.8>"
    cursor_position = text.index("n")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "Mi"
    assert query.typed_weight_text == "0.8"
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)
    assert query.has_closing_bracket is True


def test_prompt_document_service_lora_query_ignores_nonnumeric_weight_suffix() -> None:
    """LoRA autocomplete must not preserve malformed suffixes as weights."""

    document_service = PromptDocumentService()
    text = r"<lora:Pony\Concept\springrider_Pony_v1:Pony\Style\cutedoodle_XL-000012>"
    cursor_position = text.index(":Pony\\Style")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"Pony\Concept\springrider_Pony_v1"
    assert query.typed_weight_text is None
    assert query.replacement_start == 0
    assert query.replacement_end == len(text)


def test_prompt_document_service_lora_query_does_not_cross_later_lora_tag() -> None:
    """An incomplete LoRA query must not consume a following LoRA token."""

    document_service = PromptDocumentService()
    text = r"<lora:Pony\Concept\springrider_Pony_v1" + "\n<lora:testlora:1.00>"
    cursor_position = text.index("\n")

    query = document_service.lora_autocomplete_query_at_cursor(
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == r"Pony\Concept\springrider_Pony_v1"
    assert query.typed_weight_text is None
    assert query.replacement_start == 0
    assert query.replacement_end == cursor_position
    assert query.has_closing_bracket is False


def test_prompt_document_service_lora_query_ignores_weight_slot_and_closed_tail() -> (
    None
):
    """LoRA autocomplete should only activate while editing the name slot."""

    document_service = PromptDocumentService()
    text = "<lora:Mineru:0.8>"

    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=text.index("0.8") + 1,
            has_selection=False,
        )
        is None
    )
    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=len(text),
            has_selection=False,
        )
        is None
    )
    assert (
        document_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=text.index("Mineru"),
            has_selection=True,
        )
        is None
    )


def test_lora_autocomplete_ranks_replaces_and_builds_friendly_ghost_text() -> None:
    """LoRA ranking should separate display completion from raw insertion text."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="Civit",
        token_start=0,
        token_end=11,
        name_start=6,
        name_end=11,
        replacement_start=0,
        replacement_end=11,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Other",
                basename="Other",
                prompt_name=r"illustrious\characters\civit_midna",
            ),
            _lora_item(
                display_name="CivitAI Midna",
                basename="raw_midna",
                prompt_name=r"illustrious\characters\raw_midna",
            ),
        ),
    )

    assert [candidate.display_text for candidate in candidates] == [
        "CivitAI Midna",
        "Other",
    ]
    assert candidates[0].display_completion_suffix == "AI Midna"
    assert (
        candidates[0].replacement_text
        == r"<lora:illustrious\characters\raw_midna:1.00>"
    )


def test_lora_autocomplete_matches_basename_and_preserves_existing_weight() -> None:
    """Basename matching should work when provider display names are unavailable."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="Mid",
        token_start=0,
        token_end=15,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=15,
        typed_weight_text="1.2",
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
            ),
        ),
    )

    assert candidates[0].display_text == "Midna"
    assert candidates[0].display_completion_suffix == "na"
    assert candidates[0].replacement_text == r"<lora:illustrious\characters\Midna:1.2>"


def test_lora_autocomplete_defaults_malformed_preserved_weight_text() -> None:
    """LoRA replacement text should remain scheduler-safe for malformed suffixes."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text=r"Pony\Concept\springrider_Pony_v1",
        token_start=0,
        token_end=48,
        name_start=6,
        name_end=38,
        replacement_start=0,
        replacement_end=48,
        typed_weight_text="testlora",
        has_closing_bracket=True,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Springrider Pony",
                basename="springrider_Pony_v1",
                prompt_name=r"Pony\Concept\springrider_Pony_v1",
            ),
        ),
    )

    assert candidates[0].replacement_text == (
        r"<lora:Pony\Concept\springrider_Pony_v1:1.00>"
    )


def test_lora_autocomplete_matches_directory_paths_and_keeps_collisions_safe() -> None:
    """Path queries should find colliding basenames and insert qualified names."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="sd15/characters/Mid",
        token_start=0,
        token_end=24,
        name_start=6,
        name_end=24,
        replacement_start=0,
        replacement_end=24,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
                collision_count=2,
            ),
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"sd15\characters\Midna",
                collision_count=2,
            ),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].display_completion_suffix == "na"
    assert candidates[0].replacement_text == r"<lora:sd15\characters\Midna:1.00>"


def test_lora_autocomplete_omits_ghost_suffix_for_substring_match() -> None:
    """Substring matches should not project misleading ghost text."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="dna",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        (
            _lora_item(
                display_name="Midna",
                basename="Midna",
                prompt_name=r"illustrious\characters\Midna",
            ),
        ),
    )

    assert candidates[0].display_completion_suffix == ""


def test_lora_autocomplete_returns_all_ranked_matches_without_cap() -> None:
    """LoRA autocomplete should not hide matches behind a presentation cap."""

    service = PromptLoraAutocompleteService()
    query = PromptLoraAutocompleteQuery(
        query_text="LoRA",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=10,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    candidates = service.rank_candidates(
        query,
        tuple(
            _lora_item(
                display_name=f"LoRA {index:02}",
                basename=f"LoRA_{index:02}",
                prompt_name=rf"illustrious\characters\LoRA_{index:02}",
            )
            for index in range(55)
        ),
    )

    assert len(candidates) == 55
    assert candidates[0].display_text == "LoRA 00"
    assert candidates[-1].display_text == "LoRA 54"


def test_prompt_document_service_hides_literal_parenthesis_escapes_in_segment_views() -> (
    None
):
    """Document views should expose user-facing segment labels without protective backslashes."""

    document_service = PromptDocumentService()

    document_view = document_service.build_document_view(r"painting \(medium\)")

    assert document_view.source_text == r"painting \(medium\)"
    assert [segment.text for segment in document_view.segments] == [
        r"painting \(medium\)"
    ]
    assert [segment.display_text for segment in document_view.segments] == [
        "painting (medium)"
    ]


def test_prompt_document_service_hides_literal_parenthesis_escapes_in_reorder_chips() -> (
    None
):
    """Reorder chip labels should show literal parenthetical text without raw escapes."""

    document_service = PromptDocumentService()

    chips = document_service.reorder_chips(
        document_service.build_document_view(r"vertin \(reverse:1999\)")
    )

    assert [chip.text for chip in chips] == [r"vertin \(reverse:1999\)"]
    assert [chip.display_text for chip in chips] == ["vertin (reverse:1999)"]


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


def test_prompt_mutation_service_returns_refreshed_document_view_after_full_reorder() -> (
    None
):
    """Full reorders should preserve trailing-comma intent in the refreshed semantic snapshot."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "beta, alpha, "
    assert result.document_view.source_text == "beta, alpha, "
    assert result.document_view.has_trailing_comma is True
    assert [segment.display_text for segment in result.document_view.segments] == [
        "beta",
        "alpha",
    ]


def test_prompt_document_service_builds_follow_up_reorder_from_current_layout_view() -> (
    None
):
    """In-session reorder transforms should use the current layout as their baseline."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    current_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(2, 0, 1)),),
        gaps=(),
    )

    follow_up_layout_view = document_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )

    assert document_service.reorder_layout_chip_indices(follow_up_layout_view) == (
        2,
        1,
        0,
    )
    assert (
        document_service.serialize_reorder_layout_view(
            document_view,
            follow_up_layout_view,
        )
        == "gamma, beta, alpha"
    )


def test_prompt_document_service_builds_reorder_session_from_one_snapshot() -> None:
    """Reorder setup should expose chips and layout from one shared domain snapshot."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta\ngamma, delta")

    reorder_session = document_service.build_reorder_session_view(document_view)

    assert [chip.display_text for chip in reorder_session.chips] == [
        "alpha",
        "beta",
        "gamma",
        "delta",
    ]
    assert document_service.reorder_layout_chip_indices(
        reorder_session.layout_view
    ) == (0, 1, 2, 3)
    assert len(reorder_session.layout_view.rows) == 2


def test_prompt_document_service_preserves_lora_inline_separator_layout_slots() -> None:
    """Layout serialization should not force commas between no-comma LoRA chips."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("<lora:a:1.0> <lora:b:1.0>")

    reorder_session = document_service.build_reorder_session_view(document_view)
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        reorder_session.layout_view,
    )

    assert [chip.display_text for chip in reorder_session.chips] == [
        "<lora:a:1.0>",
        "<lora:b:1.0>",
    ]
    assert (
        document_service.serialize_reorder_layout_view(
            document_view,
            reorder_session.layout_view,
        )
        == "<lora:a:1.0> <lora:b:1.0>"
    )
    assert preview_snapshot.text == "<lora:a:1.0> <lora:b:1.0>"


def test_prompt_document_service_moves_lora_chip_without_forcing_commas() -> None:
    """In-session LoRA movement should preserve space-style same-row separators."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("foo <lora:a:1.0> bar")
    reorder_session = document_service.build_reorder_session_view(document_view)

    preview_layout = document_service.build_preview_drop_layout_view_from_layout(
        document_view,
        reorder_session.layout_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout,
    )

    assert (
        document_service.serialize_reorder_layout_view(document_view, preview_layout)
        == "<lora:a:1.0> foo bar"
    )
    assert preview_snapshot.text == "<lora:a:1.0> foo bar"


def test_prompt_document_service_keeps_exposed_trailing_gap_during_drag_preview() -> (
    None
):
    """Preview layouts should keep blank rows exposed by hiding the final dragged chip."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("1girl,\n\numbrella,")
    current_layout_view = document_service.build_reorder_layout_view(document_view)

    preview_layout_view = document_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert preview_layout_view.gaps == (
        PromptReorderGapView(
            gap_index=0,
            separator_text=",\n\n\n",
            blank_line_count=2,
            placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
        ),
    )
    assert preview_snapshot.text == "1girl, umbrella,\n\n\n"


def test_prompt_document_service_can_drop_into_exposed_trailing_gap() -> None:
    """Trailing blank rows should use the same blank-line target rules as row gaps."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("1girl,\n\numbrella,")
    current_layout_view = document_service.build_reorder_layout_view(document_view)

    preview_layout_view = document_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=1,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert preview_layout_view == PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1,)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n",
                blank_line_count=0,
            ),
            PromptReorderGapView(
                gap_index=1,
                separator_text=",\n\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )
    assert preview_snapshot.text == "1girl,\numbrella,\n\n"


def test_prompt_document_service_keeps_lifted_final_row_as_blank_target() -> None:
    """Lifting a final single-chip row should leave its origin row target visible."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(
        "1girl,\n\numbrella,\n\nraincoat"
    )
    current_layout_view = document_service.build_reorder_layout_view(document_view)

    base_drag_layout_view = document_service.build_base_drag_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=2,
    )
    preview_layout_view = document_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=2,
        drop_target=PromptGapBlankLineDropTarget(gap_index=1, blank_line_index=1),
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )

    assert base_drag_layout_view.gaps[-1] == PromptReorderGapView(
        gap_index=1,
        separator_text="\n\n\n",
        blank_line_count=2,
        placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
    )
    assert preview_snapshot.text == "1girl,\n\numbrella,\n\nraincoat\n"


def test_prompt_mutation_service_commits_current_reorder_layout_view() -> None:
    """Layout commits should serialize the full in-session order, not only the last move."""

    mutation_service = PromptMutationService()
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(2, 1, 0)),),
        gaps=(),
    )

    result = mutation_service.reorder_layout(
        "alpha, beta, gamma",
        layout_view=committed_layout_view,
        selected_chip_index=1,
    )

    assert result.text == "gamma, beta, alpha"
    assert result.document_view.source_text == "gamma, beta, alpha"
    assert (result.selection_start, result.selection_end) == (7, 11)


def test_prompt_mutation_service_trims_transient_trailing_gap_on_layout_commit() -> (
    None
):
    """Committing an Alt reorder session should drop preview-only trailing blank rows."""

    mutation_service = PromptMutationService()
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )

    result = mutation_service.reorder_layout(
        "1girl,\n\numbrella,",
        layout_view=committed_layout_view,
        selected_chip_index=1,
    )

    assert result.text == "1girl, umbrella,"
    assert result.document_view.source_text == "1girl, umbrella,"


def test_prompt_mutation_service_reorder_chips_splits_multi_tag_emphasis_shell() -> (
    None
):
    """Reordering one chip out of a grouped emphasis shell should duplicate the shell."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "(1girl, solo:1.20), blush",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    assert result.text == "(1girl:1.20), blush, (solo:1.20)"
    assert result.selection_start is not None
    assert result.selection_end is not None
    assert result.text[result.selection_start : result.selection_end] == "solo"


def test_prompt_mutation_service_reorder_segments_preserves_brace_placeholder_text() -> (
    None
):
    """Reorders should keep brace placeholder text intact inside moved segments."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "{animal, texture}, beta, gamma",
        dragged_chip_index=0,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )

    assert result.text == "beta, {animal, texture}, gamma"
    assert [segment.display_text for segment in result.document_view.segments] == [
        "beta",
        "{animal, texture}",
        "gamma",
    ]


def test_prompt_mutation_service_reorder_segments_preserves_base_separator_structure_under_line_drop() -> (
    None
):
    """Line-drop commits should preserve separator structure from the hidden base state."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "a, b, c,\nd, e, f",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=1, insertion_index=2),
    )

    assert result.text == "a, c,\nd, e, b, f"
    assert result.document_view.source_text == "a, c,\nd, e, b, f"
    assert (result.selection_start, result.selection_end) == (12, 13)


def test_prompt_mutation_service_reorder_segments_does_not_move_blank_line_gap_with_dragged_chip() -> (
    None
):
    """Line-drop commits should leave existing blank-line structure where it already lives."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,\n\nbeta, gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma, alpha,\n\nbeta"
    assert result.document_view.source_text == "gamma, alpha,\n\nbeta"
    assert (result.selection_start, result.selection_end) == (0, 5)


def test_prompt_mutation_service_reorder_segments_can_insert_into_blank_line_gap() -> (
    None
):
    """Blank-line drop targets should insert the moved segment onto the chosen empty row."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,\n\n\n\n\nbeta, gamma",
        dragged_chip_index=2,
        drop_target=PromptGapBlankLineDropTarget(
            gap_index=0,
            blank_line_index=1,
        ),
    )

    assert result.text == "alpha,\n\ngamma,\n\n\nbeta"
    assert result.document_view.source_text == "alpha,\n\ngamma,\n\n\nbeta"
    assert (result.selection_start, result.selection_end) == (8, 13)


def test_prompt_mutation_service_reorder_segments_restores_selection_for_selected_chip() -> (
    None
):
    """Full reorders should restore selection to the explicitly selected segment."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma,alpha,beta"
    assert (result.selection_start, result.selection_end) == (0, 5)


def test_prompt_mutation_service_reorder_segments_always_selects_the_moved_segment() -> (
    None
):
    """Typed drop-target reorders should restore selection to the moved segment."""

    mutation_service = PromptMutationService()

    result = mutation_service.reorder_chips(
        "alpha,beta,gamma",
        dragged_chip_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    assert result.text == "gamma,alpha,beta"
    assert (result.selection_start, result.selection_end) == (0, 5)


def test_prompt_mutation_service_apply_syntax_action_dispatches_emphasis_adjustment() -> (
    None
):
    """Typed syntax actions should reuse the exact-outer-range emphasis mutation path."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=10,
            delta=0.05,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.10)", 1, 4, "(cat:1.10)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.10"


def test_prompt_mutation_service_apply_syntax_action_dispatches_exact_weight_for_real_shell() -> (
    None
):
    """Typed exact-weight actions should reuse the exact outer-range mutation path."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptSetEmphasisWeightAction(
            outer_start=0,
            outer_end=10,
            weight=1.20,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:1.20)", 1, 4, "(cat:1.20)")
    assert result.document_view.emphasis_spans[0].weight_text == "1.20"


def test_prompt_mutation_service_apply_syntax_action_dispatches_exact_weight_for_content_range() -> (
    None
):
    """Typed content-range exact-weight actions should wrap plain text exactly once."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "cat",
        PromptSetEmphasisWeightContentAction(
            content_start=0,
            content_end=3,
            weight=0.95,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("(cat:0.95)", 1, 4, "(cat:0.95)")
    assert result.document_view.emphasis_spans[0].weight_text == "0.95"


def test_prompt_mutation_service_apply_syntax_action_exact_neutral_returns_plain_text() -> (
    None
):
    """Exact neutral weight should preserve plain text when no shell exists."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "cat",
        PromptSetEmphasisWeightContentAction(
            content_start=0,
            content_end=3,
            weight=1,
        ),
    )

    assert result is not None
    assert (
        result.text,
        result.selection_start,
        result.selection_end,
        result.document_view.source_text,
    ) == ("cat", 0, 3, "cat")
    assert result.document_view.emphasis_spans == ()


def test_prompt_mutation_service_apply_syntax_action_returns_none_for_stale_range() -> (
    None
):
    """Typed syntax actions should fail closed when the target outer range is stale."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptAdjustEmphasisAction(
            outer_start=0,
            outer_end=9,
            delta=0.05,
        ),
    )

    assert result is None


def test_prompt_mutation_service_apply_syntax_action_consumes_passive_clicks() -> None:
    """Consume-only syntax actions should preserve text while still being routable."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "(cat:1.05)",
        PromptConsumeSyntaxAction(syntax_kind="emphasis"),
    )

    assert result is None


def test_prompt_mutation_service_adjusts_lora_weight_by_outer_range() -> None:
    """LoRA weight mutations should preserve the hidden relative path."""

    mutation_service = PromptMutationService()
    text = r"<lora:Illustrious\Character\Mineru:0.8>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptAdjustLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            delta=0.1,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Illustrious\Character\Mineru:0.90>"
    assert result.selection_start == text.index("0.8")
    assert result.selection_end == result.selection_start + len("0.90")


def test_prompt_mutation_service_sets_lora_first_weight_only() -> None:
    """LoRA exact edits should leave the optional second weight unchanged."""

    mutation_service = PromptMutationService()
    text = r"<lora:Mineru:0.8:0.6>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptSetLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            weight=1.25,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Mineru:1.25:0.6>"


def test_prompt_mutation_service_allows_negative_lora_weight() -> None:
    """LoRA exact edits should not inherit emphasis minimum clamping."""

    mutation_service = PromptMutationService()
    text = r"<lora:Mineru:0.8:0.6>"

    result = mutation_service.apply_syntax_action(
        text,
        PromptSetLoraWeightAction(
            outer_start=0,
            outer_end=len(text),
            weight=-0.25,
        ),
    )

    assert result is not None
    assert result.text == r"<lora:Mineru:-0.25:0.6>"


def test_prompt_mutation_service_sets_implicit_wildcard_tag_explicitly() -> None:
    """Editing an implicit wildcard group should persist an explicit tag suffix."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster}, {monster}",
        PromptAdjustWildcardTagAction(
            outer_start=11,
            outer_end=20,
            current_display_tag="1",
            delta=1,
        ),
    )

    assert result is not None
    assert result.text == "{monster}, {monster|2}"
    assert result.selection_start == len("{monster}, {monster|2}") - 1
    assert result.selection_end == result.selection_start


def test_prompt_mutation_service_increments_explicit_wildcard_numeric_tag() -> None:
    """Explicit positive integer wildcard tags should step upward."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|1}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=11,
            current_display_tag="1",
            delta=1,
        ),
    )

    assert result is not None
    assert result.text == "{monster|2}"


def test_prompt_mutation_service_decrements_explicit_wildcard_numeric_tag() -> None:
    """Explicit positive integer wildcard tags should step downward to one."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|2}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=11,
            current_display_tag="2",
            delta=-1,
        ),
    )

    assert result is not None
    assert result.text == "{monster|1}"


def test_prompt_mutation_service_does_not_adjust_nonnumeric_wildcard_tag() -> None:
    """Nonnumeric wildcard tags should be display-only for numeric stepping."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{monster|one}",
        PromptAdjustWildcardTagAction(
            outer_start=0,
            outer_end=13,
            current_display_tag="one",
            delta=1,
        ),
    )

    assert result is None


def test_prompt_mutation_service_sets_csv_wildcard_tag_without_rewriting_body() -> None:
    """CSV wildcard tag edits should preserve the identifier and selected column."""

    mutation_service = PromptMutationService()

    result = mutation_service.apply_syntax_action(
        "{csv:monster:color}",
        PromptSetWildcardTagAction(
            outer_start=0,
            outer_end=19,
            tag="2",
        ),
    )

    assert result is not None
    assert result.text == "{csv:monster:color|2}"


def test_prompt_syntax_service_builds_renderer_ready_render_plan_without_reparsing() -> (
    None
):
    """Syntax service should build renderer views from an existing document view."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view("((cat:1.2) dog:1.1)")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.default_profile(),
    )
    emphasis_view = render_plan.renderer_view_for_kind("emphasis")

    assert [
        (span.kind, span.start, span.end, span.depth)
        for span in render_plan.syntax_spans
    ] == [  # noqa: E501
        ("emphasis", 0, 19, 0),
        ("emphasis", 1, 10, 1),
    ]
    assert isinstance(emphasis_view, PromptEmphasisRendererView)
    assert emphasis_view.kind == "emphasis"
    assert [
        (span.start, span.end, span.depth) for span in emphasis_view.syntax_spans
    ] == [
        (0, 19, 0),
        (1, 10, 1),
    ]
    assert [
        (span.content_start, span.content_end, span.depth)
        for span in emphasis_view.emphasis_spans
    ] == [
        (1, 14, 0),
        (2, 5, 1),
    ]


def test_prompt_document_service_reuses_cached_document_views() -> None:
    """Repeated prompt snapshots should reuse process-wide parse/view cache entries."""

    clear_prompt_document_caches()
    first_service = PromptDocumentService()
    second_service = PromptDocumentService()

    first_view = first_service.build_document_view("(cat:1.2), {animal}")
    second_view = second_service.build_document_view("(cat:1.2), {animal}")

    assert second_view is first_view


def test_prompt_scene_projection_service_reuses_cached_scene_documents() -> None:
    """Repeated scene projection parses should reuse the pure scene cache."""

    clear_prompt_scene_projection_cache()
    source = "quality\n**portrait\nportrait text"

    first_document = parse_prompt_scene_projection_document(source)
    second_document = parse_prompt_scene_projection_document(source)

    assert second_document is first_document


def test_effective_prompt_text_without_scenes_returns_full_text() -> None:
    """Scene-effective prompt context should preserve ordinary prompt text."""

    source = "quality, portrait"

    assert (
        effective_prompt_text_at_source_position(text=source, source_position=3)
        == source
    )


def test_effective_prompt_text_in_universal_block_uses_universal_text_only() -> None:
    """Scene-effective universal context should exclude all scene-local text."""

    source = "quality\n<lora:global:1>\n**portrait\nportrait text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("quality"),
        )
        == "quality\n<lora:global:1>\n"
    )


def test_effective_prompt_text_inside_scene_materializes_universal_and_scene() -> None:
    """Scene-effective scene context should match generation materialization."""

    source = "quality\n<lora:global:1>\n**portrait\nportrait text\n**cafe\ncafe text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("cafe text"),
        )
        == "quality\n<lora:global:1>\n\ncafe text"
    )


def test_effective_prompt_text_on_scene_marker_uses_that_scene() -> None:
    """Scene marker positions should resolve to their owning scene block."""

    source = "quality\n**portrait\nportrait text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("**portrait"),
        )
        == "quality\n\nportrait text"
    )


def test_prompt_syntax_service_reuses_render_plan_until_catalog_revision_changes() -> (
    None
):
    """Syntax render-plan cache should avoid duplicate catalog work and invalidate by revision."""

    clear_prompt_syntax_render_plan_cache()
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway(
        {
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        }
    )
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{animal}, {animal}")
    profile = profile_service.build_profile({"prompt_syntaxes": ["wildcard"]})

    first_plan = syntax_service.build_render_plan(document_view, profile)
    second_plan = syntax_service.build_render_plan(document_view, profile)
    gateway.bump_revision()
    third_plan = syntax_service.build_render_plan(document_view, profile)

    assert second_plan is first_plan
    assert third_plan == first_plan
    assert third_plan is not first_plan
    assert len(gateway.calls) == 2


def test_prompt_syntax_service_invalidates_render_plan_on_lora_revision_change() -> (
    None
):
    """LoRA catalog revision changes should invalidate cached syntax render plans."""

    clear_prompt_syntax_render_plan_cache()
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _StaticPromptLoraCatalogService(
        (
            _lora_item(
                display_name="Style",
                basename="style",
                prompt_name="style",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view("<lora:style:0.8>")
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    first_plan = syntax_service.build_render_plan(document_view, profile)
    second_plan = syntax_service.build_render_plan(document_view, profile)
    lora_catalog.bump_revision()
    third_plan = syntax_service.build_render_plan(document_view, profile)

    assert second_plan is first_plan
    assert third_plan == first_plan
    assert third_plan is not first_plan
    assert lora_catalog.calls == 2


def test_prompt_syntax_service_lora_render_plan_summary_counts_resolution_states() -> (
    None
):
    """LoRA render-plan summaries should separate resolved and missing metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _StaticPromptLoraCatalogService(
        (
            _lora_item(
                display_name="Style",
                basename="style",
                prompt_name="style",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view(
        "<lora:style:0.8>, <lora:missing:1.0>"
    )
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    render_plan = syntax_service.build_render_plan(document_view, profile)
    lora_view = render_plan.renderer_view_for_kind("lora")
    assert isinstance(lora_view, PromptLoraRendererView)
    summary = _lora_render_plan_summary(
        document_view=document_view,
        syntax_profile=profile,
        active_lora_syntax_spans=tuple(
            span for span in render_plan.syntax_spans if span.kind == "lora"
        ),
        lora_renderer_spans=tuple(lora_view.lora_spans),
        cache_revision=str(lora_catalog.cache_revision),
    )

    assert summary.document_lora_span_count == 2
    assert summary.active_lora_syntax_span_count == 2
    assert summary.renderer_lora_span_count == 2
    assert summary.resolved_lora_count == 1
    assert summary.missing_lora_count == 1
    assert summary.non_authoritative_unresolved_count == 0


def test_prompt_syntax_service_lora_summary_counts_bootstrap_unresolved() -> None:
    """Non-authoritative misses should stay separate from missing LoRAs."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _BootstrapPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view("<lora:missing:1.0>")
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    render_plan = syntax_service.build_render_plan(document_view, profile)
    lora_view = render_plan.renderer_view_for_kind("lora")
    assert isinstance(lora_view, PromptLoraRendererView)
    summary = _lora_render_plan_summary(
        document_view=document_view,
        syntax_profile=profile,
        active_lora_syntax_spans=tuple(
            span for span in render_plan.syntax_spans if span.kind == "lora"
        ),
        lora_renderer_spans=tuple(lora_view.lora_spans),
        cache_revision=str(lora_catalog.cache_revision),
    )

    assert summary.resolved_lora_count == 0
    assert summary.missing_lora_count == 0
    assert summary.non_authoritative_unresolved_count == 1


def test_prompt_syntax_profile_service_uses_field_style_and_ignores_unknown_entries() -> (
    None
):
    """Profile resolution should read prompt_syntaxes from field style and ignore unknown values."""

    profile_service = PromptSyntaxProfileService()

    profile = profile_service.build_profile(
        {"prompt_syntaxes": ["wildcard", "unknown", "lora", "emphasis", "wildcard"]}
    )

    assert profile.enabled_syntaxes == ("wildcard", "lora", "emphasis")


def test_prompt_syntax_profile_service_falls_back_to_default_profile() -> None:
    """Missing or invalid prompt_syntaxes metadata should return the application default."""

    profile_service = PromptSyntaxProfileService()

    assert profile_service.build_profile({}).enabled_syntaxes == (
        "emphasis",
        "wildcard",
        "lora",
    )
    assert profile_service.build_profile(
        {"prompt_syntaxes": "wildcard"}
    ).enabled_syntaxes == ("emphasis", "wildcard", "lora")


def test_prompt_syntax_service_builds_wildcard_renderer_view_when_enabled() -> None:
    """Wildcard-enabled profiles should expose renderer-ready wildcard metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway(
        {
            ("monster", "csv", "color"): PromptWildcardResolution(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
                exists=True,
                matched_csv_column="Color",
                available_csv_columns=("Color", "Size"),
            ),
        }
    )
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{csv:monster:color}")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["emphasis", "wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("wildcard", 0, 19),
    ]
    assert [
        (
            span.identifier,
            span.wildcard_form,
            span.csv_column,
            span.exists,
            span.matched_csv_column,
            span.available_csv_columns,
            span.source_key,
            span.display_text,
            span.display_tag,
            span.tag_is_explicit,
            span.tag_is_numeric,
            span.can_step_tag,
            span.source_occurrence_count,
        )
        for span in wildcard_view.wildcard_spans
    ] == [
        (
            "monster",
            "csv",
            "color",
            True,
            "Color",
            ("Color", "Size"),
            "csv:monster",
            "monster:Color",
            None,
            False,
            False,
            False,
            1,
        ),
    ]
    assert gateway.calls == [
        (
            PromptWildcardReference(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
            ),
        )
    ]


def test_prompt_syntax_service_classifies_numeric_wildcard_display_tags() -> None:
    """Only strict positive integer wildcard tags should support numeric stepping."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        "{one|1}, {two|2}, {twelve|12}, {zero|0}, {padded|01}, "
        "{negative|-1}, {decimal|1.5}, {word|one}, {mixed|a1}"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [
        (span.identifier, span.display_tag, span.tag_is_numeric, span.can_step_tag)
        for span in wildcard_view.wildcard_spans
    ] == [
        ("one", "1", True, True),
        ("two", "2", True, True),
        ("twelve", "12", True, True),
        ("zero", "0", False, False),
        ("padded", "01", False, False),
        ("negative", "-1", False, False),
        ("decimal", "1.5", False, False),
        ("word", "one", False, False),
        ("mixed", "a1", False, False),
    ]


def test_prompt_syntax_service_groups_wildcards_by_resolver_source() -> None:
    """Wildcard source grouping should ignore tags and CSV columns."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        "{monster}, {monster|2}, {csv:monster:color}, {csv:monster:size}"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [
        (span.identifier, span.csv_column, span.tag, span.source_key)
        for span in wildcard_view.wildcard_spans
    ] == [
        ("monster", None, None, "simple:monster"),
        ("monster", None, "2", "simple:monster"),
        ("monster", "color", None, "csv:monster"),
        ("monster", "size", None, "csv:monster"),
    ]
    assert [span.source_occurrence_count for span in wildcard_view.wildcard_spans] == [
        2,
        2,
        2,
        2,
    ]


def test_prompt_syntax_service_sets_implicit_and_explicit_wildcard_display_tags() -> (
    None
):
    """Repeated untagged sources should display implicit group tags without persistence."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))

    single_document_view = document_service.build_document_view("{monster}")
    repeated_document_view = document_service.build_document_view(
        "{monster}, {monster}"
    )
    explicit_document_view = document_service.build_document_view("{monster|one}")

    profile = profile_service.build_profile({"prompt_syntaxes": ["wildcard"]})
    single_view = syntax_service.build_render_plan(
        single_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")
    repeated_view = syntax_service.build_render_plan(
        repeated_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")
    explicit_view = syntax_service.build_render_plan(
        explicit_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")

    assert isinstance(single_view, PromptWildcardRendererView)
    assert isinstance(repeated_view, PromptWildcardRendererView)
    assert isinstance(explicit_view, PromptWildcardRendererView)
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in single_view.wildcard_spans
    ] == [(None, False, False)]
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in repeated_view.wildcard_spans
    ] == [("1", False, True), ("1", False, True)]
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in explicit_view.wildcard_spans
    ] == [("one", True, False)]


def test_prompt_syntax_service_omits_wildcard_renderers_when_profile_disables_them() -> (
    None
):
    """Wildcard spans should stay parsed but inactive when the field profile disables them."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway({})
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{animal}, (cat:1.05)")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["emphasis"]}),
    )

    assert [span.kind for span in document_view.syntax_spans] == [
        "wildcard",
        "emphasis",
    ]
    assert [span.kind for span in render_plan.syntax_spans] == ["emphasis"]
    assert render_plan.renderer_view_for_kind("wildcard") is None
    assert gateway.calls == []


def test_prompt_syntax_service_builds_lora_renderer_view_when_enabled() -> None:
    """LoRA-enabled profiles should expose renderer-ready LoRA metadata."""

    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(
        (
            PromptLoraCatalogItem(
                display_name="Sword stances collection [Pony]",
                display_subtitle="Battoujutsu",
                prompt_name=r"Illustrious\Character\Mineru",
                backend_value=r"Illustrious\Character\Mineru.safetensors",
                relative_path=r"Illustrious\Character\Mineru.safetensors",
                folder=r"Illustrious\Character",
                basename="Mineru",
                extension=".safetensors",
                thumbnail_variants=(),
                base_model="Illustrious",
                trained_words=("mineru",),
                tags=("character",),
                model_page_url=model_page_url,
                collision_key="mineru",
                collision_count=1,
                has_collision=False,
                search_text="mineru",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view(
        r"<lora:Illustrious\Character\Mineru:0.8>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("lora", 0, len(document_view.source_text)),
    ]
    assert [
        (
            span.prompt_name,
            span.display_name,
            span.display_subtitle,
            span.first_weight_text,
            span.model_page_url,
            span.folder,
            span.base_model,
            span.has_collision,
        )
        for span in lora_view.lora_spans
    ] == [
        (
            r"Illustrious\Character\Mineru",
            "Sword stances collection [Pony]",
            "Battoujutsu",
            "0.8",
            model_page_url,
            r"Illustrious\Character",
            "Illustrious",
            False,
        )
    ]
    assert lora_catalog_service.calls == 1


def test_prompt_syntax_service_uses_fallback_lora_view_without_catalog() -> None:
    """Uncataloged LoRA syntax should still produce a LoRA renderer span."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        r"<lora:Illustrious\Character\Mineru:0.8>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("lora", 0, len(document_view.source_text)),
    ]
    assert [
        (
            span.prompt_name,
            span.display_name,
            span.first_weight_text,
            span.backend_value,
            span.thumbnail_variants,
        )
        for span in lora_view.lora_spans
    ] == [
        (
            r"Illustrious\Character\Mineru",
            "Mineru",
            "0.8",
            None,
            (),
        )
    ]


def test_prompt_syntax_service_uses_fallback_lora_view_when_catalog_misses() -> None:
    """Missing catalog metadata should not remove parsed LoRA renderer spans."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view("<lora:failing_model:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert len(lora_view.lora_spans) == 1
    assert lora_view.lora_spans[0].prompt_name == "failing_model"
    assert lora_view.lora_spans[0].display_name == "failing_model"
    assert lora_view.lora_spans[0].backend_value is None
    assert lora_catalog_service.calls == 1


def test_prompt_syntax_service_keeps_bootstrap_lora_misses_neutral() -> None:
    """Bootstrap catalog misses should not falsely mark LoRA chips as missing."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _BootstrapPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view("<lora:not_ready_yet:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert lora_view.lora_spans[0].prompt_name == "not_ready_yet"
    assert lora_view.lora_spans[0].backend_value is None
    assert (
        lora_view.lora_spans[0].lora_status
        is PromptLoraResolutionStatus.PENDING_NO_AUTHORITY
    )
    assert lora_view.lora_spans[0].exists is True


def test_prompt_syntax_service_uses_fallback_lora_view_when_catalog_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Catalog lookup failures should log and degrade to fallback LoRA spans."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=_FailingPromptLoraCatalogService(),
    )
    document_view = document_service.build_document_view("<lora:missing_model:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert len(lora_view.lora_spans) == 1
    assert lora_view.lora_spans[0].prompt_name == "missing_model"
    assert lora_view.lora_spans[0].display_name == "missing_model"
    assert any(
        "LoRA catalog lookup failed; using fallback renderer span" in record.message
        for record in caplog.records
    )


def test_prompt_syntax_service_binds_unique_bare_lora_name_metadata() -> None:
    """Bare pasted LoRA schedules should bind unique catalog thumbnail metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(
        (
            PromptLoraCatalogItem(
                display_name="Ranni",
                display_subtitle=None,
                prompt_name=r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1",
                backend_value=(
                    r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"
                    ".safetensors"
                ),
                relative_path=(
                    r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"
                    ".safetensors"
                ),
                folder=r"illustrious\characters",
                basename="Ranni_illusXLNoobAI_Incrs_v1",
                extension=".safetensors",
                thumbnail_variants=(
                    PromptLoraThumbnailVariant(
                        size=512,
                        storage_key="RANNI:banner:512",
                        width=512,
                        height=44,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=90112,
                    ),
                ),
                base_model="Illustrious",
                trained_words=("ranni",),
                tags=("character",),
                model_page_url=None,
                collision_key="ranni_illusxlnoobai_incrs_v1",
                collision_count=1,
                has_collision=False,
                search_text="ranni",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view(
        "<lora:Ranni_illusXLNoobAI_Incrs_v1:1>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    span = lora_view.lora_spans[0]
    assert span.prompt_name == "Ranni_illusXLNoobAI_Incrs_v1"
    assert span.display_name == "Ranni"
    assert span.folder == r"illustrious\characters"
    assert span.thumbnail_variants[0].storage_key == "RANNI:banner:512"
