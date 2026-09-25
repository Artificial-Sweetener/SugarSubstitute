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

from collections.abc import Sequence
from dataclasses import replace

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptRegionStructureView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxRendererView,
    PromptSyntaxRenderPlan,
    PromptWildcardRendererView,
)
from substitute.application.prompt_editor.editing.region_structure_edits import (
    rebuild_region_structure_after_edit,
    region_structure_edit_requires_rebuild,
    remap_region_structure_after_edit,
)

from .diagnostic_remap import remap_diagnostics_after_source_edit
from .lora_semantic_remap import (
    remap_lora_renderer_spans_for_edit,
    remap_lora_views_for_edit,
)
from .segment_semantic_remap import remap_segment_views_for_edit
from .source_edit_syntax import SYNTAX_SENSITIVE_CHARACTERS
from .source_shifted_sequence import remap_source_sequence
from .wildcard_semantic_remap import (
    EditedWildcardIdentity,
    edited_wildcard_identity,
    remap_wildcard_renderer_spans_for_edit,
    remap_wildcard_views_for_edit,
)

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
        "syntax_sensitive_character",
        "syntax_sensitive_autocomplete_prefix_requires_layout",
    }
)


class PromptProjectionSemanticRemapper:
    """Remap prepared semantic snapshots without depending on Qt or the surface."""

    def region_structure_edit_requires_rebuild(
        self,
        *,
        current_document_view: PromptDocumentView,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one edit changes regional separator ownership."""

        if current_document_view.source_text != previous_text:
            return True
        return region_structure_edit_requires_rebuild(
            previous_text,
            next_text,
            current_document_view.region_structure,
            start=start,
            end=end,
        )

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
        region_structure_requires_rebuild: bool | None = None,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Return remapped semantic state for one exact source edit."""

        expected_next_text = (
            previous_text[:start] + replacement_text + previous_text[end:]
        )
        if expected_next_text != next_text:
            return None
        if current_document_view.source_text != previous_text:
            return None
        requires_region_rebuild = region_structure_requires_rebuild
        if requires_region_rebuild is None:
            requires_region_rebuild = self.region_structure_edit_requires_rebuild(
                current_document_view=current_document_view,
                previous_text=previous_text,
                next_text=next_text,
                start=start,
                end=end,
            )
        delta = len(replacement_text) - (end - start)
        preserved_emphasis_ranges = _preserved_emphasis_content_ranges(
            current_document_view,
            previous_text=previous_text,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )
        edited_wildcard = edited_wildcard_identity(
            current_document_view.wildcard_spans,
            next_text=next_text,
            start=start,
            end=end,
            delta=delta,
        )
        region_structure = (
            rebuild_region_structure_after_edit(
                previous_text,
                next_text,
                current_document_view.region_structure,
                start=start,
                end=end,
            )
            if requires_region_rebuild
            else None
        )
        document_view = _optimistic_document_view_for_edit(
            current_document_view,
            next_text=next_text,
            start=start,
            end=end,
            delta=delta,
            region_structure=region_structure,
            preserved_emphasis_ranges=preserved_emphasis_ranges,
            edited_wildcard=edited_wildcard,
        )
        render_plan = _optimistic_render_plan_for_edit(
            current_render_plan,
            start=start,
            end=end,
            delta=delta,
            preserved_emphasis_ranges=preserved_emphasis_ranges,
            edited_wildcard=edited_wildcard,
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
        region_structure_requires_rebuild: bool | None = None,
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
            region_structure_requires_rebuild=region_structure_requires_rebuild,
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
        """Shift an expanded token past insertions before its opening boundary."""

        if expanded_source_range is None:
            return None

        range_start, range_end = expanded_source_range
        insertion = start == end
        if end <= range_start:
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
        diagnostics: Sequence[PromptDiagnostic],
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> Sequence[PromptDiagnostic]:
        """Return diagnostics remapped across one bounded source edit."""

        return remap_diagnostics_after_source_edit(
            diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )


def _preserved_emphasis_content_ranges(
    document_view: PromptDocumentView,
    *,
    previous_text: str,
    start: int,
    end: int,
    replacement_text: str,
) -> frozenset[tuple[int, int]]:
    """Identify emphasis containers unchanged by one ordinary content insertion."""

    if (
        start != end
        or len(replacement_text) != 1
        or not replacement_text.isprintable()
        or replacement_text in SYNTAX_SENSITIVE_CHARACTERS
        or replacement_text in ",[]"
        or (start > 0 and previous_text[start - 1] == "\\")
    ):
        return frozenset()
    preserved_ranges: set[tuple[int, int]] = set()
    for span in document_view.emphasis_spans:
        if span.outer_start >= start:
            break
        if span.content_start <= start <= span.content_end:
            preserved_ranges.add((span.outer_start, span.outer_end))
    return frozenset(preserved_ranges)


def _optimistic_document_view_for_edit(
    document_view: PromptDocumentView,
    *,
    next_text: str,
    start: int,
    end: int,
    delta: int,
    region_structure: PromptRegionStructureView | None = None,
    preserved_emphasis_ranges: frozenset[tuple[int, int]] = frozenset(),
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> PromptDocumentView:
    """Return a document view with safe content spans retained across edits."""

    return PromptDocumentView(
        source_text=next_text,
        segments=remap_segment_views_for_edit(
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
            preserved_emphasis_ranges=preserved_emphasis_ranges,
        ),
        wildcard_spans=remap_wildcard_views_for_edit(
            document_view.wildcard_spans,
            start=start,
            end=end,
            delta=delta,
            edited_wildcard=edited_wildcard,
        ),
        lora_spans=remap_lora_views_for_edit(
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
            preserved_emphasis_ranges=preserved_emphasis_ranges,
            edited_wildcard=edited_wildcard,
        ),
        region_structure=(
            region_structure
            if region_structure is not None
            else remap_region_structure_after_edit(
                document_view.region_structure,
                start=start,
                end=end,
                replacement_text=next_text[start : start + (end - start + delta)],
            )
        ),
        has_trailing_comma=next_text.rstrip().endswith(","),
    )


def _optimistic_render_plan_for_edit(
    render_plan: PromptSyntaxRenderPlan,
    *,
    start: int,
    end: int,
    delta: int,
    preserved_emphasis_ranges: frozenset[tuple[int, int]] = frozenset(),
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> PromptSyntaxRenderPlan:
    """Return a render plan with non-overlapping renderer spans remapped."""

    return PromptSyntaxRenderPlan(
        syntax_spans=_remap_syntax_spans_for_edit(
            render_plan.syntax_spans,
            start=start,
            end=end,
            delta=delta,
            preserved_emphasis_ranges=preserved_emphasis_ranges,
            edited_wildcard=edited_wildcard,
        ),
        renderer_views=tuple(
            _remap_renderer_view_for_edit(
                renderer_view,
                start=start,
                end=end,
                delta=delta,
                preserved_emphasis_ranges=preserved_emphasis_ranges,
                edited_wildcard=edited_wildcard,
            )
            for renderer_view in render_plan.renderer_views
        ),
        document_semantics_identity=render_plan.document_semantics_identity,
    )


def _remap_renderer_view_for_edit(
    renderer_view: PromptSyntaxRendererView,
    *,
    start: int,
    end: int,
    delta: int,
    preserved_emphasis_ranges: frozenset[tuple[int, int]] = frozenset(),
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> PromptSyntaxRendererView:
    """Return one renderer view remapped across a source edit."""

    syntax_spans = _remap_syntax_spans_for_edit(
        renderer_view.syntax_spans,
        start=start,
        end=end,
        delta=delta,
        preserved_emphasis_ranges=preserved_emphasis_ranges,
        edited_wildcard=edited_wildcard,
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
                preserved_emphasis_ranges=preserved_emphasis_ranges,
            ),
        )
    if isinstance(renderer_view, PromptWildcardRendererView):
        return replace(
            renderer_view,
            syntax_spans=syntax_spans,
            wildcard_spans=remap_wildcard_renderer_spans_for_edit(
                renderer_view.wildcard_spans,
                start=start,
                end=end,
                delta=delta,
                edited_wildcard=edited_wildcard,
            ),
        )
    if isinstance(renderer_view, PromptLoraRendererView):
        return replace(
            renderer_view,
            syntax_spans=syntax_spans,
            lora_spans=remap_lora_renderer_spans_for_edit(
                renderer_view.lora_spans,
                start=start,
                end=end,
                delta=delta,
            ),
        )
    return replace(renderer_view, syntax_spans=syntax_spans)


def _remap_syntax_spans_for_edit(
    spans: Sequence[PromptSyntaxSpanView],
    *,
    start: int,
    end: int,
    delta: int,
    preserved_emphasis_ranges: frozenset[tuple[int, int]] = frozenset(),
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> Sequence[PromptSyntaxSpanView]:
    """Return syntax spans that remain valid after one source edit."""

    def remap_preserved_emphasis(
        span: PromptSyntaxSpanView, offset: int
    ) -> PromptSyntaxSpanView | None:
        """Extend a validated decorated container across its content edit."""

        if (
            edited_wildcard is not None
            and span.kind == "wildcard"
            and (span.start, span.end) == edited_wildcard[0]
        ):
            return replace(span, end=span.end + offset)
        if (
            span.kind != "emphasis"
            or (span.start, span.end) not in preserved_emphasis_ranges
        ):
            return None
        return replace(span, end=span.end + offset)

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_syntax_span_source_range,
        shift_item=_shift_syntax_span,
        remap_overlap=(
            remap_preserved_emphasis
            if preserved_emphasis_ranges or edited_wildcard is not None
            else None
        ),
    )


def _remap_emphasis_views_for_edit(
    spans: Sequence[PromptEmphasisView],
    *,
    start: int,
    end: int,
    delta: int,
    preserved_emphasis_ranges: frozenset[tuple[int, int]] = frozenset(),
) -> Sequence[PromptEmphasisView]:
    """Return emphasis spans that remain valid after one source edit."""

    def remap_preserved_emphasis(
        span: PromptEmphasisView, offset: int
    ) -> PromptEmphasisView | None:
        """Extend a validated emphasis span across its content insertion."""

        if (span.outer_start, span.outer_end) not in preserved_emphasis_ranges:
            return None
        return replace(
            span,
            outer_end=span.outer_end + offset,
            content_end=span.content_end + offset,
            weight_start=span.weight_start + offset,
            weight_end=span.weight_end + offset,
        )

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_emphasis_source_range,
        shift_item=_shift_emphasis_view,
        remap_overlap=remap_preserved_emphasis if preserved_emphasis_ranges else None,
    )


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


def _syntax_span_source_range(span: PromptSyntaxSpanView) -> tuple[int, int]:
    """Return one syntax span's source range for lazy remapping."""

    return span.start, span.end


def _shift_syntax_span(
    span: PromptSyntaxSpanView,
    delta: int,
) -> PromptSyntaxSpanView:
    """Return one unchanged syntax span shifted by a uniform source delta."""

    return PromptSyntaxSpanView(
        kind=span.kind,
        start=span.start + delta,
        end=span.end + delta,
        depth=span.depth,
    )


def _emphasis_source_range(span: PromptEmphasisView) -> tuple[int, int]:
    """Return one emphasis span's outer source range."""

    return span.outer_start, span.outer_end


def _shift_emphasis_view(span: PromptEmphasisView, delta: int) -> PromptEmphasisView:
    """Return one emphasis view shifted by a uniform source delta."""

    return replace(
        span,
        outer_start=span.outer_start + delta,
        outer_end=span.outer_end + delta,
        content_start=span.content_start + delta,
        content_end=span.content_end + delta,
        weight_start=span.weight_start + delta,
        weight_end=span.weight_end + delta,
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
