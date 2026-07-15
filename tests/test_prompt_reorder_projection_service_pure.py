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

"""Tests for pure prompt reorder projection ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.prompt_reorder_projection_service import (
    PromptReorderProjectionService,
    domain_target_from_view,
    domain_state_from_view,
    ordered_chip_indices_from_layout_view,
    state_from_layout_view,
)
from substitute.application.prompt_editor.prompt_reorder_views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
)
from substitute.domain.prompt import (
    PromptGapBlankLineDropTarget as DomainPromptGapBlankLineDropTarget,
    PromptLineDropTarget as DomainPromptLineDropTarget,
)

PROJECT_ROOT = Path(__file__).parents[1]
PROJECTION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_reorder_projection_service.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_reorder_projection_service_builds_chips_and_layout() -> None:
    """Project domain reorder chips and layout into application view models."""

    document_view = PromptDocumentProjector().build_document_view("alpha,\n\nbeta,")
    projection_service = PromptReorderProjectionService()

    session_view = projection_service.build_reorder_session_view(document_view)

    assert [chip.display_text for chip in session_view.chips] == ["alpha", "beta"]
    assert session_view.reorder_state.ordered_chip_indices == (0, 1)
    assert session_view.reorder_state.has_trailing_comma is True
    assert [row.chip_indices for row in session_view.layout_view.rows] == [(0,), (1,)]
    assert session_view.layout_view.gaps[0].separator_text == ",\n\n"


def test_prompt_reorder_projection_service_roundtrips_layout_state() -> None:
    """Convert between authoritative reorder state and derived layout views."""

    document_view = PromptDocumentProjector().build_document_view("alpha, beta, gamma")
    projection_service = PromptReorderProjectionService()
    state_view = projection_service.build_reorder_state_view(document_view)
    layout_view = projection_service.build_reorder_layout_view_from_state(state_view)

    rebuilt_state = state_from_layout_view(
        layout_view,
        has_trailing_comma=document_view.has_trailing_comma,
    )

    assert domain_state_from_view(state_view) == rebuilt_state
    assert ordered_chip_indices_from_layout_view(layout_view) == (0, 1, 2)
    assert projection_service.reorder_layout_chip_indices(layout_view) == (0, 1, 2)


def test_prompt_reorder_projection_service_converts_drop_targets() -> None:
    """Map application drop-target DTOs into domain reorder targets."""

    line_target = domain_target_from_view(
        PromptLineDropTarget(row_index=2, insertion_index=1)
    )
    gap_target = domain_target_from_view(
        PromptGapBlankLineDropTarget(gap_index=3, blank_line_index=2)
    )

    assert isinstance(line_target, DomainPromptLineDropTarget)
    assert isinstance(gap_target, DomainPromptGapBlankLineDropTarget)
    assert line_target.row_index == 2
    assert line_target.insertion_index == 1
    assert gap_target.gap_index == 3
    assert gap_target.blank_line_index == 2


def test_prompt_reorder_projection_service_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt reorder projection portable across Qt host bindings."""

    syntax_tree = ast.parse(PROJECTION_SOURCE.read_text(encoding="utf-8"))

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
