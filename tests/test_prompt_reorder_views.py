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

"""Tests for prompt reorder view-model ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor import (
    PromptReorderLayoutView as FacadePromptReorderLayoutView,
)
from substitute.application.prompt_editor.prompt_document_service import (
    PromptReorderLayoutView as ServicePromptReorderLayoutView,
)
from substitute.application.prompt_editor.prompt_reorder_views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_reorder_row_equality_ignores_separator_slots() -> None:
    """Preserve row identity semantics while moving the DTO owner."""

    first = PromptReorderRowView(
        row_index=0,
        chip_indices=(0, 1),
        separator_slots=(", ", ",\n"),
    )
    second = PromptReorderRowView(
        row_index=0,
        chip_indices=(0, 1),
        separator_slots=("", ""),
    )

    assert first == second


def test_prompt_reorder_drop_target_alias_accepts_line_and_gap_targets() -> None:
    """Keep reorder drop targets typed as the same discriminated union."""

    line_target: PromptReorderDropTarget = PromptLineDropTarget(
        row_index=1,
        insertion_index=0,
    )
    gap_target: PromptReorderDropTarget = PromptGapBlankLineDropTarget(
        gap_index=2,
        blank_line_index=1,
    )

    assert isinstance(line_target, PromptLineDropTarget)
    assert isinstance(gap_target, PromptGapBlankLineDropTarget)


def test_prompt_reorder_service_and_facade_reexport_view_models() -> None:
    """Keep existing aggregate import surfaces bound to the extracted DTO owner."""

    assert ServicePromptReorderLayoutView is PromptReorderLayoutView
    assert FacadePromptReorderLayoutView is PromptReorderLayoutView


def test_prompt_reorder_views_have_no_qt_presentation_or_adapter_imports() -> None:
    """Keep prompt reorder view models portable across host environments."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_reorder_views.py"
    )
    syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))

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


def test_prompt_reorder_gap_defaults_to_between_rows() -> None:
    """Preserve default placement for logical gaps between populated rows."""

    layout = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0,)),),
        gaps=(
            PromptReorderGapView(gap_index=0, separator_text=",\n", blank_line_count=0),
        ),
    )

    assert layout.gaps[0].placement is PromptReorderGapPlacement.BETWEEN_ROWS
