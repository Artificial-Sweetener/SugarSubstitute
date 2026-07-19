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

"""Build conservative incremental projection edits for the prompt surface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from collections.abc import Sequence

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
    PromptSyntaxRendererView,
    PromptSyntaxSpanView,
    PromptWildcardRendererView,
)

from .caret_map_builder import build_prompt_projection_caret_map
from .model import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionToken,
)
from .layout_engine import (
    PromptProjectionIncrementalLayoutResult,
    PromptProjectionLayout,
)
from .session import PromptProjectionSession
from .scene_incremental_editor import PromptSceneProjectionIncrementalEditor


@dataclass(frozen=True, slots=True)
class PromptProjectionIncrementalEdit:
    """Describe one source edit considered for incremental projection."""

    start: int
    end: int
    replacement_text: str
    previous_source_text: str
    next_source_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionIncrementalDocumentResult:
    """Carry the updated projection document and its dirty boundaries."""

    projection_document: PromptProjectionDocument
    first_dirty_source_position: int
    first_dirty_projection_position: int
    reason: str
    edited_token_id: str | None = None
    projection_edit_start: int | None = None
    projection_edit_end: int | None = None
    projection_replacement_text: str | None = None


class PromptProjectionPlainTextApplyStatus(Enum):
    """Describe how one plain-text projection fast path handled an edit."""

    APPLIED = "applied"
    DEFERRED_WRAP_REFLOW = "deferred_wrap_reflow"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceTextEdit:
    """Describe one contiguous edit between projection source snapshots."""

    start: int
    end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionPlainTextApplyResult:
    """Carry the result of applying one plain-text projection edit to layout."""

    status: PromptProjectionPlainTextApplyStatus
    projection_document: PromptProjectionDocument | None = None
    layout_result: PromptProjectionIncrementalLayoutResult | None = None


class PromptProjectionIncrementalEditor:
    """Build supported plain-text projection edits without full rebuilds."""

    def __init__(self) -> None:
        """Initialize rejection state for the last attempted edit."""

        self.last_rejection_reason = ""
        self._scene_editor = PromptSceneProjectionIncrementalEditor()

    def fast_trailing_plain_insert_document(
        self,
        *,
        previous_document: PromptProjectionDocument,
        next_text: str,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing plain text insert."""

        previous_text = previous_document.source_text
        previous_length = len(previous_text)
        appended_text = next_text[previous_length:]
        if (
            len(next_text) <= previous_length
            or not next_text.startswith(previous_text)
            or not previous_document.runs
            or any(
                span_end > previous_length
                for _span_start, span_end in projection_affecting_render_plan_ranges(
                    render_plan
                )
            )
        ):
            return None
        if any(character in {"\n", "\r"} for character in appended_text):
            return None
        last_run = previous_document.runs[-1]
        if (
            not last_run.is_text
            or not last_run.source_backed
            or last_run.token_id is not None
            or last_run.source_end != previous_length
            or last_run.projection_end != previous_document.mapping.projection_length
            or len(last_run.source_positions) < 1
            or last_run.source_positions[-1] != previous_length
        ):
            return None

        appended_length = len(appended_text)
        next_projection_length = (
            previous_document.mapping.projection_length + appended_length
        )
        next_run = replace(
            last_run,
            source_end=previous_length + appended_length,
            display_text=last_run.display_text + appended_text,
            source_positions=_extend_contiguous_source_positions(
                last_run.source_positions,
                source_start=last_run.source_start,
                previous_source_end=previous_length,
                next_source_end=previous_length + appended_length,
            ),
            projection_end=last_run.projection_end + appended_length,
        )
        next_runs = previous_document.runs[:-1] + (next_run,)
        next_caret_map = build_prompt_projection_caret_map(
            runs=next_runs,
            tokens=previous_document.tokens,
            source_length=len(next_text),
            projection_length=next_projection_length,
        )
        return replace(
            previous_document,
            source_text=next_text,
            projection_text=previous_document.projection_text + appended_text,
            runs=next_runs,
            mapping=PromptProjectionMapping(
                runs=next_runs,
                source_length=len(next_text),
                projection_length=next_projection_length,
            ),
            caret_map=next_caret_map,
        )

    def fast_trailing_newline_insert_document(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing hard-line insert."""

        previous_length = len(previous_text)
        if (
            start != previous_length
            or end != previous_length
            or next_text != f"{previous_text}\n"
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or any(
                span_end > previous_length
                for _span_start, span_end in projection_affecting_render_plan_ranges(
                    render_plan
                )
            )
        ):
            return None
        last_run = previous_document.runs[-1]
        if (
            not last_run.is_text
            or not last_run.source_backed
            or last_run.token_id is not None
            or last_run.source_end != previous_length
            or last_run.projection_end != previous_document.mapping.projection_length
            or len(last_run.source_positions) < 1
            or last_run.source_positions[-1] != previous_length
        ):
            return None

        next_projection_length = previous_document.mapping.projection_length + 1
        next_run = replace(
            last_run,
            source_end=previous_length + 1,
            display_text=f"{last_run.display_text}\n",
            source_positions=_extend_contiguous_source_positions(
                last_run.source_positions,
                source_start=last_run.source_start,
                previous_source_end=previous_length,
                next_source_end=previous_length + 1,
            ),
            projection_end=last_run.projection_end + 1,
        )
        next_runs = previous_document.runs[:-1] + (next_run,)
        next_caret_map = build_prompt_projection_caret_map(
            runs=next_runs,
            tokens=previous_document.tokens,
            source_length=len(next_text),
            projection_length=next_projection_length,
        )
        return replace(
            previous_document,
            source_text=next_text,
            projection_text=f"{previous_document.projection_text}\n",
            runs=next_runs,
            mapping=PromptProjectionMapping(
                runs=next_runs,
                source_length=len(next_text),
                projection_length=next_projection_length,
            ),
            caret_map=next_caret_map,
        )

    def fast_trailing_plain_delete_document(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a one-character trailing text delete."""

        if (
            start != len(previous_text) - 1
            or end != len(previous_text)
            or next_text != previous_text[:start]
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or previous_document.projection_text == ""
        ):
            return None
        last_run = previous_document.runs[-1]
        if (
            not last_run.is_text
            or not last_run.source_backed
            or last_run.token_id is not None
            or last_run.source_end != end
            or last_run.projection_end != previous_document.mapping.projection_length
            or len(last_run.source_positions) < 2
            or last_run.source_positions[-2] != start
            or last_run.source_positions[-1] != end
            or not last_run.display_text
        ):
            return None

        next_projection_text = previous_document.projection_text[:-1]
        next_projection_length = len(next_projection_text)
        next_display_text = last_run.display_text[:-1]
        next_run = replace(
            last_run,
            source_end=start,
            display_text=next_display_text,
            source_positions=last_run.source_positions[:-1],
            projection_end=last_run.projection_end - 1,
        )
        next_runs = (
            previous_document.runs[:-1] + (next_run,)
            if next_display_text
            else previous_document.runs[:-1]
        )
        next_caret_map = build_prompt_projection_caret_map(
            runs=next_runs,
            tokens=previous_document.tokens,
            source_length=len(next_text),
            projection_length=next_projection_length,
        )
        return replace(
            previous_document,
            source_text=next_text,
            projection_text=next_projection_text,
            runs=next_runs,
            mapping=PromptProjectionMapping(
                runs=next_runs,
                source_length=len(next_text),
                projection_length=next_projection_length,
            ),
            caret_map=next_caret_map,
        )

    def fast_trailing_newline_delete_document(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing hard-line delete."""

        if (
            start != len(previous_text) - 1
            or end != len(previous_text)
            or not previous_text.endswith("\n")
            or next_text != previous_text[:-1]
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or not previous_document.projection_text.endswith("\n")
        ):
            return None
        last_run = previous_document.runs[-1]
        if (
            not last_run.is_text
            or not last_run.source_backed
            or last_run.token_id is not None
            or last_run.source_end != end
            or last_run.projection_end != previous_document.mapping.projection_length
            or len(last_run.source_positions) < 2
            or last_run.source_positions[-2] != start
            or last_run.source_positions[-1] != end
            or not last_run.display_text.endswith("\n")
        ):
            return None

        next_projection_length = previous_document.mapping.projection_length - 1
        next_display_text = last_run.display_text[:-1]
        next_run = replace(
            last_run,
            source_end=start,
            display_text=next_display_text,
            source_positions=last_run.source_positions[:-1],
            projection_end=last_run.projection_end - 1,
        )
        next_runs = (
            previous_document.runs[:-1] + (next_run,)
            if next_display_text
            else previous_document.runs[:-1]
        )
        next_caret_map = build_prompt_projection_caret_map(
            runs=next_runs,
            tokens=previous_document.tokens,
            source_length=len(next_text),
            projection_length=next_projection_length,
        )
        return replace(
            previous_document,
            source_text=next_text,
            projection_text=previous_document.projection_text[:-1],
            runs=next_runs,
            mapping=PromptProjectionMapping(
                runs=next_runs,
                source_length=len(next_text),
                projection_length=next_projection_length,
            ),
            caret_map=next_caret_map,
        )

    def try_apply_plain_text_layout_edit(
        self,
        edit: PromptProjectionIncrementalEdit,
        *,
        layout: PromptProjectionLayout,
        previous_document: PromptProjectionDocument,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionPlainTextApplyResult:
        """Apply a supported plain-text edit to projection document and layout."""

        document_result = self.try_build_plain_text_edit(
            edit,
            previous_document=previous_document,
            document_view=document_view,
            render_plan=render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        if document_result is None:
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED
            )

        if edit.replacement_text == "\n" or (
            edit.replacement_text == ""
            and edit.previous_source_text[edit.start : edit.end] == "\n"
        ):
            layout_result = layout.try_apply_hard_line_break_edit(
                document_result.projection_document,
                prompt_document_view=document_view,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                first_dirty_projection_position=(
                    document_result.first_dirty_projection_position
                ),
            )
        else:
            layout_result = layout.try_apply_same_line_plain_text_edit(
                document_result.projection_document,
                prompt_document_view=document_view,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                first_dirty_projection_position=(
                    document_result.first_dirty_projection_position
                ),
                editable_token_id=document_result.edited_token_id,
                projection_edit_start=document_result.projection_edit_start,
                projection_edit_end=document_result.projection_edit_end,
                projection_replacement_text=(
                    document_result.projection_replacement_text
                ),
            )
        if layout_result is None:
            rejection_reason = layout.last_incremental_reflow_rejection_reason
            if rejection_reason in {"edit_would_wrap", "word_wrap_boundary"}:
                return PromptProjectionPlainTextApplyResult(
                    status=PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW
                )
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED
            )

        return PromptProjectionPlainTextApplyResult(
            status=PromptProjectionPlainTextApplyStatus.APPLIED,
            projection_document=document_result.projection_document,
            layout_result=layout_result,
        )

    def try_build_plain_text_edit(
        self,
        edit: PromptProjectionIncrementalEdit,
        *,
        previous_document: PromptProjectionDocument,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionIncrementalDocumentResult | None:
        """Return an incremental projection document for a safe plain text edit."""

        del active_span_range, decoration_accent_ranges
        self.last_rejection_reason = ""
        if display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return self._reject("display_mode_not_projected")
        if previous_document.source_text != edit.previous_source_text:
            return self._reject("previous_source_mismatch")
        if document_view.source_text != edit.next_source_text:
            return self._reject("document_view_source_mismatch")
        if (
            edit.previous_source_text[: edit.start]
            + edit.replacement_text
            + edit.previous_source_text[edit.end :]
            != edit.next_source_text
        ):
            return self._reject("edit_text_mismatch")
        if not _is_supported_plain_text_incremental_edit(edit):
            return self._reject("unsupported_plain_text_incremental_edit")
        edited_run = _source_backed_plain_text_run_for_edit(
            edit,
            previous_document.runs,
        )
        edited_scene_run = self._scene_editor.editable_title_run(
            previous_document=previous_document,
            start=edit.start,
            end=edit.end,
            replacement_text=edit.replacement_text,
        )
        if edited_scene_run is not None:
            edited_run = edited_scene_run
        editable_token_id = (
            None if edited_scene_run is None else edited_scene_run.token_id
        )
        if _edit_intersects_token(
            edit,
            previous_document.tokens,
            editable_token_id=editable_token_id,
        ):
            return self._reject("edit_intersects_token")
        if _edit_intersects_syntax_span(edit, render_plan.syntax_spans):
            return self._reject("edit_intersects_syntax_span")
        if edited_run is None:
            return self._reject("no_source_backed_plain_text_run")
        if (
            edit.replacement_text == ""
            and len(edited_run.display_text) <= edit.end - edit.start
        ):
            return self._reject("delete_would_empty_run")

        first_dirty_projection_position = _projection_position_for_source_boundary(
            edited_run,
            edit.start,
        )
        if (
            first_dirty_projection_position is None
            and edited_scene_run is not None
            and edit.start >= edited_scene_run.source_end
        ):
            first_dirty_projection_position = edited_scene_run.projection_end
        if first_dirty_projection_position is None:
            return self._reject("source_boundary_not_projected")

        del session
        try:
            projection_document = _apply_plain_text_document_edit(
                edit,
                previous_document=previous_document,
                edited_run=edited_run,
                first_dirty_projection_position=first_dirty_projection_position,
                editable_token_id=editable_token_id,
            )
        except ValueError:
            return self._reject("invalid_incremental_projection_document")
        if editable_token_id is not None:
            assert edited_scene_run is not None
            scene_result = self._scene_editor.reconcile_document(
                projection_document,
                edited_token_id=editable_token_id,
                previous_title=edited_scene_run.display_text,
                scene_error_keys=scene_error_keys,
            )
            if scene_result is None:
                return self._reject("scene_title_edit_requires_canonical_projection")
            projection_document = scene_result.document
            projection_edit_start = scene_result.projection_start
            projection_edit_end = scene_result.projection_end
            projection_replacement_text = scene_result.projection_replacement_text
        else:
            projection_edit_start = first_dirty_projection_position
            projection_edit_end = first_dirty_projection_position + (
                edit.end - edit.start
            )
            projection_replacement_text = edit.replacement_text
        return PromptProjectionIncrementalDocumentResult(
            projection_document=projection_document,
            first_dirty_source_position=edit.start,
            first_dirty_projection_position=first_dirty_projection_position,
            reason="plain_text_incremental",
            edited_token_id=editable_token_id,
            projection_edit_start=projection_edit_start,
            projection_edit_end=projection_edit_end,
            projection_replacement_text=projection_replacement_text,
        )

    def _reject(
        self,
        reason: str,
    ) -> PromptProjectionIncrementalDocumentResult | None:
        """Record one rejected incremental edit attempt."""

        self.last_rejection_reason = reason
        return None


def _is_supported_plain_text_incremental_edit(
    edit: PromptProjectionIncrementalEdit,
) -> bool:
    """Return whether a plain edit is safe to attempt incrementally."""

    replaced_length = edit.end - edit.start
    replacement_length = len(edit.replacement_text)
    if "\r" in edit.replacement_text or "\t" in edit.replacement_text:
        return False
    replaced_text = edit.previous_source_text[edit.start : edit.end]
    if "\r" in replaced_text:
        return False
    if edit.replacement_text == "\n":
        return replaced_length == 0
    if replaced_text == "\n":
        return replacement_length == 0 and replaced_length == 1
    if "\n" in replaced_text:
        return False
    return (
        (
            replaced_length == 0
            and replacement_length == 1
            and "\n" not in edit.replacement_text
        )
        or (replaced_length >= 1 and replacement_length == 0)
        or (
            replaced_length == 1
            and replacement_length == 1
            and "\n" not in edit.replacement_text
        )
    )


def _edit_intersects_token(
    edit: PromptProjectionIncrementalEdit,
    tokens: tuple[PromptProjectionToken, ...],
    *,
    editable_token_id: str | None = None,
) -> bool:
    """Return whether the source edit touches projected token structure."""

    if edit.start == edit.end:
        return any(
            token.token_id != editable_token_id
            and token.source_start < edit.start < token.source_end
            for token in tokens
        )
    return any(
        token.token_id != editable_token_id
        and edit.start < token.source_end
        and token.source_start < edit.end
        for token in tokens
    )


def _edit_intersects_syntax_span(
    edit: PromptProjectionIncrementalEdit,
    spans: tuple[PromptSyntaxSpanView, ...],
) -> bool:
    """Return whether the source edit touches syntax-owned structure."""

    if edit.start == edit.end:
        return any(span.start < edit.start < span.end for span in spans)
    return any(edit.start < span.end and span.start < edit.end for span in spans)


def _source_backed_plain_text_run_for_edit(
    edit: PromptProjectionIncrementalEdit,
    runs: tuple[PromptProjectionRun, ...],
) -> PromptProjectionRun | None:
    """Return the plain source-backed run containing the supplied edit."""

    for run in runs:
        if (
            run.kind is not PromptProjectionRunKind.TEXT
            or not run.source_backed
            or run.token_id is not None
        ):
            continue
        if edit.start == edit.end:
            if run.source_start <= edit.start <= run.source_end:
                return run
            continue
        if run.source_start <= edit.start and edit.end <= run.source_end:
            return run
    return None


def _projection_position_for_source_boundary(
    run: PromptProjectionRun,
    source_position: int,
) -> int | None:
    """Return the projection boundary corresponding to a run source boundary."""

    if _run_has_contiguous_source_positions(run):
        return run.projection_start + (source_position - run.source_start)
    try:
        boundary_index = run.source_positions.index(source_position)
    except ValueError:
        return None
    return run.projection_start + boundary_index


def _run_has_contiguous_source_positions(run: PromptProjectionRun) -> bool:
    """Return whether one text run can derive source positions arithmetically."""

    return (
        run.kind is PromptProjectionRunKind.TEXT
        and len(run.source_positions) == run.source_end - run.source_start + 1
        and run.source_positions[0] == run.source_start
        and run.source_positions[-1] == run.source_end
    )


def _apply_plain_text_document_edit(
    edit: PromptProjectionIncrementalEdit,
    *,
    previous_document: PromptProjectionDocument,
    edited_run: PromptProjectionRun,
    first_dirty_projection_position: int,
    editable_token_id: str | None = None,
) -> PromptProjectionDocument:
    """Return a projection document with one plain text edit applied."""

    source_delta = len(edit.replacement_text) - (edit.end - edit.start)
    projection_delta = source_delta
    projection_edit_end = first_dirty_projection_position + (edit.end - edit.start)
    next_projection_text = (
        previous_document.projection_text[:first_dirty_projection_position]
        + edit.replacement_text
        + previous_document.projection_text[projection_edit_end:]
    )
    next_runs = tuple(
        _remap_run_for_plain_text_edit(
            run,
            edit=edit,
            edited_run=edited_run,
            first_dirty_projection_position=first_dirty_projection_position,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
        for run in previous_document.runs
    )
    next_tokens = tuple(
        _remap_token_after_source_edit(
            token,
            edit=edit,
            delta=source_delta,
            editable_content=token.token_id == editable_token_id,
        )
        for token in previous_document.tokens
    )
    next_mapping = PromptProjectionMapping(
        runs=next_runs,
        source_length=len(edit.next_source_text),
        projection_length=len(next_projection_text),
    )
    next_caret_map = build_prompt_projection_caret_map(
        runs=next_runs,
        tokens=next_tokens,
        source_length=len(edit.next_source_text),
        projection_length=len(next_projection_text),
    )
    return replace(
        previous_document,
        source_text=edit.next_source_text,
        projection_text=next_projection_text,
        runs=next_runs,
        tokens=next_tokens,
        mapping=next_mapping,
        caret_map=next_caret_map,
    )


def _remap_run_for_plain_text_edit(
    run: PromptProjectionRun,
    *,
    edit: PromptProjectionIncrementalEdit,
    edited_run: PromptProjectionRun,
    first_dirty_projection_position: int,
    source_delta: int,
    projection_delta: int,
) -> PromptProjectionRun:
    """Return one run remapped across a supported plain text edit."""

    if run.run_id == edited_run.run_id:
        return _edit_source_backed_text_run(
            run,
            edit=edit,
            first_dirty_projection_position=first_dirty_projection_position,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
    projection_start = run.projection_start
    projection_end = run.projection_end
    if run.projection_start >= first_dirty_projection_position:
        projection_start += projection_delta
        projection_end += projection_delta
    next_source_start = _remap_position_after_source_edit(
        run.source_start,
        edit_start=edit.start,
        edit_end=edit.end,
        delta=source_delta,
        move_insert_boundary=True,
    )
    next_source_end = _remap_position_after_source_edit(
        run.source_end,
        edit_start=edit.start,
        edit_end=edit.end,
        delta=source_delta,
        move_insert_boundary=True,
    )
    source_positions = (
        range(next_source_start, next_source_end + 1)
        if _run_has_contiguous_source_positions(run)
        else tuple(
            _remap_position_after_source_edit(
                position,
                edit_start=edit.start,
                edit_end=edit.end,
                delta=source_delta,
                move_insert_boundary=True,
            )
            for position in run.source_positions
        )
    )
    return replace(
        run,
        source_start=next_source_start,
        source_end=next_source_end,
        source_positions=source_positions,
        projection_start=projection_start,
        projection_end=projection_end,
    )


def _edit_source_backed_text_run(
    run: PromptProjectionRun,
    *,
    edit: PromptProjectionIncrementalEdit,
    first_dirty_projection_position: int,
    source_delta: int,
    projection_delta: int,
) -> PromptProjectionRun:
    """Return the edited source-backed text run."""

    local_index = first_dirty_projection_position - run.projection_start
    next_source_end = run.source_end + source_delta
    replaced_length = edit.end - edit.start
    next_display_text = (
        run.display_text[:local_index]
        + edit.replacement_text
        + run.display_text[local_index + replaced_length :]
    )
    next_source_positions = (
        tuple(run.source_positions[: local_index + 1])
        + tuple(
            edit.start + index for index in range(1, len(edit.replacement_text) + 1)
        )
        + tuple(
            position + source_delta
            for position in run.source_positions[local_index + replaced_length + 1 :]
        )
    )
    return replace(
        run,
        source_end=next_source_end,
        display_text=next_display_text,
        source_positions=(
            range(run.source_start, next_source_end + 1)
            if _run_has_contiguous_source_positions(run)
            else next_source_positions
        ),
        projection_end=run.projection_end + projection_delta,
    )


def _remap_token_after_source_edit(
    token: PromptProjectionToken,
    *,
    edit: PromptProjectionIncrementalEdit,
    delta: int,
    editable_content: bool = False,
) -> PromptProjectionToken:
    """Return one token shifted across a non-intersecting source edit."""

    return replace(
        token,
        source_start=_remap_position_after_source_edit(
            token.source_start,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=delta,
            move_insert_boundary=not editable_content,
        ),
        source_end=_remap_position_after_source_edit(
            token.source_end,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=delta,
            move_insert_boundary=True,
        ),
        content_start=_remap_optional_position_after_source_edit(
            token.content_start,
            edit=edit,
            delta=delta,
            move_insert_boundary=not editable_content,
        ),
        content_end=_remap_optional_position_after_source_edit(
            token.content_end,
            edit=edit,
            delta=delta,
            move_insert_boundary=True,
        ),
    )


def _remap_optional_position_after_source_edit(
    position: int | None,
    *,
    edit: PromptProjectionIncrementalEdit,
    delta: int,
    move_insert_boundary: bool,
) -> int | None:
    """Return an optional position shifted across one source edit."""

    if position is None:
        return None
    return _remap_position_after_source_edit(
        position,
        edit_start=edit.start,
        edit_end=edit.end,
        delta=delta,
        move_insert_boundary=move_insert_boundary,
    )


def _remap_position_after_source_edit(
    position: int,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
    move_insert_boundary: bool,
) -> int:
    """Return a source position shifted across a non-overlapping edit."""

    if edit_start == edit_end:
        if position > edit_start or (move_insert_boundary and position == edit_start):
            return position + delta
        return position
    if position >= edit_end:
        return position + delta
    if position > edit_start:
        return edit_start
    return position


def single_source_text_edit(
    previous_text: str,
    next_text: str,
) -> PromptProjectionSourceTextEdit | None:
    """Return the single contiguous edit between two projection source strings."""

    if previous_text == next_text:
        return None
    prefix_length = 0
    common_length = min(len(previous_text), len(next_text))
    while (
        prefix_length < common_length
        and previous_text[prefix_length] == next_text[prefix_length]
    ):
        prefix_length += 1

    previous_suffix = len(previous_text)
    next_suffix = len(next_text)
    while (
        previous_suffix > prefix_length
        and next_suffix > prefix_length
        and previous_text[previous_suffix - 1] == next_text[next_suffix - 1]
    ):
        previous_suffix -= 1
        next_suffix -= 1
    return PromptProjectionSourceTextEdit(
        start=prefix_length,
        end=previous_suffix,
        replacement_text=next_text[prefix_length:next_suffix],
    )


def render_plan_ranges_match_after_source_edit(
    previous_render_plan: PromptSyntaxRenderPlan,
    next_render_plan: PromptSyntaxRenderPlan,
    *,
    edit: PromptProjectionSourceTextEdit,
) -> bool:
    """Return whether render-plan projection ranges remain equivalent after an edit."""

    delta = len(edit.replacement_text) - (edit.end - edit.start)
    remapped_ranges: list[tuple[int, int]] = []
    for source_range in projection_affecting_render_plan_ranges(previous_render_plan):
        remapped_range = _remap_range_after_source_edit(
            source_range,
            edit_start=edit.start,
            edit_end=edit.end,
            delta=delta,
        )
        if remapped_range is not None:
            remapped_ranges.append(remapped_range)
            continue
        return False
    return tuple(remapped_ranges) == projection_affecting_render_plan_ranges(
        next_render_plan
    )


def projection_affecting_render_plan_ranges(
    render_plan: PromptSyntaxRenderPlan,
) -> tuple[tuple[int, int], ...]:
    """Return source ranges whose renderers can replace text with projection tokens."""

    ranges: set[tuple[int, int]] = {
        (span.start, span.end)
        for span in render_plan.syntax_spans
        if span.end > span.start
    }
    for renderer_view in render_plan.renderer_views:
        ranges.update(_renderer_projection_ranges(renderer_view))
    return tuple(sorted(ranges))


def _extend_contiguous_source_positions(
    source_positions: Sequence[int],
    *,
    source_start: int,
    previous_source_end: int,
    next_source_end: int,
) -> Sequence[int]:
    """Return source positions after extending one trailing contiguous text run."""

    if (
        len(source_positions) == previous_source_end - source_start + 1
        and source_positions[0] == source_start
        and source_positions[-1] == previous_source_end
    ):
        return range(source_start, next_source_end + 1)
    return tuple(source_positions) + tuple(
        range(previous_source_end + 1, next_source_end + 1)
    )


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
    "PromptProjectionIncrementalDocumentResult",
    "PromptProjectionIncrementalEdit",
    "PromptProjectionIncrementalEditor",
    "PromptProjectionPlainTextApplyResult",
    "PromptProjectionPlainTextApplyStatus",
    "PromptProjectionSourceTextEdit",
    "projection_affecting_render_plan_ranges",
    "render_plan_ranges_match_after_source_edit",
    "single_source_text_edit",
]
