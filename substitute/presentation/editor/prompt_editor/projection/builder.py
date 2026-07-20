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

"""Build run-based prompt projections from application-owned prompt snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from hashlib import blake2s

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.prompt_editor.prompt_lora_diagnostics import (
    lora_prompt_context,
    lora_source_range_context,
)
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptEmphasisRendererView,
    PromptLoraRendererSpanView,
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
    PromptWildcardRendererView,
)
from substitute.application.prompt_editor import parse_prompt_scene_projection_document
from substitute.shared.logging.logger import get_logger, log_debug

from .caret_map_builder import build_prompt_projection_caret_map
from .model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
    PromptProjectionTransientState,
)
from .session import PromptProjectionSession

_EMPHASIS_KIND = "emphasis"
_EMPHASIS_PREFIX_RENDERER_KEY = "emphasis_prefix"
_EMPHASIS_SUFFIX_RENDERER_KEY = "emphasis_suffix"
_LORA_KIND = "lora"
_LORA_CHIP_RENDERER_KEY = "lora_chip"
_WILDCARD_KIND = "wildcard"
_WILDCARD_CHIP_RENDERER_KEY = "wildcard_chip"
_LOGGER = get_logger("presentation.editor.prompt_editor.projection_builder")


@dataclass(frozen=True, slots=True)
class _ExactWeightEditProjection:
    """Describe one projection-owned exact-edit state matched onto a token."""

    value_text: str
    slot_width: float
    caret_index: int
    select_all: bool


@dataclass(frozen=True, slots=True)
class _CollapseCandidate:
    """Describe one syntax span that should collapse into a projected token."""

    start: int
    end: int
    token: PromptProjectionToken


@dataclass(frozen=True, slots=True)
class _PromptLoraProjectionCollapseSummary:
    """Summarize LoRA collapse decisions for one projection build."""

    source_text_length: int
    render_plan_syntax_count: int
    all_supported_range_count: int
    renderer_lora_span_count: int
    lora_candidate_count: int
    lora_skipped_expanded_count: int
    lora_skipped_nested_count: int
    expanded_source_start: int | None
    expanded_source_end: int | None
    display_mode: str
    projected_lora_chip_count: int


class PromptProjectionBuilder:
    """Build one run-based prompt projection from source text plus syntax state."""

    def build_projection(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None = None,
        decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
        scene_error_keys: frozenset[str] = frozenset(),
        transient_state: PromptProjectionTransientState | None = None,
    ) -> PromptProjectionDocument:
        """Build the current prompt projection document for the requested display mode."""

        active_transient_state = transient_state or PromptProjectionTransientState()
        collapse_candidates = self._collapse_candidates(
            document_view,
            render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        tokens = tuple(candidate.token for candidate in collapse_candidates)
        source_text = document_view.source_text

        if display_mode is PromptProjectionDisplayMode.RAW:
            runs = self._raw_runs(source_text)
        else:
            runs = self._projected_runs(
                source_text,
                collapse_candidates=collapse_candidates,
            )
        runs = self._runs_with_transient_state(
            runs,
            source_text=source_text,
            transient_state=active_transient_state,
        )

        projection_text = "".join(
            run.display_text
            if run.kind is PromptProjectionRunKind.TEXT
            else OBJECT_REPLACEMENT_CHARACTER
            for run in runs
        )
        mapping = PromptProjectionMapping(
            runs=runs,
            source_length=len(source_text),
            projection_length=len(projection_text),
        )
        caret_map = build_prompt_projection_caret_map(
            runs=runs,
            tokens=tokens,
            source_length=len(source_text),
            projection_length=len(projection_text),
        )
        projection_document = PromptProjectionDocument(
            display_mode=display_mode,
            source_text=source_text,
            projection_text=projection_text,
            runs=runs,
            tokens=tokens,
            mapping=mapping,
            caret_map=caret_map,
        )
        return projection_document

    def _raw_runs(self, source_text: str) -> tuple[PromptProjectionRun, ...]:
        """Build the raw-mode visible run stream for the supplied source text."""

        if not source_text:
            return ()
        return (
            PromptProjectionRun(
                run_id="raw:0",
                kind=PromptProjectionRunKind.TEXT,
                source_start=0,
                source_end=len(source_text),
                display_text=source_text,
                source_positions=range(0, len(source_text) + 1),
                projection_start=0,
                projection_end=len(source_text),
            ),
        )

    def _projected_runs(
        self,
        source_text: str,
        *,
        collapse_candidates: tuple[_CollapseCandidate, ...],
    ) -> tuple[PromptProjectionRun, ...]:
        """Build the projected visible run stream from the supplied collapse candidates."""

        collapse_by_start = {
            candidate.start: candidate for candidate in collapse_candidates
        }
        runs: list[PromptProjectionRun] = []
        run_index = 0
        projection_position = 0
        plain_start = 0
        source_index = 0

        while source_index < len(source_text):
            candidate = collapse_by_start.get(source_index)
            if candidate is None:
                source_index += 1
                continue

            plain_run = self._plain_text_run(
                source_text,
                start=plain_start,
                end=candidate.start,
                run_index=run_index,
                projection_position=projection_position,
            )
            if plain_run is not None:
                runs.append(plain_run)
                run_index += 1
                projection_position = plain_run.projection_end

            candidate_runs = self._projected_token_runs(
                candidate.token,
                run_index=run_index,
                projection_position=projection_position,
            )
            runs.extend(candidate_runs)
            if candidate_runs:
                run_index += len(candidate_runs)
                projection_position = candidate_runs[-1].projection_end

            source_index = candidate.end
            plain_start = source_index

        trailing_plain_run = self._plain_text_run(
            source_text,
            start=plain_start,
            end=len(source_text),
            run_index=run_index,
            projection_position=projection_position,
        )
        if trailing_plain_run is not None:
            runs.append(trailing_plain_run)

        return tuple(runs)

    def _runs_with_transient_state(
        self,
        runs: tuple[PromptProjectionRun, ...],
        *,
        source_text: str,
        transient_state: PromptProjectionTransientState,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return projection runs with projection-owned transient inline state."""

        preview = transient_state.autocomplete_preview
        if preview is None:
            return runs
        return self._runs_with_inline_preview(
            runs,
            source_length=len(source_text),
            preview=preview,
        )

    def _runs_with_inline_preview(
        self,
        runs: tuple[PromptProjectionRun, ...],
        *,
        source_length: int,
        preview: PromptProjectionInlinePreview,
    ) -> tuple[PromptProjectionRun, ...]:
        """Insert one non-source-backed inline preview run when source-owned."""

        if not preview.suffix_text:
            return runs
        if preview.source_position < 0 or preview.source_position > source_length:
            return runs
        insertion = _inline_preview_insertion(
            runs,
            source_position=preview.source_position,
        )
        if insertion is None:
            return runs
        insertion_run = runs[insertion.run_index]
        local_index = insertion.local_boundary_index
        next_runs: list[PromptProjectionRun] = []
        next_runs.extend(runs[: insertion.run_index])
        next_runs.extend(_split_left_run(insertion_run, local_index))
        next_runs.append(
            _inline_preview_run(
                source_position=preview.source_position,
                suffix_text=preview.suffix_text,
                insertion_run=insertion_run,
            )
        )
        next_runs.extend(_split_right_run(insertion_run, local_index))
        next_runs.extend(runs[insertion.run_index + 1 :])
        return _runs_with_recomputed_projection_ranges(tuple(next_runs))

    def _plain_text_run(
        self,
        source_text: str,
        *,
        start: int,
        end: int,
        run_index: int,
        projection_position: int,
    ) -> PromptProjectionRun | None:
        """Build one visible plain-text run when the supplied source range is non-empty."""

        if end <= start:
            return None
        display_text, source_positions = (
            _display_text_and_source_positions_for_plain_run(
                source_text[start:end],
                source_start=start,
            )
        )
        return PromptProjectionRun(
            run_id=f"text:{run_index}:{start}",
            kind=PromptProjectionRunKind.TEXT,
            source_start=start,
            source_end=end,
            display_text=display_text,
            source_positions=source_positions,
            projection_start=projection_position,
            projection_end=projection_position + len(display_text),
        )

    def _projected_token_runs(
        self,
        token: PromptProjectionToken,
        *,
        run_index: int,
        projection_position: int,
    ) -> tuple[PromptProjectionRun, ...]:
        """Build the visible run stream for one projected semantic token."""

        return self._projected_token_runs_uninstrumented(
            token,
            run_index=run_index,
            projection_position=projection_position,
        )

    def _projected_token_runs_uninstrumented(
        self,
        token: PromptProjectionToken,
        *,
        run_index: int,
        projection_position: int,
    ) -> tuple[PromptProjectionRun, ...]:
        """Build token runs after the public helper starts temporary timing."""

        if token.kind is PromptProjectionTokenKind.EMPHASIS:
            assert token.content_start is not None
            assert token.content_end is not None
            prefix_run = PromptProjectionRun(
                run_id=f"emphasis-prefix:{token.token_id}",
                kind=PromptProjectionRunKind.INLINE_OBJECT,
                source_start=token.source_start,
                source_end=token.content_start,
                display_text="(",
                source_positions=(token.source_start, token.content_start),
                projection_start=projection_position,
                projection_end=projection_position + 1,
                token_id=token.token_id,
                renderer_key=_EMPHASIS_PREFIX_RENDERER_KEY,
                role=PromptProjectionRunRole.TOKEN_LEADING_DECORATION,
                active=token.active,
            )
            content_run = PromptProjectionRun(
                run_id=f"emphasis-content:{token.token_id}",
                kind=PromptProjectionRunKind.TEXT,
                source_start=token.content_start,
                source_end=token.content_end,
                display_text=token.display_text,
                source_positions=tuple(
                    range(token.content_start, token.content_end + 1)
                ),
                projection_start=prefix_run.projection_end,
                projection_end=prefix_run.projection_end + len(token.display_text),
                token_id=token.token_id,
                active=token.active,
            )
            suffix_run = PromptProjectionRun(
                run_id=f"emphasis-suffix:{token.token_id}",
                kind=PromptProjectionRunKind.INLINE_OBJECT,
                source_start=token.content_end,
                source_end=token.source_end,
                display_text=token.value_text or "",
                source_positions=(token.content_end, token.source_end),
                projection_start=content_run.projection_end,
                projection_end=content_run.projection_end + 1,
                token_id=token.token_id,
                renderer_key=_EMPHASIS_SUFFIX_RENDERER_KEY,
                role=PromptProjectionRunRole.TOKEN_TRAILING_DECORATION,
                active=token.active,
            )
            return (prefix_run, content_run, suffix_run)

        if token.kind is PromptProjectionTokenKind.SCENE:
            assert token.content_start is not None
            assert token.content_end is not None
            return (
                PromptProjectionRun(
                    run_id=f"scene-title:{token.token_id}",
                    kind=PromptProjectionRunKind.TEXT,
                    source_start=token.content_start,
                    source_end=token.content_end,
                    display_text=token.display_text,
                    source_positions=tuple(
                        range(token.content_start, token.content_end + 1)
                    ),
                    projection_start=projection_position,
                    projection_end=projection_position + len(token.display_text),
                    token_id=token.token_id,
                    active=token.active,
                    text_style_variant=token.style_variant,
                ),
            )

        wildcard_run = PromptProjectionRun(
            run_id=f"lora-chip:{token.token_id}",
            kind=PromptProjectionRunKind.INLINE_OBJECT,
            source_start=token.source_start,
            source_end=token.source_end,
            display_text=token.display_text,
            source_positions=(token.source_start, token.source_end),
            projection_start=projection_position,
            projection_end=projection_position + 1,
            token_id=token.token_id,
            renderer_key=_LORA_CHIP_RENDERER_KEY,
            active=token.active,
        )
        if token.kind is PromptProjectionTokenKind.LORA:
            return (wildcard_run,)

        wildcard_run = PromptProjectionRun(
            run_id=f"wildcard-chip:{token.token_id}",
            kind=PromptProjectionRunKind.INLINE_OBJECT,
            source_start=token.source_start,
            source_end=token.source_end,
            display_text=token.display_text,
            source_positions=(token.source_start, token.source_end),
            projection_start=projection_position,
            projection_end=projection_position + 1,
            token_id=token.token_id,
            renderer_key=_WILDCARD_CHIP_RENDERER_KEY,
            active=token.active,
        )
        return (wildcard_run,)

    def _collapse_candidates(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> tuple[_CollapseCandidate, ...]:
        """Return the syntax spans that should collapse into semantic projection tokens."""

        emphasis_view = _emphasis_renderer_view_for_plan(render_plan)
        lora_view = _lora_renderer_view_for_plan(render_plan)
        wildcard_view = _wildcard_renderer_view_for_plan(render_plan)
        all_supported_ranges = tuple(
            (span.start, span.end) for span in render_plan.syntax_spans
        )
        accent_range_set = frozenset(decoration_accent_ranges)
        lora_candidate_count = 0
        lora_skipped_expanded_count = 0
        lora_skipped_nested_count = 0
        candidates: list[_CollapseCandidate] = []

        scene_document = parse_prompt_scene_projection_document(
            document_view.source_text
        )
        for index, scene_block in enumerate(scene_document.scenes):
            marker = scene_block.marker
            invalid = marker.duplicate or marker.normalized_key in scene_error_keys
            candidates.append(
                _CollapseCandidate(
                    start=marker.line_range.start,
                    end=marker.line_range.end,
                    token=PromptProjectionToken(
                        token_id=f"scene:{index}:{marker.line_range.start}",
                        kind=PromptProjectionTokenKind.SCENE,
                        source_start=marker.line_range.start,
                        source_end=marker.line_range.end,
                        display_text=marker.title,
                        value_text=marker.normalized_key,
                        style_variant="scene_error" if invalid else "scene_title",
                        exists=not invalid,
                        content_start=marker.title_range.start,
                        content_end=marker.title_range.end,
                        navigation_mode=(
                            PromptProjectionTokenNavigationMode.TEXT_CONTENT
                        ),
                    ),
                )
            )

        for index, emphasis_span in enumerate(emphasis_view.emphasis_spans):
            token_range = (emphasis_span.outer_start, emphasis_span.outer_end)
            if session.expanded_source_range == token_range:
                continue
            if _contains_nested_supported_range(token_range, all_supported_ranges):
                continue
            exact_weight_edit = _exact_weight_edit_for_emphasis_token(
                session,
                token_id=f"emphasis:{index}:{emphasis_span.outer_start}",
                content_start=emphasis_span.content_start,
                content_end=emphasis_span.content_end,
            )
            candidates.append(
                _CollapseCandidate(
                    start=emphasis_span.outer_start,
                    end=emphasis_span.outer_end,
                    token=PromptProjectionToken(
                        token_id=f"emphasis:{index}:{emphasis_span.outer_start}",
                        kind=PromptProjectionTokenKind.EMPHASIS,
                        source_start=emphasis_span.outer_start,
                        source_end=emphasis_span.outer_end,
                        display_text=document_view.source_text[
                            emphasis_span.content_start : emphasis_span.content_end
                        ],
                        value_text=emphasis_span.weight_text,
                        active=active_span_range == token_range,
                        decoration_accented=token_range in accent_range_set,
                        content_start=emphasis_span.content_start,
                        content_end=emphasis_span.content_end,
                        editing_value_text=(
                            None
                            if exact_weight_edit is None
                            else exact_weight_edit.value_text
                        ),
                        editing_slot_width=(
                            None
                            if exact_weight_edit is None
                            else exact_weight_edit.slot_width
                        ),
                        editing_caret_index=(
                            None
                            if exact_weight_edit is None
                            else exact_weight_edit.caret_index
                        ),
                        editing_select_all=(
                            False
                            if exact_weight_edit is None
                            else exact_weight_edit.select_all
                        ),
                        navigation_mode=(
                            PromptProjectionTokenNavigationMode.TEXT_CONTENT
                        ),
                    ),
                )
            )

        transient_neutral_emphasis = session.transient_neutral_emphasis
        if transient_neutral_emphasis is not None:
            token_range = (
                transient_neutral_emphasis.content_start,
                transient_neutral_emphasis.content_end,
            )
            if (
                session.expanded_source_range != token_range
                and not any(
                    span.content_start == transient_neutral_emphasis.content_start
                    and span.content_end == transient_neutral_emphasis.content_end
                    for span in emphasis_view.emphasis_spans
                )
                and not _contains_nested_supported_range(
                    token_range, all_supported_ranges
                )
            ):
                exact_weight_edit = _exact_weight_edit_for_emphasis_token(
                    session,
                    token_id=(
                        f"transient-emphasis:{transient_neutral_emphasis.content_start}"
                    ),
                    content_start=transient_neutral_emphasis.content_start,
                    content_end=transient_neutral_emphasis.content_end,
                )
                candidates.append(
                    _CollapseCandidate(
                        start=transient_neutral_emphasis.content_start,
                        end=transient_neutral_emphasis.content_end,
                        token=PromptProjectionToken(
                            token_id=(
                                "transient-emphasis:"
                                f"{transient_neutral_emphasis.content_start}"
                            ),
                            kind=PromptProjectionTokenKind.EMPHASIS,
                            source_start=transient_neutral_emphasis.content_start,
                            source_end=transient_neutral_emphasis.content_end,
                            display_text=document_view.source_text[
                                transient_neutral_emphasis.content_start : transient_neutral_emphasis.content_end
                            ],
                            value_text=transient_neutral_emphasis.display_weight_text,
                            active=active_span_range == token_range,
                            decoration_accented=token_range in accent_range_set,
                            synthetic=True,
                            content_start=transient_neutral_emphasis.content_start,
                            content_end=transient_neutral_emphasis.content_end,
                            editing_value_text=(
                                None
                                if exact_weight_edit is None
                                else exact_weight_edit.value_text
                            ),
                            editing_slot_width=(
                                None
                                if exact_weight_edit is None
                                else exact_weight_edit.slot_width
                            ),
                            editing_caret_index=(
                                None
                                if exact_weight_edit is None
                                else exact_weight_edit.caret_index
                            ),
                            editing_select_all=(
                                False
                                if exact_weight_edit is None
                                else exact_weight_edit.select_all
                            ),
                            navigation_mode=(
                                PromptProjectionTokenNavigationMode.TEXT_CONTENT
                            ),
                        ),
                    )
                )

        for index, wildcard_span in enumerate(wildcard_view.wildcard_spans):
            token_range = (wildcard_span.outer_start, wildcard_span.outer_end)
            if session.expanded_source_range == token_range:
                continue
            if _contains_nested_supported_range(token_range, all_supported_ranges):
                continue
            candidates.append(
                _CollapseCandidate(
                    start=wildcard_span.outer_start,
                    end=wildcard_span.outer_end,
                    token=PromptProjectionToken(
                        token_id=f"wildcard:{index}:{wildcard_span.outer_start}",
                        kind=PromptProjectionTokenKind.WILDCARD,
                        source_start=wildcard_span.outer_start,
                        source_end=wildcard_span.outer_end,
                        display_text=wildcard_span.display_text,
                        value_text=wildcard_span.identifier,
                        style_variant=wildcard_span.wildcard_form,
                        wildcard_display_tag=wildcard_span.display_tag,
                        wildcard_tag_is_explicit=wildcard_span.tag_is_explicit,
                        wildcard_tag_is_numeric=wildcard_span.tag_is_numeric,
                        wildcard_can_step_tag=wildcard_span.can_step_tag,
                        exists=wildcard_span.exists,
                        active=active_span_range == token_range,
                        decoration_accented=token_range in accent_range_set,
                        content_start=wildcard_span.content_start,
                        content_end=wildcard_span.content_end,
                        navigation_mode=PromptProjectionTokenNavigationMode.ATOMIC,
                    ),
                )
            )

        for index, lora_span in enumerate(lora_view.lora_spans):
            token_range = (lora_span.outer_start, lora_span.outer_end)
            if session.expanded_source_range == token_range:
                lora_skipped_expanded_count += 1
                _log_lora_projection_skip(
                    lora_span,
                    skip_reason="expanded_token",
                    expanded_source_range=session.expanded_source_range,
                )
                continue
            if _contains_nested_supported_range(token_range, all_supported_ranges):
                lora_skipped_nested_count += 1
                _log_lora_projection_skip(
                    lora_span,
                    skip_reason="nested_supported_range",
                    expanded_source_range=session.expanded_source_range,
                )
                continue
            exact_weight_edit = _exact_weight_edit_for_emphasis_token(
                session,
                token_id=f"lora:{index}:{lora_span.outer_start}",
                content_start=lora_span.name_start,
                content_end=lora_span.name_end,
            )
            lora_candidate_count += 1
            candidates.append(
                _CollapseCandidate(
                    start=lora_span.outer_start,
                    end=lora_span.outer_end,
                    token=_lora_projection_token(
                        lora_span,
                        token_id=f"lora:{index}:{lora_span.outer_start}",
                        active=active_span_range == token_range,
                        exact_weight_edit=exact_weight_edit,
                    ),
                )
            )

        candidates.sort(key=lambda candidate: candidate.start)
        if lora_view.lora_spans:
            _log_lora_projection_collapse_summary(
                _lora_projection_collapse_summary(
                    document_view=document_view,
                    render_plan=render_plan,
                    all_supported_ranges=all_supported_ranges,
                    lora_view=lora_view,
                    lora_candidate_count=lora_candidate_count,
                    lora_skipped_expanded_count=lora_skipped_expanded_count,
                    lora_skipped_nested_count=lora_skipped_nested_count,
                    expanded_source_range=session.expanded_source_range,
                    display_mode=display_mode,
                    candidates=tuple(candidates),
                )
            )
        return tuple(candidates)


def _emphasis_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptEmphasisRendererView:
    """Return the emphasis renderer view registered for the supplied render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_EMPHASIS_KIND)
    if isinstance(renderer_view, PromptEmphasisRendererView):
        return renderer_view
    return PromptEmphasisRendererView(
        kind=_EMPHASIS_KIND,
        syntax_spans=(),
        emphasis_spans=(),
    )


def _wildcard_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptWildcardRendererView:
    """Return the wildcard renderer view registered for the supplied render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_WILDCARD_KIND)
    if isinstance(renderer_view, PromptWildcardRendererView):
        return renderer_view
    return PromptWildcardRendererView(
        kind=_WILDCARD_KIND,
        syntax_spans=(),
        wildcard_spans=(),
    )


def _lora_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptLoraRendererView:
    """Return the LoRA renderer view registered for the supplied render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_LORA_KIND)
    if isinstance(renderer_view, PromptLoraRendererView):
        return renderer_view
    return PromptLoraRendererView(
        kind=_LORA_KIND,
        syntax_spans=(),
        lora_spans=(),
    )


def _lora_projection_collapse_summary(
    *,
    document_view: PromptDocumentView,
    render_plan: PromptSyntaxRenderPlan,
    all_supported_ranges: tuple[tuple[int, int], ...],
    lora_view: PromptLoraRendererView,
    lora_candidate_count: int,
    lora_skipped_expanded_count: int,
    lora_skipped_nested_count: int,
    expanded_source_range: tuple[int, int] | None,
    display_mode: PromptProjectionDisplayMode,
    candidates: tuple[_CollapseCandidate, ...],
) -> _PromptLoraProjectionCollapseSummary:
    """Return aggregate LoRA collapse diagnostics for observability and tests."""

    projected_lora_chip_count = sum(
        1
        for candidate in candidates
        if candidate.token.kind is PromptProjectionTokenKind.LORA
    )
    return _PromptLoraProjectionCollapseSummary(
        source_text_length=len(document_view.source_text),
        render_plan_syntax_count=len(render_plan.syntax_spans),
        all_supported_range_count=len(all_supported_ranges),
        renderer_lora_span_count=len(lora_view.lora_spans),
        lora_candidate_count=lora_candidate_count,
        lora_skipped_expanded_count=lora_skipped_expanded_count,
        lora_skipped_nested_count=lora_skipped_nested_count,
        expanded_source_start=None
        if expanded_source_range is None
        else expanded_source_range[0],
        expanded_source_end=None
        if expanded_source_range is None
        else expanded_source_range[1],
        display_mode=display_mode.value,
        projected_lora_chip_count=projected_lora_chip_count,
    )


def _log_lora_projection_collapse_summary(
    summary: _PromptLoraProjectionCollapseSummary,
) -> None:
    """Emit one aggregate LoRA projection-collapse diagnostic event."""

    log_debug(
        _LOGGER,
        "prompt_lora_projection.collapse_summary",
        source_text_length=summary.source_text_length,
        render_plan_syntax_count=summary.render_plan_syntax_count,
        all_supported_range_count=summary.all_supported_range_count,
        renderer_lora_span_count=summary.renderer_lora_span_count,
        lora_candidate_count=summary.lora_candidate_count,
        lora_skipped_expanded_count=summary.lora_skipped_expanded_count,
        lora_skipped_nested_count=summary.lora_skipped_nested_count,
        expanded_source_start=summary.expanded_source_start,
        expanded_source_end=summary.expanded_source_end,
        display_mode=summary.display_mode,
        projected_lora_chip_count=summary.projected_lora_chip_count,
    )


def _log_lora_projection_skip(
    span: PromptLoraRendererSpanView,
    *,
    skip_reason: str,
    expanded_source_range: tuple[int, int] | None,
) -> None:
    """Emit one diagnostic event for a skipped LoRA projection candidate."""

    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    log_debug(
        _LOGGER,
        "prompt_lora_projection.skip",
        **lora_prompt_context(span.prompt_name),
        **lora_source_range_context(span.outer_start, span.outer_end),
        skip_reason=skip_reason,
        expanded_source_start=None
        if expanded_source_range is None
        else expanded_source_range[0],
        expanded_source_end=None
        if expanded_source_range is None
        else expanded_source_range[1],
    )


def _lora_projection_token(
    span: PromptLoraRendererSpanView,
    *,
    token_id: str,
    active: bool,
    exact_weight_edit: _ExactWeightEditProjection | None,
) -> PromptProjectionToken:
    """Build the projected token for one renderer-ready LoRA span."""

    return PromptProjectionToken(
        token_id=token_id,
        kind=PromptProjectionTokenKind.LORA,
        source_start=span.outer_start,
        source_end=span.outer_end,
        display_text=span.display_name,
        value_text=span.first_weight_text,
        status_text=_lora_status_text(span),
        detail_text=span.prompt_name,
        lora_status=span.lora_status,
        lora_status_reason=span.status_reason,
        lora_match_source=span.match_source,
        lora_authority=span.authority,
        lora_backend_value=span.backend_value,
        lora_version_text=span.display_subtitle,
        lora_trained_words=span.trained_words,
        model_page_url=span.model_page_url,
        thumbnail_variants=tuple(
            PromptProjectionThumbnailVariant(
                size=variant.size,
                storage_key=variant.storage_key,
                width=variant.width,
                height=variant.height,
                content_format=variant.content_format,
                byte_size=variant.byte_size,
                role=variant.role,
            )
            for variant in span.thumbnail_variants
        ),
        exists=span.exists,
        active=active,
        content_start=span.name_start,
        content_end=span.name_end,
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
        navigation_mode=PromptProjectionTokenNavigationMode.ATOMIC,
    )


def _lora_status_text(span: PromptLoraRendererSpanView) -> ApplicationText | None:
    """Return compact status text for a projected LoRA chip."""

    if span.lora_status.value == "missing":
        return app_text("Not found")
    if span.lora_status.value == "ambiguous":
        return app_text("Ambiguous")
    return None


def _contains_nested_supported_range(
    token_range: tuple[int, int],
    supported_ranges: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether one syntax span contains another supported syntax span."""

    return any(
        other_start >= token_range[0]
        and other_end <= token_range[1]
        and (other_start, other_end) != token_range
        for other_start, other_end in supported_ranges
    )


def _exact_weight_edit_for_emphasis_token(
    session: PromptProjectionSession,
    *,
    token_id: str,
    content_start: int,
    content_end: int,
) -> _ExactWeightEditProjection | None:
    """Return the active exact-edit state when it belongs to one emphasis token."""

    edit_state = session.exact_weight_edit
    if edit_state is None:
        return None
    if edit_state.token_id == token_id:
        return _ExactWeightEditProjection(
            value_text=edit_state.buffer_text,
            slot_width=edit_state.slot_width,
            caret_index=edit_state.caret_index,
            select_all=edit_state.select_all,
        )
    if (
        edit_state.synthetic
        and edit_state.content_start == content_start
        and edit_state.content_end == content_end
    ):
        return _ExactWeightEditProjection(
            value_text=edit_state.buffer_text,
            slot_width=edit_state.slot_width,
            caret_index=edit_state.caret_index,
            select_all=edit_state.select_all,
        )
    return None


def _display_text_and_source_positions_for_plain_run(
    source_text: str,
    *,
    source_start: int,
) -> tuple[str, Sequence[int]]:
    """Return visible text plus source boundary mapping for one plain source slice."""

    if "\\(" not in source_text and "\\)" not in source_text:
        return source_text, range(source_start, source_start + len(source_text) + 1)

    display_characters: list[str] = []
    source_positions: list[int] = [source_start]
    relative_index = 0

    while relative_index < len(source_text):
        character = source_text[relative_index]
        if (
            character == "\\"
            and relative_index + 1 < len(source_text)
            and source_text[relative_index + 1] in "()"
        ):
            display_characters.append(source_text[relative_index + 1])
            relative_index += 2
            source_positions.append(source_start + relative_index)
            continue

        display_characters.append(character)
        relative_index += 1
        source_positions.append(source_start + relative_index)

    return "".join(display_characters), tuple(source_positions)


@dataclass(frozen=True, slots=True)
class _InlinePreviewInsertion:
    """Identify where one transient inline preview belongs in the run stream."""

    run_index: int
    local_boundary_index: int


def _inline_preview_insertion(
    runs: tuple[PromptProjectionRun, ...],
    *,
    source_position: int,
) -> _InlinePreviewInsertion | None:
    """Return the source-backed text boundary that owns a preview insertion."""

    fallback: _InlinePreviewInsertion | None = None
    for run_index, run in enumerate(runs):
        if run.kind is not PromptProjectionRunKind.TEXT or not run.source_backed:
            continue
        try:
            local_boundary_index = _source_boundary_index(
                run.source_positions,
                source_position,
            )
        except ValueError:
            continue
        insertion = _InlinePreviewInsertion(
            run_index=run_index,
            local_boundary_index=local_boundary_index,
        )
        if local_boundary_index > 0:
            return insertion
        if fallback is None:
            fallback = insertion
    return fallback


def _source_boundary_index(
    source_positions: Sequence[int],
    source_position: int,
) -> int:
    """Return the first local boundary matching one source position."""

    for index, candidate_position in enumerate(source_positions):
        if candidate_position == source_position:
            return index
    raise ValueError(source_position)


def _split_left_run(
    run: PromptProjectionRun,
    local_index: int,
) -> tuple[PromptProjectionRun, ...]:
    """Return the left source-backed split run when it has visible text."""

    if local_index <= 0:
        return ()
    return (
        replace(
            run,
            run_id=f"{run.run_id}:preview-left",
            source_start=run.source_positions[0],
            source_end=run.source_positions[local_index],
            display_text=run.display_text[:local_index],
            source_positions=tuple(run.source_positions[: local_index + 1]),
            projection_start=0,
            projection_end=local_index,
        ),
    )


def _split_right_run(
    run: PromptProjectionRun,
    local_index: int,
) -> tuple[PromptProjectionRun, ...]:
    """Return the right source-backed split run when it has visible text."""

    if local_index >= len(run.display_text):
        return ()
    display_text = run.display_text[local_index:]
    return (
        replace(
            run,
            run_id=f"{run.run_id}:preview-right",
            source_start=run.source_positions[local_index],
            source_end=run.source_positions[-1],
            display_text=display_text,
            source_positions=tuple(run.source_positions[local_index:]),
            projection_start=0,
            projection_end=len(display_text),
        ),
    )


def _inline_preview_run(
    *,
    source_position: int,
    suffix_text: str,
    insertion_run: PromptProjectionRun,
) -> PromptProjectionRun:
    """Return one visible ghost run that does not contribute source text."""

    suffix_hash = blake2s(suffix_text.encode("utf-8"), digest_size=4).hexdigest()
    return PromptProjectionRun(
        run_id=f"inline-preview:{source_position}:{suffix_hash}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=source_position,
        source_end=source_position,
        display_text=suffix_text,
        source_positions=tuple(source_position for _ in range(len(suffix_text) + 1)),
        projection_start=0,
        projection_end=len(suffix_text),
        token_id=insertion_run.token_id,
        active=insertion_run.active,
        source_backed=False,
        ghosted=True,
        text_style_variant=insertion_run.text_style_variant,
    )


def _runs_with_recomputed_projection_ranges(
    runs: tuple[PromptProjectionRun, ...],
) -> tuple[PromptProjectionRun, ...]:
    """Return runs with contiguous projection ranges matching visible length."""

    next_runs: list[PromptProjectionRun] = []
    projection_position = 0
    for run in runs:
        run_length = len(run.display_text) if run.is_text else 1
        next_runs.append(
            replace(
                run,
                projection_start=projection_position,
                projection_end=projection_position + run_length,
            )
        )
        projection_position += run_length
    return tuple(next_runs)


__all__ = ["PromptProjectionBuilder"]
