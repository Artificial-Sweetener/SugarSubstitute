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

from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)

from .support import (
    _line_texts,
    _layout_geometry_signature,
    _assert_all_projection_caret_rects_resolve,
    _plain_text_wrap_width,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_applies_local_comma_insert_that_creates_keep_groups() -> (
    None
):
    """Comma insertion may stay incremental when the new keep group remains local."""

    previous_text = "test test test test, omega"
    edit_start = len("test")
    next_text = previous_text[:edit_start] + "," + previous_text[edit_start:]
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=",",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert layout.frame.output.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_rejects_comma_insert_when_new_keep_group_needs_wrap() -> (
    None
):
    """Comma insertion should reflow when the new kept tag no longer fits locally."""

    previous_text = "test test test test, omega"
    edit_start = len("test")
    next_text = previous_text[:edit_start] + "," + previous_text[edit_start:]
    layout, _ = _layout_for(
        previous_text,
        text_width=_plain_text_wrap_width("test test test, "),
    )
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=",",
        first_dirty_projection_position=edit_start,
    )

    assert not result.applied
    assert result.rejection_reason == "tag_keep_group"


def test_projection_layout_rejects_incremental_comma_delete_that_removes_keep_groups() -> (
    None
):
    """Comma deletion should reflow when it merges kept tags into normal wrapping."""

    previous_text = "test, test test test, omega"
    edit_start = previous_text.index(",")
    next_text = previous_text[:edit_start] + previous_text[edit_start + 1 :]
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="",
        first_dirty_projection_position=edit_start,
    )

    assert not result.applied
    assert result.rejection_reason in {
        "tag_keep_group",
        "fragment_edit_not_supported",
    }


def test_projection_layout_applies_same_length_plain_replacement_incrementally() -> (
    None
):
    """Plain same-line replacement should publish real layout without full relayout."""

    previous_text = "alpha beta gamma"
    edit_start = previous_text.index("b")
    next_text = f"{previous_text[:edit_start]}z{previous_text[edit_start + 1 :]}"
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)

    result = layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 1,
        replacement_text="z",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert layout.frame.output.projection_document.source_text == next_text
    assert _line_texts(layout) == (next_text,)
    _assert_all_projection_caret_rects_resolve(layout, next_projection)


def test_projection_layout_incremental_plain_edit_matches_full_rebuild_geometry() -> (
    None
):
    """Incremental same-line text edits should match full rebuild row geometry."""

    previous_text = "alpha beta gamma delta"
    edit_start = previous_text.index("beta")
    next_text = f"{previous_text[:edit_start]}bravo{previous_text[edit_start + 4 :]}"
    incremental_layout, _ = _layout_for(previous_text, text_width=96.0)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=96.0)

    result = incremental_layout.try_apply_same_line_plain_text_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start + 4,
        replacement_text="bravo",
        first_dirty_projection_position=edit_start,
    )

    assert result.applied
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )
