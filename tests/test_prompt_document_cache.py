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

"""Tests for prompt document cache ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_document_cache import (
    cached_prompt_document,
    cached_prompt_document_view,
    clear_prompt_document_caches,
    prewarm_prompt_document_views,
    store_prompt_document_view,
)
from substitute.application.prompt_editor.prompt_document_views import (
    PromptDocumentView,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_cached_prompt_document_reuses_parsed_documents() -> None:
    """Return the same parsed document instance for repeated source text."""

    clear_prompt_document_caches()

    first_document = cached_prompt_document("alpha, beta")
    second_document = cached_prompt_document("alpha, beta")

    assert second_document is first_document


def test_prompt_document_view_cache_reuses_stored_views() -> None:
    """Return stored prompt document views from the view cache."""

    clear_prompt_document_caches()
    document_view = _document_view("alpha")

    store_prompt_document_view("alpha", document_view)

    assert cached_prompt_document_view("alpha") is document_view


def test_prompt_document_cache_prewarm_uses_supplied_view_builder() -> None:
    """Populate view caches through the caller-owned projection function."""

    clear_prompt_document_caches()
    built_texts: list[str] = []

    def build_document_view(text: str) -> PromptDocumentView:
        """Record one projection request and return a minimal view."""

        built_texts.append(text)
        document_view = _document_view(text)
        store_prompt_document_view(text, document_view)
        return document_view

    warmed_count = prewarm_prompt_document_views(
        ("alpha", "beta"),
        build_document_view,
    )

    assert warmed_count == 2
    assert built_texts == ["alpha", "beta"]
    assert cached_prompt_document_view("alpha") is not None
    assert cached_prompt_document_view("beta") is not None


def test_prompt_document_cache_has_no_qt_presentation_or_adapter_imports() -> None:
    """Keep prompt document caches portable across host environments."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_document_cache.py"
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


def _document_view(text: str) -> PromptDocumentView:
    """Build a minimal prompt document view for cache storage tests."""

    return PromptDocumentView(
        source_text=text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        has_trailing_comma=False,
    )
