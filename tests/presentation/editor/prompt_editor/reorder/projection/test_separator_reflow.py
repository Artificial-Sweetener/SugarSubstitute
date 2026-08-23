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

"""Verify prompt reorder preview-projection separator reflow."""

from __future__ import annotations


from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.theme import (
    semantic_palette_from_theme,
)

from .support import (
    _service,
    _context,
    _build_reorder_preview_state,
)


def test_reorder_projection_service_reflows_drag_snapshot_across_separator(
    app: QApplication,
) -> None:
    """Removing a regional chip should reflow from before its caretless separator."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "tag00\n[SEP]\nred, blue, green",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=1, insertion_index=0),
    )

    service.set_preview_state(
        preview_state,
        context=_context(active_drop_target_identity=("line", 1, 0)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    assert service.preview_document is not None
    assert service.preview_frame is not None
    assert service.base_drag_document is not None
    assert service.base_drag_frame is not None
    assert service.base_drag_document.source_text == "tag00\n[SEP]\nblue, green"
    assert tuple(
        (line.source_start, line.source_end)
        for line in service.base_drag_frame.output.snapshot.lines
    ) == ((0, 6), (6, 12), (12, 23))


def test_reorder_projection_service_reflows_across_second_separator_boundary(
    app: QApplication,
) -> None:
    """Target changes must preserve the caret host before a later separator."""

    _ = app
    source = (
        "best quality, score_7, masterpiece, very aesthetic\n\n"
        "2girls, standing, full body, looking at viewer, outdoors, "
        "cherry blossoms, school uniform,\n\n"
        "[SEP]\n"
        "1girl, red hair, long hair, green eyes, smile, blazer, pleated skirt, "
        "black thighhighs,\n\n"
        "[SEP]\n"
        "1girl, blue hair, short hair, blue eyes, serious, cardigan, "
        "pleated skirt, kneehighs\n"
    )
    service = _service()
    first_target = PromptLineDropTarget(row_index=2, insertion_index=0)
    next_target = PromptLineDropTarget(row_index=2, insertion_index=7)
    separator_starts_by_target: list[tuple[int, ...]] = []

    for target in (first_target, next_target):
        service.set_preview_state(
            _build_reorder_preview_state(
                source,
                dragged_chip_index=11,
                drop_target=target,
            ),
            context=_context(
                active_drop_target_identity=(
                    "line",
                    target.row_index,
                    target.insertion_index,
                )
            ),
            font=QFont(),
            palette=QPalette(),
            semantic_palette=semantic_palette_from_theme(),
        )
        assert service.preview_document is not None
        assert service.preview_frame is not None
        assert service.base_drag_document is not None
        assert service.base_drag_frame is not None
        separator_starts = tuple(
            run.projection_start
            for run in service.preview_document.runs
            if run.is_structural_row
        )
        separator_starts_by_target.append(separator_starts)
        for document, frame in (
            (service.preview_document, service.preview_frame),
            (service.base_drag_document, service.base_drag_frame),
        ):
            caret_rects = frame.output.snapshot.caret_rects_by_projection_position
            assert all(
                run.projection_start in caret_rects
                for run in document.runs
                if run.is_structural_row
            )

    assert separator_starts_by_target == [(144, 234), (144, 234)]
