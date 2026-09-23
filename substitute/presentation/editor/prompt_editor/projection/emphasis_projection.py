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

"""Project emphasis syntax and transient neutral emphasis into tokens."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.document.visible_source import (
    map_prompt_source_for_display,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptEmphasisRendererView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.collapse_models import (
    PromptProjectionCollapseCandidate,
)
from substitute.presentation.editor.prompt_editor.projection.exact_weight_projection import (
    exact_weight_edit_for_token,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)

_EMPHASIS_KIND = "emphasis"


def build_emphasis_collapse_candidates(
    document_view: PromptDocumentView,
    render_plan: PromptSyntaxRenderPlan,
    *,
    session: PromptProjectionSession,
    active_span_range: tuple[int, int] | None,
    decoration_accent_ranges: frozenset[tuple[int, int]],
) -> tuple[PromptProjectionCollapseCandidate, ...]:
    """Return collapsed emphasis tokens allowed by current session state."""

    emphasis_view = emphasis_renderer_view_for_plan(render_plan)
    candidates: list[PromptProjectionCollapseCandidate] = []
    for index, emphasis_span in enumerate(emphasis_view.emphasis_spans):
        candidate = _emphasis_candidate(
            document_view,
            session=session,
            index=index,
            source_start=emphasis_span.outer_start,
            source_end=emphasis_span.outer_end,
            content_start=emphasis_span.content_start,
            content_end=emphasis_span.content_end,
            value_text=emphasis_span.weight_text,
            synthetic=False,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
        )
        if candidate is not None:
            candidates.append(candidate)
    transient = session.transient_neutral_emphasis
    if transient is None:
        return tuple(candidates)
    if any(
        span.content_start == transient.content_start
        and span.content_end == transient.content_end
        for span in emphasis_view.emphasis_spans
    ):
        return tuple(candidates)
    if any(
        span.outer_start <= transient.content_start < span.content_start
        and transient.content_end <= span.outer_end
        for span in emphasis_view.emphasis_spans
    ):
        return tuple(candidates)
    transient_candidate = _emphasis_candidate(
        document_view,
        session=session,
        index=None,
        source_start=transient.content_start,
        source_end=transient.content_end,
        content_start=transient.content_start,
        content_end=transient.content_end,
        value_text=transient.display_weight_text,
        synthetic=True,
        active_span_range=active_span_range,
        decoration_accent_ranges=decoration_accent_ranges,
    )
    if transient_candidate is not None:
        candidates.append(transient_candidate)
    return tuple(candidates)


def emphasis_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptEmphasisRendererView:
    """Return the typed emphasis view registered in one render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_EMPHASIS_KIND)
    if isinstance(renderer_view, PromptEmphasisRendererView):
        return renderer_view
    return PromptEmphasisRendererView(
        kind=_EMPHASIS_KIND,
        syntax_spans=(),
        emphasis_spans=(),
    )


def _emphasis_candidate(
    document_view: PromptDocumentView,
    *,
    session: PromptProjectionSession,
    index: int | None,
    source_start: int,
    source_end: int,
    content_start: int,
    content_end: int,
    value_text: str,
    synthetic: bool,
    active_span_range: tuple[int, int] | None,
    decoration_accent_ranges: frozenset[tuple[int, int]],
) -> PromptProjectionCollapseCandidate | None:
    """Build one emphasis candidate when expansion and nesting permit it."""

    token_range = (source_start, source_end)
    if session.expanded_source_range == token_range:
        return None
    token_id = (
        f"transient-emphasis:{source_start}"
        if synthetic
        else f"emphasis:{index}:{source_start}"
    )
    exact_weight_edit = exact_weight_edit_for_token(
        session,
        token_id=token_id,
        content_start=content_start,
        content_end=content_end,
    )
    return PromptProjectionCollapseCandidate(
        start=source_start,
        end=source_end,
        token=PromptProjectionToken(
            token_id=token_id,
            kind=PromptProjectionTokenKind.EMPHASIS,
            source_start=source_start,
            source_end=source_end,
            display_text=map_prompt_source_for_display(
                document_view.source_text[content_start:content_end],
                source_start=content_start,
            ).display_text,
            value_text=value_text,
            active=active_span_range == token_range,
            decoration_accented=token_range in decoration_accent_ranges,
            synthetic=synthetic,
            content_start=content_start,
            content_end=content_end,
            editing_value_text=(
                None if exact_weight_edit is None else exact_weight_edit.value_text
            ),
            editing_slot_width=(
                None if exact_weight_edit is None else exact_weight_edit.slot_width
            ),
            editing_caret_index=(
                None if exact_weight_edit is None else exact_weight_edit.caret_index
            ),
            editing_select_all=(
                False if exact_weight_edit is None else exact_weight_edit.select_all
            ),
            navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
        ),
    )


__all__ = ["build_emphasis_collapse_candidates", "emphasis_renderer_view_for_plan"]
