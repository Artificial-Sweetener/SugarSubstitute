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

"""Tests for prompt document domain-to-view mapping."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_view_mapper import (
    prompt_document_view_from_domain,
    prompt_reorder_chip_view_from_domain,
)
from substitute.domain.prompt import build_reorder_chips, parse_prompt_document

PROJECT_ROOT = Path(__file__).parents[1]
MAPPER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_document_view_mapper.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_document_view_mapper_projects_domain_spans() -> None:
    """Map parsed domain ranges into application view DTOs without service state."""

    document = parse_prompt_document(
        r"  painting \(medium\), ((cat:1.20) dog:1.10), "
        r"{csv:monster:color|blue}, <lora:style:0.8:0.6>"
    )

    document_view = prompt_document_view_from_domain(document)

    assert document_view.source_text == document.source_text
    assert [segment.display_text for segment in document_view.segments] == [
        "painting (medium)",
        "((cat:1.20) dog:1.10)",
        "{csv:monster:color|blue}",
        "<lora:style:0.8:0.6>",
    ]
    assert document_view.segments[0].display_source_start == 2
    assert document_view.segments[0].has_separator_after is True
    assert document_view.emphasis_spans[0].weight_text == "1.10"
    assert document_view.wildcard_spans[0].identifier == "monster"
    assert document_view.wildcard_spans[0].csv_column == "color"
    assert document_view.wildcard_spans[0].tag == "blue"
    assert document_view.lora_spans[0].prompt_name == "style"
    assert document_view.lora_spans[0].first_weight_text == "0.8"
    assert document_view.lora_spans[0].second_weight_text == "0.6"
    assert {span.kind for span in document_view.syntax_spans} >= {
        "emphasis",
        "wildcard",
        "lora",
    }


def test_prompt_document_view_mapper_projects_reorder_chips() -> None:
    """Reorder chip mapping should preserve display labels and source ranges."""

    document = parse_prompt_document(r"  vertin \(reverse:1999\), solo,")
    chips = build_reorder_chips(document)

    chip_view = prompt_reorder_chip_view_from_domain(document, chips[0])

    assert chip_view.index == 0
    assert chip_view.text == r"  vertin \(reverse:1999\)"
    assert chip_view.display_text == "vertin (reverse:1999)"
    assert chip_view.display_source_start == 2
    assert chip_view.has_separator_after is True
    assert chip_view.separator_text_after == ", "


def test_prompt_document_view_mapper_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt document mapping portable across host environments."""

    syntax_tree = ast.parse(MAPPER_SOURCE.read_text(encoding="utf-8"))

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
