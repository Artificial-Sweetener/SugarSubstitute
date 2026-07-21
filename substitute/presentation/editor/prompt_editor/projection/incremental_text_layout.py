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

"""Build one locally edited projection text fragment without document relayout."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QTextLayout, QTextOption

from .model import PromptProjectionRun
from .snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionTextFragment,
)
from .text_style import projection_text_run_font


def editable_text_fragment(
    fragments: Sequence[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
    ],
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    editable_token_id: str | None = None,
    projection_edit_start: int | None = None,
    projection_edit_end: int | None = None,
) -> PromptProjectionTextFragment | None:
    """Return the permitted source-backed fragment containing one edit."""

    for fragment in fragments:
        if not isinstance(fragment, PromptProjectionTextFragment):
            continue
        if fragment.token_id is not None and fragment.token_id != editable_token_id:
            continue
        if (
            fragment.token_id == editable_token_id
            and projection_edit_start is not None
            and projection_edit_end is not None
            and fragment.projection_start <= projection_edit_start
            and projection_edit_end <= fragment.projection_end
        ):
            return fragment
        try:
            start_index = fragment.source_positions.index(edit_start)
        except ValueError:
            continue
        if replacement_text and edit_start == edit_end:
            return fragment
        try:
            end_index = fragment.source_positions.index(edit_end)
        except ValueError:
            continue
        if end_index > start_index:
            return fragment
    return None


def build_edited_text_fragment(
    fragment: PromptProjectionTextFragment,
    *,
    next_run: PromptProjectionRun,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    base_font: QFont,
    projection_edit_start: int | None = None,
    projection_edit_end: int | None = None,
    projection_replacement_text: str | None = None,
) -> PromptProjectionTextFragment | None:
    """Return a locally remeasured fragment for source and visible edit deltas."""

    source_delta = len(replacement_text) - (edit_end - edit_start)
    if (
        projection_edit_start is not None
        and projection_edit_end is not None
        and projection_replacement_text is not None
    ):
        local_start = projection_edit_start - fragment.projection_start
        local_end = projection_edit_end - fragment.projection_start
        visible_replacement = projection_replacement_text
        projection_delta = len(visible_replacement) - (local_end - local_start)
    else:
        try:
            local_start = fragment.source_positions.index(edit_start)
            local_end = fragment.source_positions.index(edit_end)
        except ValueError:
            return None
        visible_replacement = replacement_text
        projection_delta = source_delta
    if local_end < local_start:
        return None
    next_text = (
        fragment.text[:local_start] + visible_replacement + fragment.text[local_end:]
    )
    if not next_text:
        return None

    next_projection_end = fragment.projection_end + projection_delta
    if (
        next_projection_end <= fragment.projection_start
        or next_run.projection_start > fragment.projection_start
        or next_run.projection_end < next_projection_end
    ):
        return None
    expected_text = next_run.display_text[
        fragment.projection_start - next_run.projection_start : next_projection_end
        - next_run.projection_start
    ]
    if expected_text != next_text:
        return None
    next_run_local_start = fragment.projection_start - next_run.projection_start
    next_run_local_end = next_projection_end - next_run.projection_start
    next_source_positions = next_run.source_positions[
        next_run_local_start : next_run_local_end + 1
    ]
    if len(next_source_positions) != len(next_text) + 1:
        return None
    boundary_offsets = text_boundary_offsets(
        next_text,
        projection_text_run_font(next_run, base_font),
    )
    if len(boundary_offsets) != len(next_text) + 1:
        return None
    next_rect = QRectF(fragment.rect)
    next_rect.setWidth(max(1.0, boundary_offsets[-1]))
    return PromptProjectionTextFragment(
        run_id=fragment.run_id,
        token_id=fragment.token_id,
        projection_start=fragment.projection_start,
        projection_end=next_projection_end,
        text=next_text,
        source_positions=next_source_positions,
        rect=next_rect,
        baseline=fragment.baseline,
        boundary_offsets=boundary_offsets,
        active=next_run.active,
    )


def text_boundary_offsets(text: str, font: QFont) -> tuple[float, ...]:
    """Return horizontal offsets for every character boundary in one fragment."""

    if not text:
        return (0.0,)
    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.NoWrap)
    text_layout = QTextLayout(text, font)
    text_layout.setTextOption(text_option)
    text_layout.beginLayout()
    text_line = text_layout.createLine()
    if text_line.isValid():
        text_line.setLineWidth(
            max(1.0, QFontMetricsF(font).horizontalAdvance(text) + 1.0)
        )
    text_layout.endLayout()
    if not text_line.isValid():
        return (0.0,)
    return tuple(
        float(cast(tuple[float, int], text_line.cursorToX(index))[0])
        for index in range(len(text) + 1)
    )


__all__ = [
    "build_edited_text_fragment",
    "editable_text_fragment",
    "text_boundary_offsets",
]
