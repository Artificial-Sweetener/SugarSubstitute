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

"""Tests for passive prompt editing-session state primitives."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptSelection,
    PromptSourceBuffer,
    PromptSourceSnapshot,
)


def test_source_snapshot_reports_revision_and_length() -> None:
    """Source snapshots should expose immutable source identity."""

    snapshot = PromptSourceSnapshot(source_text="alpha beta", source_revision=3)

    assert snapshot.source_text == "alpha beta"
    assert snapshot.source_revision == 3
    assert snapshot.source_length == len("alpha beta")


def test_source_snapshot_rejects_negative_revision() -> None:
    """Revision identities should never move below the initial baseline."""

    with pytest.raises(ValueError, match="Source revision"):
        PromptSourceSnapshot(source_text="", source_revision=-1)


def test_source_buffer_returns_snapshot_without_edit_behavior() -> None:
    """Source buffers should expose current state without applying edit policy."""

    buffer = PromptSourceBuffer(source_text="cat", source_revision=2)

    assert buffer.source_length == 3
    assert buffer.snapshot() == PromptSourceSnapshot(
        source_text="cat",
        source_revision=2,
    )


def test_cursor_state_clamps_to_source_length_and_collapses_anchor() -> None:
    """Cursor state should track source positions without projection metadata."""

    cursor = PromptCursorState(cursor_position=12, anchor_position=4)

    assert cursor.clamped(6) == PromptCursorState(
        cursor_position=6,
        anchor_position=4,
    )
    assert cursor.collapsed() == PromptCursorState(
        cursor_position=12,
        anchor_position=12,
    )


def test_cursor_state_derives_selection() -> None:
    """Cursor state should expose the equivalent source-backed selection."""

    cursor = PromptCursorState(cursor_position=2, anchor_position=5)

    assert cursor.selection() == PromptSelection(anchor_position=5, cursor_position=2)


def test_selection_preserves_anchor_direction_and_normalizes_bounds() -> None:
    """Selections should normalize ranges without losing cursor direction."""

    selection = PromptSelection(anchor_position=8, cursor_position=3)

    assert selection.start == 3
    assert selection.end == 8
    assert selection.is_empty is False
    assert selection.anchor_position == 8
    assert selection.cursor_position == 3


def test_selection_returns_selected_raw_source_text() -> None:
    """Selected text should come from the normalized raw source range."""

    selection = PromptSelection(anchor_position=10, cursor_position=4)

    assert selection.selected_text("0123456789abcdef") == "456789"


def test_selection_clamps_to_available_source_text() -> None:
    """Selections should clamp to the source text before slicing."""

    selection = PromptSelection(anchor_position=12, cursor_position=4)

    assert selection.clamped(7) == PromptSelection(
        anchor_position=7,
        cursor_position=4,
    )
    assert selection.selected_text("abcdefg") == "efg"
