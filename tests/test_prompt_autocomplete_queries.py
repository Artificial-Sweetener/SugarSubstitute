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

"""Tests for prompt autocomplete query view-model ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor import (
    PromptAutocompleteQuery as FacadePromptAutocompleteQuery,
)
from substitute.application.prompt_editor.prompt_autocomplete_queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.prompt_document_service import (
    PromptAutocompleteQuery as ServicePromptAutocompleteQuery,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_autocomplete_query_carries_fallback_range() -> None:
    """Preserve fallback query data for larger active replacement ranges."""

    fallback_query = PromptAutocompleteFallbackQuery(
        prefix="alp",
        word_start=3,
        word_end=6,
        active_tag_end=11,
    )
    query = PromptAutocompleteQuery(
        prefix="alpha beta",
        word_start=0,
        word_end=10,
        active_tag_end=11,
        fallback_query=fallback_query,
    )

    assert query.fallback_query is fallback_query
    assert query.active_tag_end == 11


def test_prompt_autocomplete_specific_query_shapes_are_unchanged() -> None:
    """Keep wildcard and scene autocomplete query fields explicit."""

    wildcard_query = PromptWildcardAutocompleteQuery(
        prefix="cha",
        opener_start=4,
        content_start=6,
        cursor_position=9,
        replacement_end=11,
    )
    scene_query = PromptSceneAutocompleteQuery(
        prefix="intro",
        marker_start=0,
        title_start=3,
        cursor_position=8,
        replacement_end=12,
    )

    assert wildcard_query.content_start == 6
    assert scene_query.title_start == 3


def test_prompt_document_service_and_facade_reexport_query_models() -> None:
    """Keep existing aggregate import surfaces bound to the extracted DTO owner."""

    assert ServicePromptAutocompleteQuery is PromptAutocompleteQuery
    assert FacadePromptAutocompleteQuery is PromptAutocompleteQuery


def test_prompt_autocomplete_queries_have_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt autocomplete query models portable across host environments."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_autocomplete_queries.py"
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
