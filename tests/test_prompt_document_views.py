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

"""Tests for prompt document view-model ownership."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from substitute.application.prompt_editor import (
    PromptDocumentView as FacadePromptDocumentView,
)
from substitute.application.prompt_editor.prompt_document_service import (
    PromptDocumentView as ServicePromptDocumentView,
)
from substitute.application.prompt_editor.prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptSegmentView,
    PromptSyntaxSpanView,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_document_view_models_are_immutable_value_objects() -> None:
    """Expose prompt document data without requiring domain or Qt objects."""

    segment = PromptSegmentView(
        index=0,
        text="(alpha:1.2)",
        display_text="alpha",
        display_source_start=1,
        display_source_end=6,
        selection_start=0,
        selection_end=11,
        separator_text_after="",
        has_separator_after=False,
    )
    emphasis = PromptEmphasisView(
        outer_start=0,
        outer_end=11,
        content_start=1,
        content_end=6,
        weight_start=7,
        weight_end=10,
        weight=Decimal("1.2"),
        weight_text="1.2",
        depth=0,
    )

    document_view = PromptDocumentView(
        source_text="(alpha:1.2)",
        segments=(segment,),
        emphasis_spans=(emphasis,),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(PromptSyntaxSpanView(kind="emphasis", start=0, end=11, depth=0),),
        has_trailing_comma=False,
    )

    assert document_view.segments == (segment,)
    assert document_view.emphasis_spans == (emphasis,)
    assert document_view.syntax_spans[0].kind == "emphasis"


def test_prompt_document_service_and_facade_reexport_view_models() -> None:
    """Keep existing import surfaces bound to the extracted DTO owner."""

    assert ServicePromptDocumentView is PromptDocumentView
    assert FacadePromptDocumentView is PromptDocumentView


def test_prompt_document_views_have_no_qt_presentation_or_adapter_imports() -> None:
    """Keep prompt document view models portable across host environments."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_document_views.py"
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
