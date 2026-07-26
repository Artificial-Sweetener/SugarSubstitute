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

"""Resolve bounded eligibility and target facts for plain projection edits."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .incremental_edit_contracts import PromptProjectionIncrementalEdit


def plain_text_edit_is_supported(edit: PromptProjectionIncrementalEdit) -> bool:
    """Return whether a plain edit has a bounded supported shape."""

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


def edit_intersects_token(
    edit: PromptProjectionIncrementalEdit,
    tokens: Sequence[PromptProjectionToken],
    *,
    editable_token_id: str | None = None,
) -> bool:
    """Return whether the edit touches token structure outside its target."""

    for token in tokens:
        if token.source_start >= edit.end and edit.start != edit.end:
            return False
        if token.source_start >= edit.start and edit.start == edit.end:
            return False
        if token.token_id == editable_token_id:
            continue
        if edit.start == edit.end:
            if token.source_start < edit.start < token.source_end:
                return True
            continue
        if edit.start < token.source_end and token.source_start < edit.end:
            return True
    return False


def edit_intersects_syntax_span(
    edit: PromptProjectionIncrementalEdit,
    spans: Sequence[PromptSyntaxSpanView],
) -> bool:
    """Return whether the edit touches syntax-owned structure."""

    for span in spans:
        if span.start >= edit.end and edit.start != edit.end:
            return False
        if span.start >= edit.start and edit.start == edit.end:
            return False
        if edit.start == edit.end:
            if span.start < edit.start < span.end:
                return True
            continue
        if edit.start < span.end and span.start < edit.end:
            return True
    return False


def source_backed_plain_text_run_for_edit(
    edit: PromptProjectionIncrementalEdit,
    runs: Sequence[PromptProjectionRun],
) -> PromptProjectionRun | None:
    """Return the plain source-backed run containing the edit."""

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


def projection_position_for_source_boundary(
    run: PromptProjectionRun,
    source_position: int,
) -> int | None:
    """Return the projection boundary corresponding to a run source boundary."""

    if run_has_contiguous_source_positions(run):
        return run.projection_start + (source_position - run.source_start)
    try:
        boundary_index = run.source_positions.index(source_position)
    except ValueError:
        return None
    return run.projection_start + boundary_index


def run_has_contiguous_source_positions(run: PromptProjectionRun) -> bool:
    """Return whether a text run can derive source positions arithmetically."""

    return (
        run.kind is PromptProjectionRunKind.TEXT
        and len(run.source_positions) == run.source_end - run.source_start + 1
        and run.source_positions[0] == run.source_start
        and run.source_positions[-1] == run.source_end
    )


__all__ = [
    "edit_intersects_syntax_span",
    "edit_intersects_token",
    "plain_text_edit_is_supported",
    "projection_position_for_source_boundary",
    "run_has_contiguous_source_positions",
    "source_backed_plain_text_run_for_edit",
]
