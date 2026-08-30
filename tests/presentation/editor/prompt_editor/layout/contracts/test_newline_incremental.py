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
from substitute.presentation.editor.prompt_editor.layout.shifted_snapshot import (
    ShiftedLineSnapshot,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)

from .support import (
    _line_texts,
    _install_non_iterable_caret_rect_mapping,
    _assert_snapshot_caret_rects_resolve,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_trailing_newline_after_shifted_line_does_not_crash() -> None:
    """Trailing newline should handle line snapshots shifted by prior edits."""

    previous_text = "alpha beta gamma"
    first_next_text = "alpha Xbeta gamma"
    second_next_text = f"{first_next_text}\n"
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

    assert layout.try_apply_trailing_newline_insert(
        second_projection,
        prompt_document_view=second_document_view,
    )
    assert layout.frame.output.projection_document.source_text == second_next_text
    assert _line_texts(layout) == (first_next_text, "")


def test_projection_layout_trailing_newline_derives_caret_rects_from_lines() -> None:
    """Trailing newline should install line-owned caret rects without map cloning."""

    previous_text = "alpha beta gamma"
    next_text = f"{previous_text}\n"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    previous = _install_non_iterable_caret_rect_mapping(layout.frame.output)
    next_document_view, next_projection = _projection_for(next_text)

    outcome = PromptTrailingLayoutEngine().apply_trailing_newline_insert(
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
    ) == (previous_text, "")
    _assert_snapshot_caret_rects_resolve(
        outcome.output.snapshot,
        next_projection,
    )


def test_projection_layout_middle_newline_insert_uses_incremental_layout() -> None:
    """Middle newline insert should split a plain line without full relayout."""

    previous_text = "alpha beta"
    edit_start = len("alpha")
    next_text = f"{previous_text[:edit_start]}\n{previous_text[edit_start:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="\n",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert result.damage is not None
    assert result.damage.content_height_changed is True
    assert layout.frame.output.projection_document.source_text == next_text
    assert _line_texts(layout) == ("alpha", " beta")
    first_line = layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    second_line = layout.frame.output.snapshot.lines[1]  # noqa: SLF001
    assert first_line.line_break_start == edit_start
    assert first_line.line_break_end == edit_start + 1
    assert second_line.source_start == edit_start + 1


def test_projection_layout_consecutive_middle_newlines_preserve_fragment_height() -> (
    None
):
    """Consecutive line splits should translate fragments without collapsing them."""

    initial_text = "alpha beta"
    first_edit_start = len("alpha")
    first_text = "alpha\n beta"
    layout, _ = _layout_for(initial_text, text_width=1000.0)
    first_document_view, first_projection = _projection_for(first_text)

    first_result = layout.try_apply_hard_line_break_edit(
        first_projection,
        prompt_document_view=first_document_view,
        edit_start=first_edit_start,
        edit_end=first_edit_start,
        replacement_text="\n",
        first_dirty_projection_position=first_edit_start,
    )

    assert first_result.applied
    second_edit_start = first_edit_start + 1
    second_text = "alpha\n\n beta"
    second_document_view, second_projection = _projection_for(second_text)
    second_result = layout.try_apply_hard_line_break_edit(
        second_projection,
        prompt_document_view=second_document_view,
        edit_start=second_edit_start,
        edit_end=second_edit_start,
        replacement_text="\n",
        first_dirty_projection_position=second_edit_start,
    )

    assert second_result.applied
    assert _line_texts(layout) == ("alpha", "", " beta")
    assert all(
        fragment.rect.height() == line.height
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        for fragment in line.fragments
        if isinstance(fragment, PromptProjectionTextFragment)
    )


def test_projection_layout_middle_newline_insert_keeps_downstream_lines_lazy() -> None:
    """Middle newline insert should not materialize every downstream visual line."""

    previous_text = "alpha beta\ngamma delta\nomega"
    edit_start = len("alpha")
    next_text = f"{previous_text[:edit_start]}\n{previous_text[edit_start:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    previous_downstream_line = layout.frame.output.snapshot.lines[1]  # noqa: SLF001
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="\n",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    shifted_downstream_line = layout.frame.output.snapshot.lines[2]  # noqa: SLF001
    assert isinstance(shifted_downstream_line, ShiftedLineSnapshot)
    assert shifted_downstream_line.top == previous_downstream_line.top + (
        layout.frame.output.snapshot.lines[1].height  # noqa: SLF001
    )
    assert (
        shifted_downstream_line.source_start
        == previous_downstream_line.source_start + 1
    )
    assert shifted_downstream_line.fragments[0].source_positions[0] == (
        previous_downstream_line.fragments[0].source_positions[0] + 1
    )


def test_projection_layout_middle_newline_delete_uses_incremental_layout() -> None:
    """Middle newline delete should join adjacent plain lines without full relayout."""

    previous_text = "alpha\nbeta"
    edit_start = len("alpha")
    next_text = "alphabeta"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_hard_line_break_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert result.damage is not None
    assert result.damage.content_height_changed is True
    assert layout.frame.output.projection_document.source_text == next_text
    assert _line_texts(layout) == ("alphabeta",)
    joined_line = layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    assert joined_line.line_break_start is None
    assert joined_line.line_break_end is None


def test_projection_layout_newline_insert_delete_preserves_downstream_inline_rows() -> (
    None
):
    """Hard-line toggles should preserve downstream decorated row ownership."""

    previous_text = "scene\nbody\n(sharp eyes:1.25)"
    edit_start = len("scene")
    inserted_text = f"{previous_text[:edit_start]}\n{previous_text[edit_start:]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    inserted_document_view, inserted_projection = _projection_for(inserted_text)

    insert_result = layout.try_apply_hard_line_break_edit(
        inserted_projection,
        prompt_document_view=inserted_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text="\n",
        first_dirty_projection_position=edit_start,
    )

    assert insert_result.applied
    inserted_inline_line = layout.frame.output.snapshot.lines[-1]  # noqa: SLF001
    assert inserted_inline_line.fragments
    assert layout.frame.output.snapshot.inline_object_fragments  # noqa: SLF001

    restored_document_view, restored_projection = _projection_for(previous_text)
    delete_result = layout.try_apply_hard_line_break_edit(
        restored_projection,
        prompt_document_view=restored_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert delete_result.applied
    restored_inline_line = layout.frame.output.snapshot.lines[-1]  # noqa: SLF001
    assert restored_inline_line.fragments
    assert layout.frame.output.snapshot.inline_object_fragments  # noqa: SLF001
    fresh_layout, _ = _layout_for(previous_text, text_width=1000.0)
    assert _line_texts(layout)[-1] == _line_texts(fresh_layout)[-1]
    assert tuple(
        isinstance(fragment, PromptProjectionTextFragment)
        for fragment in restored_inline_line.fragments
    ) == tuple(
        isinstance(fragment, PromptProjectionTextFragment)
        for fragment in fresh_layout.frame.output.snapshot.lines[-1].fragments  # noqa: SLF001
    )
