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

"""Verify prompt reorder cursor-selection adapter contracts."""

from __future__ import annotations


from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCloseTransition,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_cursor_selection import (
    PromptReorderCursor,
    PromptReorderCursorSelectionAdapter,
)


class _CursorSelectionDouble:
    """Provide the empty-selection query required by the cursor protocol."""

    def isEmpty(self) -> bool:  # noqa: N802
        """Return that this deterministic cursor has no selection."""

        return True


class _CursorDouble:
    """Record the Qt cursor boundary used by selection-restoration tests."""

    def __init__(self) -> None:
        """Initialize a cursor with no recorded position changes."""

        self.moves: list[tuple[int, object | None]] = []

    def position(self) -> int:
        """Return the deterministic current position."""

        return 0

    def selection(self) -> _CursorSelectionDouble:
        """Return the deterministic empty selection."""

        return _CursorSelectionDouble()

    def selectionStart(self) -> int:  # noqa: N802
        """Return the deterministic selection start."""

        return 0

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the deterministic selection end."""

        return 0

    def setPosition(self, position: int, mode: object | None = None) -> None:  # noqa: N802
        """Record one cursor position update."""

        self.moves.append((position, mode))


class _CursorSurfaceDouble:
    """Expose a deterministic cursor surface for adapter owner tests."""

    def __init__(self) -> None:
        """Initialize one reusable cursor and publication counter."""

        self.cursor = _CursorDouble()
        self.published_cursors: list[object] = []

    def textCursor(self) -> PromptReorderCursor:  # noqa: N802
        """Return the current deterministic cursor."""

        return self.cursor

    def setTextCursor(self, cursor: PromptReorderCursor) -> None:  # noqa: N802
        """Record one cursor publication."""

        self.published_cursors.append(cursor)


def test_reorder_cursor_selection_adapter_restores_one_half_open_range() -> None:
    """The Qt adapter must publish both anchors exactly once for a close effect."""

    surface = _CursorSurfaceDouble()

    PromptReorderCursorSelectionAdapter().restore(
        surface,
        PromptReorderCloseTransition(selection_start=3, selection_end=8),
    )

    assert [position for position, _mode in surface.cursor.moves] == [3, 8]
    assert surface.published_cursors == [surface.cursor]


def test_reorder_cursor_selection_adapter_skips_absent_restore_effect() -> None:
    """A commit-relative selection must not cause redundant Qt cursor work."""

    surface = _CursorSurfaceDouble()

    PromptReorderCursorSelectionAdapter().restore(
        surface,
        PromptReorderCloseTransition(selection_start=None, selection_end=None),
    )

    assert surface.cursor.moves == []
    assert surface.published_cursors == []
