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

"""Tests for prompt document projection ownership."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from substitute.application.prompt_editor.document import projector as projector_module
from substitute.application.prompt_editor.document.cache import (
    clear_prompt_document_caches,
)
from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.domain.prompt.document.parser import parse_prompt_document


_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


@pytest.fixture(autouse=True)
def _clear_document_caches() -> Iterator[None]:
    """Isolate process-lifetime document projection cache state."""

    clear_prompt_document_caches()
    yield
    clear_prompt_document_caches()


def test_prompt_document_projector_reuses_cached_document_views() -> None:
    """Reuse cached projected views for repeated source text."""

    projector = PromptDocumentProjector()

    first_view = projector.build_document_view(r"alpha \(literal\), beta")
    second_view = projector.build_document_view(r"alpha \(literal\), beta")

    assert second_view is first_view
    assert [segment.display_text for segment in first_view.segments] == [
        "alpha (literal)",
        "beta",
    ]


def test_prompt_document_projector_projects_existing_domain_document() -> None:
    """Project parsed domain documents without reparsing source text."""

    projector = PromptDocumentProjector()
    document = parse_prompt_document(r"  cat, <lora:style:0.8>")

    document_view = projector.build_document_view_from_document(document)

    assert document_view.source_text == document.source_text
    assert document_view.segments[0].display_source_start == 2
    assert document_view.lora_spans[0].prompt_name == "style"


def test_prompt_document_projector_prewarms_document_views() -> None:
    """Populate document projection cache entries for every supplied source."""

    projector = PromptDocumentProjector()

    warmed_count = projector.prewarm_document_views(("alpha", "beta"))

    assert warmed_count == 2
    assert projector.build_document_view("alpha") is projector.build_document_view(
        "alpha"
    )


def test_prompt_document_projector_has_no_qt_presentation_or_adapter_imports() -> None:
    """Keep document projection portable across Qt host bindings."""

    source_path = Path(projector_module.__file__).resolve()
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
