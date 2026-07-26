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

"""Remap immutable projection coordinates across one accepted plain edit."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from substitute.presentation.text_coordinates import TextCoordinateMap

from .caret_map_builder import build_prompt_projection_caret_map
from .incremental_edit_contracts import PromptProjectionIncrementalEdit
from .plain_edit_caret_sequence import (
    MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH,
    PromptProjectionPlainEditCaretStopSequence,
)
from .plain_edit_coordinates import PromptProjectionPlainEditCoordinates
from .plain_edit_run_sequence import PromptProjectionPlainEditRunSequence
from .plain_text_edit_policy import run_has_contiguous_source_positions


def apply_plain_text_document_edit(
    edit: PromptProjectionIncrementalEdit,
    *,
    previous_document: PromptProjectionDocument,
    region_structure: PromptRegionStructureView,
    edited_run: PromptProjectionRun,
    first_dirty_projection_position: int,
    editable_token_id: str | None = None,
) -> PromptProjectionDocument:
    """Return a projection document with one plain-text edit applied."""

    source_delta = len(edit.replacement_text) - (edit.end - edit.start)
    projection_delta = source_delta
    projection_edit_end = first_dirty_projection_position + (edit.end - edit.start)
    next_projection_text = (
        previous_document.projection_text[:first_dirty_projection_position]
        + edit.replacement_text
        + previous_document.projection_text[projection_edit_end:]
    )
    edited_run_index = next(
        index
        for index, run in enumerate(previous_document.runs)
        if run.run_id == edited_run.run_id
    )
    next_edited_run = _edit_source_backed_text_run(
        edited_run,
        edit=edit,
        first_dirty_projection_position=first_dirty_projection_position,
        source_delta=source_delta,
        projection_delta=projection_delta,
    )
    if editable_token_id is None:
        coordinates = PromptProjectionPlainEditCoordinates(
            source_start=edit.start,
            source_end=edit.end,
            source_delta=source_delta,
            projection_start=first_dirty_projection_position,
            projection_delta=projection_delta,
        )
        next_runs: Sequence[PromptProjectionRun] = PromptProjectionPlainEditRunSequence(
            previous_document.runs,
            edited_run_index=edited_run_index,
            edited_run=next_edited_run,
            coordinates=coordinates,
        )
        next_tokens: Sequence[PromptProjectionToken] = tuple(
            _remap_token_after_source_edit(
                token,
                edit=edit,
                delta=source_delta,
                editable_content=False,
            )
            for token in previous_document.tokens
        )
        if _plain_edit_supports_lazy_caret_transform(edit) and callable(
            getattr(
                previous_document.caret_map.stops,
                "visual_index_for_state",
                None,
            )
        ):
            edited_stops = PromptProjectionPlainEditCaretStopSequence(
                previous_document.caret_map,
                edited_run=next_edited_run,
                coordinates=coordinates,
            )
            if edited_stops.transform_depth <= MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH:
                next_caret_map = PromptProjectionCaretMap(
                    stops=edited_stops,
                    tokens=next_tokens,
                    source_length=len(edit.next_source_text),
                    projection_length=len(next_projection_text),
                )
            else:
                next_caret_map = build_prompt_projection_caret_map(
                    runs=next_runs,
                    tokens=next_tokens,
                    source_length=len(edit.next_source_text),
                    projection_length=len(next_projection_text),
                )
        else:
            next_caret_map = build_prompt_projection_caret_map(
                runs=tuple(next_runs),
                tokens=tuple(next_tokens),
                source_length=len(edit.next_source_text),
                projection_length=len(next_projection_text),
            )
    else:
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
        next_caret_map = build_prompt_projection_caret_map(
            runs=tuple(next_runs),
            tokens=tuple(next_tokens),
            source_length=len(edit.next_source_text),
            projection_length=len(next_projection_text),
        )
    next_mapping = PromptProjectionMapping(
        runs=next_runs,
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
        region_structure=region_structure,
    )


def _plain_edit_supports_lazy_caret_transform(
    edit: PromptProjectionIncrementalEdit,
) -> bool:
    """Use lazy stop arithmetic only for independent grapheme boundaries."""

    replaced_text = edit.previous_source_text[edit.start : edit.end]
    return _has_independent_grapheme_boundaries(
        replaced_text,
    ) and _has_independent_grapheme_boundaries(edit.replacement_text)


def _has_independent_grapheme_boundaries(text: str) -> bool:
    """Recognize bounded payloads with one caret boundary per code point."""

    maximum_lazy_edit_codepoints = 64
    if len(text) > maximum_lazy_edit_codepoints:
        return False
    return TextCoordinateMap(text).grapheme_boundaries() == tuple(range(len(text) + 1))


def _remap_run_for_plain_text_edit(
    run: PromptProjectionRun,
    *,
    edit: PromptProjectionIncrementalEdit,
    edited_run: PromptProjectionRun,
    first_dirty_projection_position: int,
    source_delta: int,
    projection_delta: int,
) -> PromptProjectionRun:
    """Return one run remapped across a supported plain-text edit."""

    if run.run_id == edited_run.run_id:
        return _edit_source_backed_text_run(
            run,
            edit=edit,
            first_dirty_projection_position=first_dirty_projection_position,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
    if (
        run.source_end < edit.start
        and run.projection_end <= first_dirty_projection_position
    ):
        return run
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
        if run_has_contiguous_source_positions(run)
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
            if run_has_contiguous_source_positions(run)
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

    if token.source_end < edit.start:
        return token
    if (
        not editable_content
        and edit.start == edit.end
        and token.source_start < edit.start
        and token.source_end == edit.start
    ):
        return token
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


__all__ = ["apply_plain_text_document_edit"]
