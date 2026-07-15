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

"""Tests for prompt reorder serialization behavior ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.prompt_reorder_projection_service import (
    PromptReorderProjectionService,
)
from substitute.application.prompt_editor.prompt_reorder_serialization_service import (
    PromptReorderSerializationService,
    blank_line_drop_offsets,
)
from substitute.application.prompt_editor.prompt_reorder_views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)

PROJECT_ROOT = Path(__file__).parents[1]
SERIALIZATION_SERVICE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_reorder_serialization_service.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_reorder_serialization_service_preserves_lora_inline_separators() -> (
    None
):
    """Serialize no-comma LoRA layouts without inserting row-default comma text."""

    document_projector = PromptDocumentProjector()
    projection_service = PromptReorderProjectionService(
        document_projector=document_projector,
    )
    serialization_service = PromptReorderSerializationService(
        document_projector=document_projector,
    )
    document_view = document_projector.build_document_view("<lora:a:1.0> <lora:b:1.0>")
    layout_view = projection_service.build_reorder_layout_view(document_view)

    serialized_text = serialization_service.serialize_reorder_layout_view(
        document_view,
        layout_view,
    )
    preview_snapshot = serialization_service.build_reorder_preview_snapshot(
        document_view,
        layout_view,
    )

    assert serialized_text == "<lora:a:1.0> <lora:b:1.0>"
    assert preview_snapshot.text == "<lora:a:1.0> <lora:b:1.0>"


def test_prompt_reorder_serialization_service_maps_trailing_edge_gap_range() -> None:
    """Expose appended after-last-row gap text as a stable preview gap range."""

    document_projector = PromptDocumentProjector()
    serialization_service = PromptReorderSerializationService(
        document_projector=document_projector,
    )
    document_view = document_projector.build_document_view("1girl, umbrella,")
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )

    preview_snapshot = serialization_service.build_reorder_preview_snapshot(
        document_view,
        layout_view,
    )

    assert preview_snapshot.text == "1girl, umbrella,\n\n"
    assert preview_snapshot.gap_ranges_by_index == {0: (15, 18)}


def test_prompt_reorder_serialization_service_serializes_authoritative_state() -> None:
    """Serialize source state directly without depending on layout row order."""

    document_projector = PromptDocumentProjector()
    projection_service = PromptReorderProjectionService(
        document_projector=document_projector,
    )
    serialization_service = PromptReorderSerializationService(
        document_projector=document_projector,
    )
    document_view = document_projector.build_document_view("alpha, beta, gamma")
    state_view = projection_service.build_reorder_state_view(document_view)

    serialized_text = serialization_service.serialize_reorder_state_view(
        document_view,
        state_view,
    )

    assert serialized_text == "alpha, beta, gamma"


def test_prompt_reorder_serialization_service_exposes_blank_line_offsets() -> None:
    """Keep blank-line target calculations available from the serialization owner."""

    assert blank_line_drop_offsets(",\n\nbeta") == (2,)


def test_prompt_reorder_serialization_service_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep reorder serialization portable across Qt host bindings."""

    syntax_tree = ast.parse(SERIALIZATION_SERVICE_SOURCE.read_text(encoding="utf-8"))

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
