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

"""Tests for prompt autocomplete query behavior ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.prompt_autocomplete_queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
)
from substitute.application.prompt_editor.prompt_autocomplete_query_service import (
    PromptAutocompleteQueryService,
    autocomplete_replacement_text,
    filter_noop_autocomplete_suggestions,
)
from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)

PROJECT_ROOT = Path(__file__).parents[1]
QUERY_SERVICE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_autocomplete_query_service.py"
)
TAG_RANGES_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "prompt_editor"
    / "prompt_autocomplete_tag_ranges.py"
)
_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_prompt_autocomplete_query_service_builds_plain_tag_query() -> None:
    """Resolve plain tag autocomplete from parsed document segment bounds."""

    projector = PromptDocumentProjector()
    query_service = PromptAutocompleteQueryService(document_projector=projector)
    text = "1girl blue ha solo"
    document_view = projector.build_document_view(text)
    cursor_position = text.index("ha") + len("ha")

    query = query_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query == PromptAutocompleteQuery(
        prefix="1girl blue ha",
        word_start=0,
        word_end=cursor_position,
        active_tag_end=len(text),
        fallback_query=PromptAutocompleteFallbackQuery(
            prefix="ha",
            word_start=text.index("ha"),
            word_end=cursor_position,
            active_tag_end=cursor_position,
        ),
    )


def test_prompt_autocomplete_query_service_keeps_space_inside_tag_query() -> None:
    """Keep tag autocomplete alive after horizontal whitespace inside a tag."""

    projector = PromptDocumentProjector()
    query_service = PromptAutocompleteQueryService(document_projector=projector)
    text = "re "
    document_view = projector.build_document_view(text)

    query = query_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query == PromptAutocompleteQuery(
        prefix="re ",
        word_start=0,
        word_end=len(text),
        active_tag_end=len(text),
        fallback_query=None,
    )


def test_prompt_autocomplete_query_service_builds_specialized_queries() -> None:
    """Resolve wildcard, scene, and LoRA autocomplete ranges."""

    query_service = PromptAutocompleteQueryService()

    wildcard_query = query_service.wildcard_autocomplete_query_at_cursor(
        text="{ani}",
        cursor_position=len("{ani"),
        has_selection=False,
    )
    scene_query = query_service.scene_autocomplete_query_at_cursor(
        text="  **Ca  ",
        cursor_position=len("  **Ca"),
        has_selection=False,
    )
    lora_query = query_service.lora_autocomplete_query_at_cursor(
        text="<LoRA:Mid:0.75>, next",
        cursor_position=len("<LoRA:Mid"),
        has_selection=False,
    )

    assert wildcard_query is not None
    assert (wildcard_query.prefix, wildcard_query.replacement_end) == (
        "ani",
        len("{ani}"),
    )
    assert scene_query is not None
    assert (scene_query.prefix, scene_query.marker_start, scene_query.title_start) == (
        "Ca",
        2,
        4,
    )
    assert lora_query is not None
    assert (
        lora_query.query_text,
        lora_query.typed_weight_text,
        lora_query.has_closing_bracket,
    ) == ("Mid", "0.75", True)


def test_prompt_autocomplete_query_service_normalizes_replacements() -> None:
    """Format accepted tags and suppress suggestions that match the active text."""

    text = r"cat \(animal\)"
    query = PromptAutocompleteQuery(
        prefix="cat (animal)",
        word_start=0,
        word_end=len("cat (animal)"),
        active_tag_end=len(text),
    )
    suggestions = (
        PromptAutocompleteSuggestion("cat_(animal)", 100),
        PromptAutocompleteSuggestion("cat_ears", 50),
    )

    filtered_suggestions = filter_noop_autocomplete_suggestions(
        text=text,
        query=query,
        suggestions=suggestions,
    )

    assert autocomplete_replacement_text("looking_at_viewer") == "looking at viewer"
    assert autocomplete_replacement_text("cat_(animal)") == r"cat \(animal\)"
    assert filtered_suggestions == (PromptAutocompleteSuggestion("cat_ears", 50),)


def test_prompt_autocomplete_query_modules_have_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep prompt autocomplete query behavior portable across Qt host bindings."""

    imported_modules: set[str] = set()
    for source_path in (QUERY_SERVICE_SOURCE, TAG_RANGES_SOURCE):
        syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))
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
