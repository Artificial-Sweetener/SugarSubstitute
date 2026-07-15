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

"""Tests for prompt reorder gap-layout ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_reorder_gap_layout import (
    gap_by_index,
    layout_view_from_rows_and_gaps,
    split_after_last_row_gap_for_insert,
    trailing_edge_separator_text_for_hidden_chip,
    with_trailing_edge_gap,
)
from substitute.application.prompt_editor.prompt_reorder_views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)

PROJECT_ROOT = Path(__file__).parents[1]
GAP_LAYOUT_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_reorder_gap_layout.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_reorder_gap_layout_builds_rows_and_edge_gap() -> None:
    """Build renumbered rows plus between-row and after-last-row gaps."""

    layout_view = layout_view_from_rows_and_gaps(
        [(0,), (2,)],
        between_separator_texts=(",\n\n",),
        trailing_edge_separator_text="\n\n",
    )

    assert [row.chip_indices for row in layout_view.rows] == [(0,), (2,)]
    assert layout_view.gaps == (
        PromptReorderGapView(
            gap_index=0,
            separator_text=",\n\n",
            blank_line_count=1,
            placement=PromptReorderGapPlacement.BETWEEN_ROWS,
        ),
        PromptReorderGapView(
            gap_index=1,
            separator_text="\n\n",
            blank_line_count=1,
            placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
        ),
    )


def test_prompt_reorder_gap_layout_splits_after_last_gap_without_comma() -> None:
    """Split an after-last gap while adding the comma owned by the inserted chip."""

    assert split_after_last_row_gap_for_insert(
        "\n\n",
        blank_line_index=0,
    ) == (",\n", "\n")


def test_prompt_reorder_gap_layout_exposes_hidden_final_row_separator() -> None:
    """Hiding a final singleton row should expose its incoming gap as edge text."""

    layout_view = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1,)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )

    edge_text = trailing_edge_separator_text_for_hidden_chip(
        layout_view,
        dragged_segment_index=1,
        has_trailing_comma=False,
    )

    assert edge_text == "\n\n\n"


def test_prompt_reorder_gap_layout_finds_after_last_gap() -> None:
    """Return stable gap lookup results after appending an edge gap."""

    layout_view = with_trailing_edge_gap(
        PromptReorderLayoutView(
            rows=(PromptReorderRowView(row_index=0, chip_indices=(0,)),),
            gaps=(),
        ),
        separator_text=",\n\n",
    )

    gap = gap_by_index(layout_view, 0)

    assert gap is not None
    assert gap.placement is PromptReorderGapPlacement.AFTER_LAST_ROW


def test_prompt_reorder_gap_layout_has_no_qt_presentation_or_adapter_imports() -> None:
    """Keep prompt reorder gap layout portable across Qt host bindings."""

    syntax_tree = ast.parse(GAP_LAYOUT_SOURCE.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    offenders = sorted(
        imported_module
        for imported_module in imported_modules
        if any(
            imported_module == forbidden_root
            or imported_module.startswith(f"{forbidden_root}.")
            for forbidden_root in _FORBIDDEN_IMPORT_ROOTS
        )
    )

    assert offenders == []
