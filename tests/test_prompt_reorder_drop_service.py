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

"""Tests for prompt reorder drop behavior ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.prompt_reorder_drop_service import (
    PromptReorderDropService,
)
from substitute.application.prompt_editor.prompt_reorder_views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)

PROJECT_ROOT = Path(__file__).parents[1]
DROP_SERVICE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_reorder_drop_service.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_reorder_drop_service_builds_base_drag_layout() -> None:
    """Hide the dragged chip and expose the derived base-drag layout."""

    document_view = PromptDocumentProjector().build_document_view("alpha, beta, gamma")
    drop_service = PromptReorderDropService()

    layout_view = drop_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )

    assert layout_view.rows == (PromptReorderRowView(row_index=0, chip_indices=(0, 2)),)


def test_prompt_reorder_drop_service_builds_preview_from_current_layout() -> None:
    """Apply line targets against the supplied in-session layout."""

    document_view = PromptDocumentProjector().build_document_view("alpha, beta, gamma")
    drop_service = PromptReorderDropService()
    current_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(2, 0, 1)),),
        gaps=(),
    )

    preview_layout = drop_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )

    assert preview_layout.rows == (
        PromptReorderRowView(row_index=0, chip_indices=(2, 1, 0)),
    )


def test_prompt_reorder_drop_service_can_drop_into_after_last_gap() -> None:
    """Insert a dragged chip into an exposed after-last-row blank-line target."""

    document_view = PromptDocumentProjector().build_document_view("1girl,\n\numbrella,")
    drop_service = PromptReorderDropService()
    current_layout_view = PromptReorderLayoutView(
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

    preview_layout = drop_service.build_preview_drop_layout_view_from_layout(
        document_view,
        current_layout_view,
        dragged_segment_index=1,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )

    assert preview_layout.gaps[-1] == PromptReorderGapView(
        gap_index=1,
        separator_text=",\n\n",
        blank_line_count=1,
        placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
    )


def test_prompt_reorder_drop_service_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt reorder drop behavior portable across Qt host bindings."""

    syntax_tree = ast.parse(DROP_SERVICE_SOURCE.read_text(encoding="utf-8"))

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
