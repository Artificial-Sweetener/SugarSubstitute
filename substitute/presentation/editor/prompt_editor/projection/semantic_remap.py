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

"""Remap prepared prompt semantics across bounded local source edits."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDocumentView,
    PromptEmphasisRendererView,
    PromptEmphasisView,
    PromptLoraRendererSpanView,
    PromptLoraRendererView,
    PromptLoraView,
    PromptSegmentView,
    PromptSyntaxRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxSpanView,
    PromptWildcardRendererSpanView,
    PromptWildcardRendererView,
    PromptWildcardView,
)

from .diagnostic_remap import remap_diagnostics_after_source_edit

type PromptProjectionOptimisticPromptState = tuple[
    PromptDocumentView, PromptSyntaxRenderPlan
]

_OPTIMISTIC_IMMEDIATE_DEFERRAL_REASONS = frozenset(
    {
        "control_character",
        "delete_control_character",
        "expanded_token_active",
        "delete_intersects_projected_token",
        "plain_single_character_requires_layout",
        "plain_single_character_delete",
        "syntax_sensitive_autocomplete_prefix_requires_layout",
    }
)


class PromptProjectionSemanticRemapper:
    """Remap prepared semantic snapshots without depending on Qt or the surface."""

    def optimistic_prompt_state_for_edit(
        self,
        *,
        current_document_view: PromptDocumentView,
        current_render_plan: PromptSyntaxRenderPlan,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Return remapped semantic state for one exact source edit."""

        expected_next_text = (
            previous_text[:start] + replacement_text + previous_text[end:]
        )
        if expected_next_text != next_text:
            return None
        if current_document_view.source_text != previous_text:
            return None

        delta = len(replacement_text) - (end - start)
        document_view = _optimistic_document_view_for_edit(
            current_document_view,
            next_text=next_text,
            start=start,
            end=end,
            delta=delta,
        )
        render_plan = _optimistic_render_plan_for_edit(
            current_render_plan,
            start=start,
            end=end,
            delta=delta,
        )
        return document_view, render_plan

    def optimistic_prompt_state_for_source_edit(
        self,
        *,
        current_document_view: PromptDocumentView,
        current_render_plan: PromptSyntaxRenderPlan,
        previous_text: str | None,
        next_text: str,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Return remapped semantic state when source-edit metadata is exact."""

        if (
            previous_text is None
            or start is None
            or end is None
            or replacement_text is None
            or start < 0
            or end < start
            or end > len(previous_text)
        ):
            return None
        return self.optimistic_prompt_state_for_edit(
            current_document_view=current_document_view,
            current_render_plan=current_render_plan,
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )

    def should_use_optimistic_prompt_state_for_immediate_edit(
        self, *, deferral_reason: str
    ) -> bool:
        """Return whether an immediate edit should preserve semantic state."""

        return deferral_reason in _OPTIMISTIC_IMMEDIATE_DEFERRAL_REASONS

    def remap_expanded_source_range_for_edit(
        self,
        expanded_source_range: tuple[int, int] | None,
        *,
        start: int,
        end: int,
        delta: int,
    ) -> tuple[int, int] | None:
        """Return an expanded raw-token range aligned across one source edit."""

        if expanded_source_range is None:
            return None

        range_start, range_end = expanded_source_range
        insertion = start == end
        if end <= range_start and not (insertion and start == range_start):
            return range_start + delta, range_end + delta
        if start >= range_end and not (insertion and start == range_end):
            return expanded_source_range

        next_start = range_start
        if start < range_start:
            next_start = start
        next_end = max(next_start, range_end + delta)
        return next_start, next_end

    def remap_diagnostics_for_edit(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return diagnostics remapped across one bounded source edit."""

        return remap_diagnostics_after_source_edit(
            diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )


def _optimistic_document_view_for_edit(
    document_view: PromptDocumentView,
    *,
    next_text: str,
    start: int,
    end: int,
    delta: int,
) -> PromptDocumentView:
    """Return a document view with non-overlapping semantic spans remapped."""

    return PromptDocumentView(
        source_text=next_text,
        segments=_remap_segment_views_for_edit(
            document_view.segments,
            start=start,
            end=end,
            delta=delta,
        ),
        emphasis_spans=_remap_emphasis_views_for_edit(
            document_view.emphasis_spans,
            start=start,
            end=end,
            delta=delta,
        ),
        wildcard_spans=_remap_wildcard_views_for_edit(
            document_view.wildcard_spans,
            start=start,
            end=end,
            delta=delta,
        ),
        lora_spans=_remap_lora_views_for_edit(
            document_view.lora_spans,
            start=start,
            end=end,
            delta=delta,
        ),
        syntax_spans=_remap_syntax_spans_for_edit(
            document_view.syntax_spans,
            start=start,
            end=end,
            delta=delta,
        ),
        has_trailing_comma=next_text.rstrip().endswith(","),
    )


def _optimistic_render_plan_for_edit(
    render_plan: PromptSyntaxRenderPlan,
    *,
    start: int,
    end: int,
    delta: int,
) -> PromptSyntaxRenderPlan:
    """Return a render plan with non-overlapping renderer spans remapped."""

    return PromptSyntaxRenderPlan(
        syntax_spans=_remap_syntax_spans_for_edit(
            render_plan.syntax_spans,
            start=start,
            end=end,
            delta=delta,
        ),
        renderer_views=tuple(
            _remap_renderer_view_for_edit(
                renderer_view,
                start=start,
                end=end,
                delta=delta,
            )
            for renderer_view in render_plan.renderer_views
        ),
    )


def _remap_renderer_view_for_edit(
    renderer_view: PromptSyntaxRendererView,
    *,
    start: int,
    end: int,
    delta: int,
) -> PromptSyntaxRendererView:
    """Return one renderer view remapped across a source edit."""

    syntax_spans = _remap_syntax_spans_for_edit(
        renderer_view.syntax_spans,
        start=start,
        end=end,
        delta=delta,
    )
    if isinstance(renderer_view, PromptEmphasisRendererView):
        return replace(
            renderer_view,
            syntax_spans=syntax_spans,
            emphasis_spans=_remap_emphasis_views_for_edit(
                renderer_view.emphasis_spans,
                start=start,
                end=end,
                delta=delta,
            ),
        )
    if isinstance(renderer_view, PromptWildcardRendererView):
        return replace(
            renderer_view,
            syntax_spans=syntax_spans,
            wildcard_spans=_remap_wildcard_renderer_spans_for_edit(
                renderer_view.wildcard_spans,
                start=start,
                end=end,
                delta=delta,
            ),
        )
    if isinstance(renderer_view, PromptLoraRendererView):
        return replace(
            renderer_view,
            syntax_spans=syntax_spans,
            lora_spans=_remap_lora_renderer_spans_for_edit(
                renderer_view.lora_spans,
                start=start,
                end=end,
                delta=delta,
            ),
        )
    return replace(renderer_view, syntax_spans=syntax_spans)


def _remap_segment_views_for_edit(
    segments: tuple[PromptSegmentView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptSegmentView, ...]:
    """Return segment ranges that remain valid after one source edit."""

    remapped_segments: list[PromptSegmentView] = []
    for segment in segments:
        if _range_overlaps_edit(
            range_start=segment.selection_start,
            range_end=segment.selection_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_segments.append(
            replace(
                segment,
                display_source_start=_remap_position_after_edit(
                    segment.display_source_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                display_source_end=_remap_position_after_edit(
                    segment.display_source_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                selection_start=_remap_position_after_edit(
                    segment.selection_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                selection_end=_remap_position_after_edit(
                    segment.selection_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_segments)


def _remap_syntax_spans_for_edit(
    spans: tuple[PromptSyntaxSpanView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptSyntaxSpanView, ...]:
    """Return syntax spans that remain valid after one source edit."""

    remapped_spans: list[PromptSyntaxSpanView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.start,
            range_end=span.end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                start=_remap_position_after_edit(
                    span.start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                end=_remap_position_after_edit(
                    span.end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_emphasis_views_for_edit(
    spans: tuple[PromptEmphasisView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptEmphasisView, ...]:
    """Return emphasis spans that remain valid after one source edit."""

    remapped_spans: list[PromptEmphasisView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.outer_start,
            range_end=span.outer_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                outer_start=_remap_position_after_edit(
                    span.outer_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                outer_end=_remap_position_after_edit(
                    span.outer_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                content_start=_remap_position_after_edit(
                    span.content_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                content_end=_remap_position_after_edit(
                    span.content_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                weight_start=_remap_position_after_edit(
                    span.weight_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                weight_end=_remap_position_after_edit(
                    span.weight_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_wildcard_views_for_edit(
    spans: tuple[PromptWildcardView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptWildcardView, ...]:
    """Return wildcard spans that remain valid after one source edit."""

    remapped_spans: list[PromptWildcardView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.outer_start,
            range_end=span.outer_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                outer_start=_remap_position_after_edit(
                    span.outer_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                outer_end=_remap_position_after_edit(
                    span.outer_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                content_start=_remap_position_after_edit(
                    span.content_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                content_end=_remap_position_after_edit(
                    span.content_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_lora_views_for_edit(
    spans: tuple[PromptLoraView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptLoraView, ...]:
    """Return LoRA spans that remain valid after one source edit."""

    remapped_spans: list[PromptLoraView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.outer_start,
            range_end=span.outer_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                outer_start=_remap_position_after_edit(
                    span.outer_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                outer_end=_remap_position_after_edit(
                    span.outer_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                name_start=_remap_position_after_edit(
                    span.name_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                name_end=_remap_position_after_edit(
                    span.name_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                first_weight_start=_remap_position_after_edit(
                    span.first_weight_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                first_weight_end=_remap_position_after_edit(
                    span.first_weight_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                second_weight_start=_remap_optional_position_after_edit(
                    span.second_weight_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                second_weight_end=_remap_optional_position_after_edit(
                    span.second_weight_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                block_weights_start=_remap_optional_position_after_edit(
                    span.block_weights_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                block_weights_end=_remap_optional_position_after_edit(
                    span.block_weights_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_wildcard_renderer_spans_for_edit(
    spans: tuple[PromptWildcardRendererSpanView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptWildcardRendererSpanView, ...]:
    """Return wildcard renderer spans that remain valid after one source edit."""

    remapped_spans: list[PromptWildcardRendererSpanView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.outer_start,
            range_end=span.outer_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                outer_start=_remap_position_after_edit(
                    span.outer_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                outer_end=_remap_position_after_edit(
                    span.outer_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                content_start=_remap_position_after_edit(
                    span.content_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                content_end=_remap_position_after_edit(
                    span.content_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_lora_renderer_spans_for_edit(
    spans: tuple[PromptLoraRendererSpanView, ...],
    *,
    start: int,
    end: int,
    delta: int,
) -> tuple[PromptLoraRendererSpanView, ...]:
    """Return LoRA renderer spans that remain valid after one source edit."""

    remapped_spans: list[PromptLoraRendererSpanView] = []
    for span in spans:
        if _range_overlaps_edit(
            range_start=span.outer_start,
            range_end=span.outer_end,
            edit_start=start,
            edit_end=end,
        ):
            continue
        remapped_spans.append(
            replace(
                span,
                outer_start=_remap_position_after_edit(
                    span.outer_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                outer_end=_remap_position_after_edit(
                    span.outer_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                name_start=_remap_position_after_edit(
                    span.name_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                name_end=_remap_position_after_edit(
                    span.name_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                first_weight_start=_remap_position_after_edit(
                    span.first_weight_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                first_weight_end=_remap_position_after_edit(
                    span.first_weight_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
                second_weight_start=_remap_optional_position_after_edit(
                    span.second_weight_start,
                    start=start,
                    end=end,
                    delta=delta,
                ),
                second_weight_end=_remap_optional_position_after_edit(
                    span.second_weight_end,
                    start=start,
                    end=end,
                    delta=delta,
                    range_end=True,
                ),
            )
        )
    return tuple(remapped_spans)


def _remap_position_after_edit(
    position: int,
    *,
    start: int,
    end: int,
    delta: int,
    range_end: bool = False,
) -> int:
    """Return a source position shifted across a non-overlapping edit."""

    if range_end and start == end:
        if position > start:
            return position + delta
        return position
    if position >= end:
        return position + delta
    if position > start:
        return start
    return position


def _remap_optional_position_after_edit(
    position: int | None,
    *,
    start: int,
    end: int,
    delta: int,
    range_end: bool = False,
) -> int | None:
    """Return an optional source position shifted across one source edit."""

    if position is None:
        return None
    return _remap_position_after_edit(
        position,
        start=start,
        end=end,
        delta=delta,
        range_end=range_end,
    )


def _range_overlaps_edit(
    *,
    range_start: int,
    range_end: int,
    edit_start: int,
    edit_end: int,
) -> bool:
    """Return whether a source range intersects one source edit."""

    if edit_start == edit_end:
        return range_start < edit_start < range_end
    return range_start < edit_end and edit_start < range_end


__all__ = [
    "PromptProjectionOptimisticPromptState",
    "PromptProjectionSemanticRemapper",
]
