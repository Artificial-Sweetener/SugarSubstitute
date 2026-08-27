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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations


import pytest

from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.layout.contracts import (
    PromptLayoutRequest,
    PromptLayoutStatus,
)
from substitute.presentation.editor.prompt_editor.layout.trailing_engine import (
    PromptTrailingLayoutEngine,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)

from .support import (
    _line_texts,
    _layout_geometry_signature,
    _install_non_iterable_caret_rect_mapping,
    _assert_all_projection_caret_rects_resolve,
    _assert_snapshot_caret_rects_resolve,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


@pytest.mark.parametrize(
    ("previous_text", "edit_start"),
    (
        ("alpha, (decorated:1.20), omega", len("alpha")),
        (
            "(decorated:1.20), alpha omega",
            len("(decorated:1.20), alpha"),
        ),
    ),
)
def test_projection_layout_incremental_plain_edit_preserves_inline_object_geometry(
    previous_text: str,
    edit_start: int,
) -> None:
    """Local text edits should remap an adjacent inline object exactly."""

    next_text = previous_text[:edit_start] + "x" + previous_text[edit_start:]
    incremental_layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=1000.0)

    result = incremental_layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="x",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_applies_same_line_plain_selection_delete_incrementally() -> (
    None
):
    """Plain same-line selection delete should update geometry without full relayout."""

    previous_text = "alpha removable beta gamma"
    edit_start = previous_text.index("removable ")
    edit_end = edit_start + len("removable ")
    next_text = f"{previous_text[:edit_start]}{previous_text[edit_end:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert layout.frame.output.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_trailing_insert_after_shifted_fragment_does_not_crash() -> (
    None
):
    """Trailing insert should handle fragments shifted by prior same-line edits."""

    previous_text = "alpha beta gamma"
    first_next_text = "alpha Xbeta gamma"
    second_next_text = f"{first_next_text}!"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    first_document_view, first_projection = _projection_for(first_next_text)

    first_result = layout.try_apply_same_line_plain_text_edit(
        first_projection,
        prompt_document_view=first_document_view,
        edit_start=len("alpha "),
        edit_end=len("alpha "),
        replacement_text="X",
        first_dirty_projection_position=len("alpha "),
    )

    assert first_result.applied
    second_document_view, second_projection = _projection_for(second_next_text)

    assert layout.try_apply_trailing_plain_insert(
        second_projection,
        prompt_document_view=second_document_view,
    )
    assert layout.frame.output.projection_document.source_text == second_next_text
    assert _line_texts(layout) == (second_next_text,)


def test_projection_layout_trailing_insert_derives_caret_rects_from_lines() -> None:
    """Trailing insert should not clone the prior caret-rect map on the hot path."""

    previous_text = "alpha beta gamma"
    next_text = f"{previous_text}!"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    previous = _install_non_iterable_caret_rect_mapping(layout.frame.output)
    next_document_view, next_projection = _projection_for(next_text)

    outcome = PromptTrailingLayoutEngine().apply_trailing_plain_insert(
        PromptLayoutRequest(
            previous=previous,
            projection_document=next_projection,
            prompt_document_view=next_document_view,
            configuration=previous.configuration,
        )
    )

    assert outcome.status is PromptLayoutStatus.APPLIED
    assert outcome.output is not None
    assert tuple(
        "".join(
            fragment.text
            for fragment in line.fragments
            if isinstance(fragment, PromptProjectionTextFragment)
        )
        for line in outcome.output.snapshot.lines
    ) == (next_text,)
    _assert_snapshot_caret_rects_resolve(
        outcome.output.snapshot,
        next_projection,
    )


def test_projection_layout_rejects_trailing_comma_insert_that_creates_keep_group() -> (
    None
):
    """Trailing comma insertion should reflow when it creates kept-tag semantics."""

    previous_text = "1girl"
    next_text = f"{previous_text},"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    assert (
        layout.try_apply_trailing_plain_insert(
            next_projection,
            prompt_document_view=next_document_view,
        )
        is False
    )
    assert layout.frame.output.projection_document.source_text == previous_text
