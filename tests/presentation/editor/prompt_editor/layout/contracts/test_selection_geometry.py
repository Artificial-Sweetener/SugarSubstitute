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


from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_selection_rects_include_selected_empty_lines() -> None:
    """Selected blank visual rows should expose one synthetic highlight rect."""

    layout, _ = _layout_for("alpha\n\nbeta")
    blank_line = next(
        line for line in layout.frame.output.snapshot.lines if not line.fragments
    )  # noqa: SLF001

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(anchor_position=6, cursor_position=7)
    )

    assert any(abs(rect.top() - blank_line.top) < 1.0 for rect in selection_rects)
    blank_line_rect = next(
        rect for rect in selection_rects if abs(rect.top() - blank_line.top) < 1.0
    )
    assert blank_line_rect.width() >= 8.0


def test_projection_line_snapshots_distinguish_content_from_line_break() -> None:
    """Hard-wrapped lines should expose visible content and newline boundaries."""

    layout, _ = _layout_for("alpha\nbeta")
    first_line = layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    second_line = layout.frame.output.snapshot.lines[1]  # noqa: SLF001

    assert first_line.source_content_start == 0
    assert first_line.source_content_end == 5
    assert first_line.line_break_start == 5
    assert first_line.line_break_end == 6
    assert second_line.source_content_start == 6
    assert second_line.source_content_end == 10
    assert second_line.line_break_start is None
    assert second_line.line_break_end is None


def test_projection_layout_selection_rects_show_selected_line_break() -> None:
    """Selected hard line breaks should visibly extend the selected source range."""

    layout, _ = _layout_for("alpha\nbeta")
    first_line = layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    first_fragment = first_line.fragments[0]

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(anchor_position=0, cursor_position=6)
    )

    first_line_right = max(
        rect.right()
        for rect in selection_rects
        if abs(rect.top() - first_line.top) < 1.0
    )
    assert first_line_right > first_fragment.rect.right() + 4.0


def test_projection_layout_selection_rects_do_not_invent_soft_wrap_breaks() -> None:
    """Soft-wrapped line ends should not receive hard-line-break selection affordances."""

    layout, _ = _layout_for("alpha beta gamma delta epsilon zeta eta theta")
    first_line = layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    first_line_content_right = max(
        fragment.rect.right() for fragment in first_line.fragments
    )

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(
            anchor_position=first_line.source_start,
            cursor_position=first_line.source_end,
        )
    )

    first_line_right = max(
        rect.right()
        for rect in selection_rects
        if abs(rect.top() - first_line.top) < 1.0
    )
    assert first_line.line_break_start is None
    assert first_line.line_break_end is None
    assert first_line_right <= first_line_content_right + 1.0


def test_projection_layout_selection_rects_include_empty_line_at_active_boundary() -> (
    None
):
    """Landing the selection endpoint on an empty row should still paint that row."""

    layout, _ = _layout_for("alpha\n\nbeta")
    blank_line = next(
        line for line in layout.frame.output.snapshot.lines if not line.fragments
    )  # noqa: SLF001

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(anchor_position=0, cursor_position=6)
    )

    assert any(abs(rect.top() - blank_line.top) < 1.0 for rect in selection_rects)


def test_projection_layout_selection_rects_ignore_empty_line_anchor_boundary() -> None:
    """Starting on an empty row should not paint it when selecting the previous break."""

    layout, _ = _layout_for("\n\n")
    anchored_line = layout.frame.output.snapshot.lines[1]  # noqa: SLF001

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(anchor_position=1, cursor_position=0)
    )

    assert selection_rects
    assert all(abs(rect.top() - anchored_line.top) >= 1.0 for rect in selection_rects)


def test_projection_layout_selection_rects_exclude_blank_line_before_next_line_start() -> (
    None
):
    """Selecting from the next line's first column should not highlight the blank row above."""

    layout, _ = _layout_for("some, prompt, tags,\n\nblue and pink,\n")
    blank_line = next(
        line
        for line in layout.frame.output.snapshot.lines  # noqa: SLF001
        if not line.fragments and line.source_end == 21
    )

    selection_rects = layout.frame.geometry.selection.selection_rects(
        PromptProjectionSelection(anchor_position=21, cursor_position=34)
    )

    assert all(abs(rect.top() - blank_line.top) >= 1.0 for rect in selection_rects)


def test_projection_layout_source_range_fragments_do_not_include_empty_line_selection_affordances() -> (
    None
):
    """Source-range fragments should exclude synthetic blank-line selection geometry."""

    layout, _ = _layout_for("alpha\n\nbeta, gamma")
    blank_line = next(
        line for line in layout.frame.output.snapshot.lines if not line.fragments
    )  # noqa: SLF001

    fragments = layout.frame.geometry.selection.source_range_fragments(
        7,
        11,
        viewport_rect=QRectF(0.0, 0.0, 360.0, 220.0),
        scroll_offset=0.0,
    )

    assert fragments
    assert all(abs(rect.top() - blank_line.top) >= 1.0 for rect in fragments)
    assert len(fragments) == 1


def test_projection_layout_reuses_source_line_rects_until_viewport_geometry_changes() -> (
    None
):
    """Repeated paint consumers should share source-line geometry for one frame."""

    prompt_text = "\n".join(f"line {index}, alpha beta gamma" for index in range(30))
    layout, _ = _layout_for(prompt_text, text_width=180.0)
    viewport_rect = QRectF(0.0, 0.0, 180.0, 160.0)

    initial_rects = layout.frame.geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    repeated_rects = layout.frame.geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    scrolled_rects = layout.frame.geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=24.0,
    )
    repeated_scrolled_rects = layout.frame.geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=24.0,
    )

    assert repeated_rects is initial_rects
    assert repeated_scrolled_rects is scrolled_rects
    assert scrolled_rects is not initial_rects
    assert scrolled_rects[0].rect.top() < initial_rects[0].rect.top()
