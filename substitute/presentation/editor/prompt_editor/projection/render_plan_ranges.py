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

"""Own projection-affecting render-plan range equivalence."""

from __future__ import annotations

from substitute.application.prompt_editor.projection.syntax_service import (
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxRendererView,
    PromptWildcardRendererView,
)

from .source_text_edit import PromptProjectionSourceTextEdit


def render_plan_ranges_match_after_source_edit(
    previous_render_plan: PromptSyntaxRenderPlan,
    next_render_plan: PromptSyntaxRenderPlan,
    *,
    edit: PromptProjectionSourceTextEdit,
) -> bool:
    """Return whether projection ranges remain equivalent after one source edit."""

    delta = len(edit.replacement_text) - (edit.end - edit.start)
    remapped_ranges: list[tuple[int, int]] = []
    for source_range in projection_affecting_render_plan_ranges(previous_render_plan):
        remapped_range = _remap_range_after_source_edit(
            source_range,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=delta,
        )
        if remapped_range is None:
            return False
        remapped_ranges.append(remapped_range)
    return tuple(remapped_ranges) == projection_affecting_render_plan_ranges(
        next_render_plan
    )


def projection_affecting_render_plan_ranges(
    render_plan: PromptSyntaxRenderPlan,
) -> tuple[tuple[int, int], ...]:
    """Return source ranges whose renderers replace text with projection tokens."""

    ranges: set[tuple[int, int]] = {
        (span.start, span.end)
        for span in render_plan.syntax_spans
        if span.end > span.start
    }
    for renderer_view in render_plan.renderer_views:
        ranges.update(_renderer_projection_ranges(renderer_view))
    return tuple(sorted(ranges))


def _renderer_projection_ranges(
    renderer_view: PromptSyntaxRendererView,
) -> tuple[tuple[int, int], ...]:
    """Return projection-affecting source ranges from one renderer view."""

    if isinstance(renderer_view, PromptEmphasisRendererView):
        return tuple(
            (span.outer_start, span.outer_end)
            for span in renderer_view.emphasis_spans
            if span.outer_end > span.outer_start
        )
    if isinstance(renderer_view, PromptWildcardRendererView):
        return tuple(
            (span.outer_start, span.outer_end)
            for span in renderer_view.wildcard_spans
            if span.outer_end > span.outer_start
        )
    if isinstance(renderer_view, PromptLoraRendererView):
        return tuple(
            (span.outer_start, span.outer_end)
            for span in renderer_view.lora_spans
            if span.outer_end > span.outer_start
        )
    return ()


def _remap_range_after_source_edit(
    source_range: tuple[int, int],
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
) -> tuple[int, int] | None:
    """Return one source range shifted across a non-overlapping edit."""

    range_start, range_end = source_range
    if edit_start == edit_end:
        if edit_start <= range_start:
            return range_start + delta, range_end + delta
        if edit_start >= range_end:
            return source_range
        return None
    if edit_end <= range_start:
        return range_start + delta, range_end + delta
    if edit_start >= range_end:
        return source_range
    return None


__all__ = [
    "projection_affecting_render_plan_ranges",
    "render_plan_ranges_match_after_source_edit",
]
