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

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.reorder.drop import PromptReorderDropService
from substitute.application.prompt_editor.reorder.projection import (
    PromptReorderProjectionService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderRowView,
)

PROJECT_ROOT = Path(__file__).parents[1]
DROP_SERVICE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "reorder"
    / "drop.py"
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
    """Apply follow-up targets against one authoritative in-session state."""

    projector = PromptDocumentProjector()
    document_view = projector.build_document_view("alpha, beta, gamma")
    drop_service = PromptReorderDropService(document_projector=projector)
    session = PromptReorderProjectionService(
        document_projector=projector
    ).build_reorder_session_view(document_view)
    first_base = drop_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=2,
    )
    current = drop_service.build_preview_drop_state(
        document_view,
        first_base,
        dragged_segment_index=2,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    follow_up_base = drop_service.build_base_drag_state(
        document_view,
        current.reorder_state,
        current_layout_view=current.layout_view,
        dragged_segment_index=1,
    )
    preview = drop_service.build_preview_drop_state(
        document_view,
        follow_up_base,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )

    assert preview.layout_view.rows == (
        PromptReorderRowView(row_index=0, chip_indices=(2, 1, 0)),
    )
    assert preview.reorder_state.ordered_chip_indices == (2, 1, 0)


def test_prompt_reorder_drop_service_can_drop_into_after_last_gap() -> None:
    """Insert a dragged chip into an exposed after-last-row blank-line target."""

    document_view = PromptDocumentProjector().build_document_view("1girl,\n\numbrella,")
    projector = PromptDocumentProjector()
    drop_service = PromptReorderDropService(document_projector=projector)
    session = PromptReorderProjectionService(
        document_projector=projector
    ).build_reorder_session_view(document_view)
    base = drop_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=1,
    )
    preview = drop_service.build_preview_drop_state(
        document_view,
        base,
        dragged_segment_index=1,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=0),
    )

    assert preview.layout_view.gaps[-1] == PromptReorderGapView(
        gap_index=1,
        separator_text=",\n\n",
        blank_line_count=1,
        placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
    )


def test_prompt_reorder_drop_service_derives_mixed_region_targets_from_state() -> None:
    """Mixed separator syntax must never publish rows absent from mutation state."""

    source = (
        "tag0, tag1\n[SEP]\ntag2, tag3\n[SEP]\ntag4,\ntag5,\n"
        "[SEP]\ntag6,\n\n\ntag7,\n[SEP]\ntag8,\n[SEP]\ntag9,"
    )
    projector = PromptDocumentProjector()
    document_view = projector.build_document_view(source)
    drop_service = PromptReorderDropService(document_projector=projector)
    projection_service = PromptReorderProjectionService(document_projector=projector)
    session = projection_service.build_reorder_session_view(document_view)

    base = drop_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=9,
    )
    derived_layout = projection_service.build_reorder_layout_view_from_state(
        base.reorder_state
    )

    assert base.layout_view.rows == derived_layout.rows
    for row in base.layout_view.rows:
        for insertion_index in range(len(row.chip_indices) + 1):
            preview = drop_service.build_preview_drop_state(
                document_view,
                base,
                dragged_segment_index=9,
                drop_target=PromptLineDropTarget(
                    row_index=row.row_index,
                    insertion_index=insertion_index,
                ),
            )
            assert preview.layout_view.rows


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


def test_prompt_reorder_drop_service_exposes_only_atomic_session_transitions() -> None:
    """Keep authoritative reorder state and its derived layout inseparable."""

    source = DROP_SERVICE_SOURCE.read_text(encoding="utf-8")

    assert "def build_base_drag_state(" in source
    assert "def build_preview_drop_state(" in source
    assert "def build_base_drag_layout_view_from_layout(" not in source
    assert "def build_base_drag_reorder_state_from_state(" not in source
    assert "def build_preview_drop_layout_view_from_layout(" not in source
    assert "def build_preview_drop_reorder_state_from_state(" not in source
