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

"""Project wildcard syntax into atomic semantic tokens."""

from __future__ import annotations

from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
    PromptWildcardRendererView,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.collapse_models import (
    PromptProjectionCollapseCandidate,
    contains_nested_supported_range,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)

_WILDCARD_KIND = "wildcard"


def build_wildcard_collapse_candidates(
    render_plan: PromptSyntaxRenderPlan,
    *,
    session: PromptProjectionSession,
    active_span_range: tuple[int, int] | None,
    decoration_accent_ranges: frozenset[tuple[int, int]],
    all_supported_ranges: tuple[tuple[int, int], ...],
) -> tuple[PromptProjectionCollapseCandidate, ...]:
    """Return wildcard tokens allowed by expansion and nesting state."""

    candidates: list[PromptProjectionCollapseCandidate] = []
    wildcard_view = wildcard_renderer_view_for_plan(render_plan)
    for index, span in enumerate(wildcard_view.wildcard_spans):
        token_range = (span.outer_start, span.outer_end)
        if session.expanded_source_range == token_range:
            continue
        if contains_nested_supported_range(token_range, all_supported_ranges):
            continue
        candidates.append(
            PromptProjectionCollapseCandidate(
                start=span.outer_start,
                end=span.outer_end,
                token=PromptProjectionToken(
                    token_id=f"wildcard:{index}:{span.outer_start}",
                    kind=PromptProjectionTokenKind.WILDCARD,
                    source_start=span.outer_start,
                    source_end=span.outer_end,
                    display_text=span.display_text,
                    value_text=span.identifier,
                    style_variant=span.wildcard_form,
                    wildcard_display_tag=span.display_tag,
                    wildcard_tag_is_explicit=span.tag_is_explicit,
                    wildcard_tag_is_numeric=span.tag_is_numeric,
                    wildcard_can_step_tag=span.can_step_tag,
                    exists=span.exists,
                    active=active_span_range == token_range,
                    decoration_accented=token_range in decoration_accent_ranges,
                    content_start=span.content_start,
                    content_end=span.content_end,
                    navigation_mode=PromptProjectionTokenNavigationMode.ATOMIC,
                ),
            )
        )
    return tuple(candidates)


def wildcard_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptWildcardRendererView:
    """Return the typed wildcard view registered in one render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_WILDCARD_KIND)
    if isinstance(renderer_view, PromptWildcardRendererView):
        return renderer_view
    return PromptWildcardRendererView(
        kind=_WILDCARD_KIND,
        syntax_spans=(),
        wildcard_spans=(),
    )


__all__ = ["build_wildcard_collapse_candidates", "wildcard_renderer_view_for_plan"]
