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

"""Tests for prompt document selection lookup ownership."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.prompt_document_selection_service import (
    PromptDocumentSelectionService,
    emphasis_span_at_cursor,
)
from substitute.application.prompt_editor.prompt_document_views import (
    PromptReorderChipView,
)

PROJECT_ROOT = Path(__file__).parents[1]
SELECTION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_document_selection_service.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_document_selection_service_finds_segment_at_cursor() -> None:
    """Locate the segment whose visible range contains the cursor."""

    document_view = PromptDocumentProjector().build_document_view("red, blue, green")
    selection_service = PromptDocumentSelectionService()

    segment = selection_service.segment_at_position(document_view, 9)

    assert segment is not None
    assert (segment.index, segment.display_text) == (1, "blue")


def test_prompt_document_selection_service_finds_reorder_chip_at_cursor() -> None:
    """Locate reorder chips by their visible selection range."""

    selection_service = PromptDocumentSelectionService()
    chip = PromptReorderChipView(
        index=2,
        text=" beta",
        serialized_text=" beta",
        display_text="beta",
        display_source_start=6,
        display_source_end=10,
        selection_start=5,
        selection_end=10,
        separator_text_after=", ",
        has_separator_after=True,
    )

    selected_chip = selection_service.reorder_chip_at_position((chip,), 10)

    assert selected_chip is chip


def test_prompt_document_selection_service_finds_emphasis_spans() -> None:
    """Resolve emphasis spans by cursor position and exact source ranges."""

    document_view = PromptDocumentProjector().build_document_view("((cat:1.2) dog:1.1)")
    selection_service = PromptDocumentSelectionService()

    cursor_span = selection_service.emphasis_at_position(document_view, 3)
    content_span = selection_service.emphasis_for_content_range(
        document_view,
        content_start=2,
        content_end=5,
    )
    outer_span = selection_service.emphasis_for_outer_range(
        document_view,
        outer_start=1,
        outer_end=10,
    )

    assert cursor_span is not None
    assert cursor_span.weight == Decimal("1.2")
    assert content_span is cursor_span
    assert outer_span is cursor_span


def test_emphasis_span_at_cursor_is_bounded_by_segment_selection() -> None:
    """Return the innermost emphasis span only when it belongs to the segment."""

    document_view = PromptDocumentProjector().build_document_view("alpha, (cat:1.2)")
    segment = document_view.segments[1]

    emphasis_span = emphasis_span_at_cursor(
        document_view,
        segment=segment,
        cursor_position=9,
    )

    assert emphasis_span is not None
    assert emphasis_span.weight == Decimal("1.2")
    assert (
        emphasis_span_at_cursor(
            document_view,
            segment=document_view.segments[0],
            cursor_position=9,
        )
        is None
    )


def test_prompt_document_selection_service_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt document selection portable across Qt host bindings."""

    syntax_tree = ast.parse(SELECTION_SOURCE.read_text(encoding="utf-8"))

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
