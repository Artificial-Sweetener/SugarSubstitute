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

"""Verify pure optimistic semantic remapping for projection source edits."""

from __future__ import annotations

from decimal import Decimal

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDocumentView,
    PromptEmphasisRendererView,
    PromptEmphasisView,
    PromptLoraRendererSpanView,
    PromptLoraRendererView,
    PromptLoraResolutionStatus,
    PromptLoraView,
    PromptSegmentView,
    PromptSpellingDiagnosticPayload,
    PromptSyntaxRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxSpanView,
    PromptWildcardRendererSpanView,
    PromptWildcardRendererView,
    PromptWildcardView,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_remap import (
    PromptProjectionSemanticRemapper,
)


def _segment() -> PromptSegmentView:
    """Return one segment span for remap tests."""

    return PromptSegmentView(
        index=0,
        text="segment",
        display_text="segment",
        display_source_start=10,
        display_source_end=17,
        selection_start=10,
        selection_end=17,
        separator_text_after=", ",
        has_separator_after=True,
    )


def _syntax_span(start: int = 18, end: int = 24) -> PromptSyntaxSpanView:
    """Return one syntax span for remap tests."""

    return PromptSyntaxSpanView(kind="emphasis", start=start, end=end, depth=1)


def _emphasis() -> PromptEmphasisView:
    """Return one emphasis span for remap tests."""

    return PromptEmphasisView(
        outer_start=18,
        outer_end=28,
        content_start=19,
        content_end=25,
        weight_start=26,
        weight_end=27,
        weight=Decimal("1.2"),
        weight_text="1.2",
        depth=1,
    )


def _wildcard() -> PromptWildcardView:
    """Return one wildcard span for remap tests."""

    return PromptWildcardView(
        outer_start=30,
        outer_end=39,
        content_start=32,
        content_end=37,
        wildcard_form="curly",
        identifier="colors",
        csv_column=None,
        tag=None,
        depth=1,
    )


def _lora() -> PromptLoraView:
    """Return one LoRA span for remap tests."""

    return PromptLoraView(
        outer_start=42,
        outer_end=66,
        name_start=48,
        name_end=52,
        first_weight_start=53,
        first_weight_end=56,
        first_weight=Decimal("1.0"),
        first_weight_text="1.0",
        second_weight_start=58,
        second_weight_end=61,
        second_weight=Decimal("0.5"),
        second_weight_text="0.5",
        block_weights_start=None,
        block_weights_end=None,
        prompt_name="demo",
        depth=1,
    )


def _wildcard_renderer_span() -> PromptWildcardRendererSpanView:
    """Return one renderer wildcard span for remap tests."""

    return PromptWildcardRendererSpanView(
        outer_start=30,
        outer_end=39,
        content_start=32,
        content_end=37,
        wildcard_form="curly",
        identifier="colors",
        csv_column=None,
        tag=None,
        exists=True,
        matched_csv_column=None,
        available_csv_columns=(),
        depth=1,
        source_key="colors",
        display_text="red",
        display_tag=None,
        tag_is_explicit=False,
        tag_is_numeric=False,
        can_step_tag=False,
        source_occurrence_count=1,
    )


def _lora_renderer_span() -> PromptLoraRendererSpanView:
    """Return one renderer LoRA span for remap tests."""

    return PromptLoraRendererSpanView(
        outer_start=42,
        outer_end=66,
        name_start=48,
        name_end=52,
        first_weight_start=53,
        first_weight_end=56,
        first_weight=Decimal("1.0"),
        first_weight_text="1.0",
        second_weight_start=58,
        second_weight_end=61,
        second_weight=Decimal("0.5"),
        second_weight_text="0.5",
        prompt_name="demo",
        backend_value="demo.safetensors",
        display_name="Demo",
        display_subtitle=None,
        trained_words=(),
        thumbnail_variants=(),
        model_page_url=None,
        folder="",
        base_model=None,
        has_collision=False,
        lora_status=PromptLoraResolutionStatus.FOUND,
        match_source="exact",
        status_reason="",
        authority=True,
        ambiguity_candidate_count=0,
        exists=True,
        depth=1,
    )


def _prompt_state(text: str) -> tuple[PromptDocumentView, PromptSyntaxRenderPlan]:
    """Return one semantic prompt state with all remappable span families."""

    document_view = PromptDocumentView(
        source_text=text,
        segments=(_segment(),),
        emphasis_spans=(_emphasis(),),
        wildcard_spans=(_wildcard(),),
        lora_spans=(_lora(),),
        syntax_spans=(_syntax_span(),),
        has_trailing_comma=False,
    )
    render_plan = PromptSyntaxRenderPlan(
        syntax_spans=(_syntax_span(),),
        renderer_views=(
            PromptSyntaxRendererView(kind="plain", syntax_spans=(_syntax_span(),)),
            PromptEmphasisRendererView(
                kind="emphasis",
                syntax_spans=(_syntax_span(),),
                emphasis_spans=(_emphasis(),),
            ),
            PromptWildcardRendererView(
                kind="wildcard",
                syntax_spans=(_syntax_span(30, 39),),
                wildcard_spans=(_wildcard_renderer_span(),),
            ),
            PromptLoraRendererView(
                kind="lora",
                syntax_spans=(_syntax_span(42, 66),),
                lora_spans=(_lora_renderer_span(),),
            ),
        ),
    )
    return document_view, render_plan


def _diagnostic(start: int = 70, end: int = 76) -> PromptDiagnostic:
    """Return one diagnostic with source coordinates."""

    return PromptDiagnostic(
        diagnostic_id="spell-demo",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.WARNING,
        source_start=start,
        source_end=end,
        message="Check spelling",
        payload=PromptSpellingDiagnosticPayload(word="demo"),
    )


def test_semantic_remapper_shifts_non_intersecting_semantic_state() -> None:
    """Non-intersecting semantic spans shift by the source edit delta."""

    previous_text = "a" * 90
    next_text = previous_text[:3] + "xx" + previous_text[3:]
    document_view, render_plan = _prompt_state(previous_text)

    result = PromptProjectionSemanticRemapper().optimistic_prompt_state_for_edit(
        current_document_view=document_view,
        current_render_plan=render_plan,
        previous_text=previous_text,
        next_text=next_text,
        start=3,
        end=3,
        replacement_text="xx",
    )

    assert result is not None
    next_document_view, next_render_plan = result
    assert next_document_view.source_text == next_text
    assert next_document_view.segments[0].selection_start == 12
    assert next_document_view.syntax_spans[0].start == 20
    assert next_document_view.emphasis_spans[0].content_start == 21
    assert next_document_view.wildcard_spans[0].content_end == 39
    assert next_document_view.lora_spans[0].second_weight_start == 60
    assert next_document_view.lora_spans[0].block_weights_start is None
    lora_renderer = next_render_plan.renderer_view_for_kind("lora")
    assert isinstance(lora_renderer, PromptLoraRendererView)
    assert lora_renderer.lora_spans[0].first_weight_end == 58


def test_semantic_remapper_drops_intersecting_semantic_ranges() -> None:
    """Semantic spans intersecting a source edit are omitted as stale."""

    previous_text = "a" * 90
    next_text = previous_text[:12] + "Z" + previous_text[13:]
    document_view, render_plan = _prompt_state(previous_text)

    result = PromptProjectionSemanticRemapper().optimistic_prompt_state_for_edit(
        current_document_view=document_view,
        current_render_plan=render_plan,
        previous_text=previous_text,
        next_text=next_text,
        start=12,
        end=13,
        replacement_text="Z",
    )

    assert result is not None
    next_document_view, _next_render_plan = result
    assert next_document_view.segments == ()
    assert next_document_view.emphasis_spans == document_view.emphasis_spans


def test_semantic_remapper_preserves_insertion_at_range_boundaries() -> None:
    """Boundary insertions use the existing non-overlap position behavior."""

    previous_text = "a" * 90
    next_text = previous_text[:10] + "!" + previous_text[10:]
    document_view, render_plan = _prompt_state(previous_text)

    result = PromptProjectionSemanticRemapper().optimistic_prompt_state_for_edit(
        current_document_view=document_view,
        current_render_plan=render_plan,
        previous_text=previous_text,
        next_text=next_text,
        start=10,
        end=10,
        replacement_text="!",
    )

    assert result is not None
    next_document_view, _next_render_plan = result
    assert len(next_document_view.segments) == 1
    assert next_document_view.segments[0].selection_start == 11
    assert next_document_view.segments[0].selection_end == 18


def test_semantic_remapper_reuses_objects_strictly_before_an_edit() -> None:
    """Optimistic edits should not reconstruct unaffected semantic prefix objects."""

    previous_text = "a" * 90
    next_text = previous_text[:80] + "!" + previous_text[80:]
    document_view, render_plan = _prompt_state(previous_text)

    result = PromptProjectionSemanticRemapper().optimistic_prompt_state_for_edit(
        current_document_view=document_view,
        current_render_plan=render_plan,
        previous_text=previous_text,
        next_text=next_text,
        start=80,
        end=80,
        replacement_text="!",
    )

    assert result is not None
    next_document_view, next_render_plan = result
    assert next_document_view.segments[0] is document_view.segments[0]
    assert next_document_view.syntax_spans[0] is document_view.syntax_spans[0]
    assert next_document_view.emphasis_spans[0] is document_view.emphasis_spans[0]
    assert next_document_view.wildcard_spans[0] is document_view.wildcard_spans[0]
    assert next_document_view.lora_spans[0] is document_view.lora_spans[0]
    assert (
        next_render_plan.renderer_views[1].syntax_spans[0]
        is render_plan.renderer_views[1].syntax_spans[0]
    )

    diagnostic = _diagnostic(start=10, end=14)
    remapped_diagnostics = (
        PromptProjectionSemanticRemapper().remap_diagnostics_for_edit(
            (diagnostic,),
            start=80,
            end=80,
            replacement_text="!",
        )
    )
    assert remapped_diagnostics[0] is diagnostic


def test_semantic_remapper_rejects_mismatched_source_metadata() -> None:
    """Optimistic remap is unavailable when source identity is not exact."""

    previous_text = "a" * 90
    document_view, render_plan = _prompt_state(previous_text)
    remapper = PromptProjectionSemanticRemapper()

    assert (
        remapper.optimistic_prompt_state_for_edit(
            current_document_view=document_view,
            current_render_plan=render_plan,
            previous_text=previous_text,
            next_text="unexpected",
            start=3,
            end=3,
            replacement_text="xx",
        )
        is None
    )
    assert (
        remapper.optimistic_prompt_state_for_source_edit(
            current_document_view=document_view,
            current_render_plan=render_plan,
            previous_text=previous_text,
            next_text=previous_text,
            start=8,
            end=3,
            replacement_text="",
        )
        is None
    )


def test_semantic_remapper_remaps_expanded_ranges() -> None:
    """Expanded raw-token ranges shift or expand using the surface-era policy."""

    remapper = PromptProjectionSemanticRemapper()

    assert remapper.remap_expanded_source_range_for_edit(
        (10, 20), start=3, end=3, delta=2
    ) == (12, 22)
    assert remapper.remap_expanded_source_range_for_edit(
        (10, 20), start=12, end=13, delta=-1
    ) == (10, 19)
    assert remapper.remap_expanded_source_range_for_edit(
        (10, 20), start=25, end=25, delta=2
    ) == (10, 20)


def test_semantic_remapper_remaps_diagnostics_and_drops_overlaps() -> None:
    """Diagnostic source ranges remap through the semantic remap service."""

    remapper = PromptProjectionSemanticRemapper()

    shifted = remapper.remap_diagnostics_for_edit(
        (_diagnostic(),),
        start=3,
        end=3,
        replacement_text="xx",
    )
    assert shifted[0].source_start == 72
    assert shifted[0].source_end == 78

    dropped = remapper.remap_diagnostics_for_edit(
        (_diagnostic(start=10, end=14),),
        start=12,
        end=12,
        replacement_text="x",
    )
    assert dropped == ()


def test_semantic_remapper_keeps_immediate_reason_allowlist() -> None:
    """The optimistic immediate remap allowlist preserves current reasons."""

    remapper = PromptProjectionSemanticRemapper()

    assert remapper.should_use_optimistic_prompt_state_for_immediate_edit(
        deferral_reason="plain_single_character_delete"
    )
    assert not remapper.should_use_optimistic_prompt_state_for_immediate_edit(
        deferral_reason="safe_typing"
    )
