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

"""Retain edited wildcard identity during bounded optimistic source remaps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from substitute.application.prompt_editor.document.views import PromptWildcardView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptWildcardRendererSpanView,
)
from substitute.application.prompt_editor.projection.wildcard_projection import (
    is_numeric_wildcard_tag,
)
from substitute.domain.prompt.document.parser import parse_wildcard_content

from .source_shifted_sequence import remap_source_sequence

type EditedWildcardIdentity = tuple[tuple[int, int], str, str, str | None, str | None]


def edited_wildcard_identity(
    spans: Sequence[PromptWildcardView],
    *,
    next_text: str,
    start: int,
    end: int,
    delta: int,
) -> EditedWildcardIdentity | None:
    """Parse only an edited wildcard's content without resolving its catalog entry."""

    for span in spans:
        if not (span.content_start <= start and end <= span.content_end):
            continue
        raw_content = next_text[span.content_start : span.content_end + delta]
        form, identifier, csv_column, tag = parse_wildcard_content(raw_content)
        if form is None or identifier is None:
            return None
        return (
            (span.outer_start, span.outer_end),
            form.value,
            identifier,
            csv_column,
            tag,
        )
    return None


def remap_wildcard_views_for_edit(
    spans: Sequence[PromptWildcardView],
    *,
    start: int,
    end: int,
    delta: int,
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> Sequence[PromptWildcardView]:
    """Keep valid edited wildcard content and shift unaffected wildcard spans."""

    def remap_edited_wildcard(
        span: PromptWildcardView, offset: int
    ) -> PromptWildcardView | None:
        """Keep the exact new wildcard identity while the catalog catches up."""

        if edited_wildcard is None or _view_range(span) != edited_wildcard[0]:
            return None
        _, form, identifier, csv_column, tag = edited_wildcard
        return replace(
            span,
            outer_end=span.outer_end + offset,
            content_end=span.content_end + offset,
            wildcard_form=form,
            identifier=identifier,
            csv_column=csv_column,
            tag=tag,
        )

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_view_range,
        shift_item=_shift_view,
        remap_overlap=remap_edited_wildcard if edited_wildcard is not None else None,
    )


def remap_wildcard_renderer_spans_for_edit(
    spans: Sequence[PromptWildcardRendererSpanView],
    *,
    start: int,
    end: int,
    delta: int,
    edited_wildcard: EditedWildcardIdentity | None = None,
) -> Sequence[PromptWildcardRendererSpanView]:
    """Retain edited presentation spans with provisional catalog state."""

    def remap_edited_wildcard(
        span: PromptWildcardRendererSpanView, offset: int
    ) -> PromptWildcardRendererSpanView | None:
        """Publish the new source identity without claiming catalog validity."""

        if edited_wildcard is None or _renderer_range(span) != edited_wildcard[0]:
            return None
        _, form, identifier, csv_column, tag = edited_wildcard
        identity_unchanged = (
            form == span.wildcard_form
            and identifier == span.identifier
            and csv_column == span.csv_column
        )
        display_tag = (
            tag if tag is not None else span.display_tag if identity_unchanged else None
        )
        return replace(
            span,
            outer_end=span.outer_end + offset,
            content_end=span.content_end + offset,
            wildcard_form=form,
            identifier=identifier,
            csv_column=csv_column,
            tag=tag,
            exists=span.exists if identity_unchanged else False,
            resolution_pending=not identity_unchanged,
            matched_csv_column=(
                span.matched_csv_column if identity_unchanged else None
            ),
            available_csv_columns=(
                span.available_csv_columns if identity_unchanged else ()
            ),
            source_key=f"{form}:{identifier}",
            display_text=(
                span.display_text
                if identity_unchanged
                else identifier + (f":{csv_column}" if csv_column is not None else "")
            ),
            display_tag=display_tag,
            tag_is_explicit=tag is not None,
            tag_is_numeric=is_numeric_wildcard_tag(display_tag),
            can_step_tag=is_numeric_wildcard_tag(display_tag),
            source_occurrence_count=(
                span.source_occurrence_count if identity_unchanged else 1
            ),
        )

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_renderer_range,
        shift_item=_shift_renderer_span,
        remap_overlap=remap_edited_wildcard if edited_wildcard is not None else None,
    )


def _view_range(span: PromptWildcardView) -> tuple[int, int]:
    """Return one wildcard view's outer source range."""

    return span.outer_start, span.outer_end


def _shift_view(span: PromptWildcardView, delta: int) -> PromptWildcardView:
    """Shift one unchanged wildcard view by a uniform source delta."""

    return replace(
        span,
        outer_start=span.outer_start + delta,
        outer_end=span.outer_end + delta,
        content_start=span.content_start + delta,
        content_end=span.content_end + delta,
    )


def _renderer_range(span: PromptWildcardRendererSpanView) -> tuple[int, int]:
    """Return one wildcard renderer span's outer source range."""

    return span.outer_start, span.outer_end


def _shift_renderer_span(
    span: PromptWildcardRendererSpanView, delta: int
) -> PromptWildcardRendererSpanView:
    """Shift one unchanged renderer span by a uniform source delta."""

    return replace(
        span,
        outer_start=span.outer_start + delta,
        outer_end=span.outer_end + delta,
        content_start=span.content_start + delta,
        content_end=span.content_end + delta,
    )


__all__ = [
    "EditedWildcardIdentity",
    "edited_wildcard_identity",
    "remap_wildcard_renderer_spans_for_edit",
    "remap_wildcard_views_for_edit",
]
