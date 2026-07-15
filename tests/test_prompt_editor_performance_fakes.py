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

"""Tests for prompt editor performance fake services."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

from substitute.devtools.prompt_editor_performance.fakes import (
    autocomplete_gateway,
    danbooru_url_import_service,
    danbooru_wiki_service_for_scenario,
    immediate_danbooru_import_dispatcher,
    lora_catalog,
    scheduled_lora_for_context_menu,
    scheduled_lora_resolver_for_scenario,
    segment_preset_source_for_scenario,
    spellcheck_service_for_scenario,
    wildcard_gateway,
)
from substitute.devtools.prompt_editor_performance.metrics import OperationCounter
from substitute.devtools.prompt_editor_performance.scenarios import (
    DANBOORU_IMPORT_URL,
    Scenario,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAKES_MODULE = (
    PROJECT_ROOT / "substitute" / "devtools" / "prompt_editor_performance" / "fakes.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.prompt_editor",
    "substitute.presentation.widgets",
    "tests",
    "tools",
)


def test_prompt_editor_performance_fakes_import_no_qt_widgets_or_tools() -> None:
    """Fake services must not depend on Qt widgets, tests, or CLI modules."""

    imported_modules = _imported_module_names(
        ast.parse(FAKES_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_autocomplete_and_wildcard_fakes_return_deterministic_rows() -> None:
    """Autocomplete fake services should return stable rows and record searches."""

    autocomplete_counter = OperationCounter()
    autocomplete = cast(Any, autocomplete_gateway("static", autocomplete_counter))
    empty_autocomplete = cast(Any, autocomplete_gateway("empty", OperationCounter()))
    wildcard_counter = OperationCounter()
    wildcards = cast(Any, wildcard_gateway("static", wildcard_counter))

    assert tuple(row.tag for row in autocomplete.search("ha")) == (
        "hair ornament",
        "hair ribbon",
    )
    assert empty_autocomplete.search("ha") == ()
    assert tuple(row.tag for row in wildcards.search_wildcards("li")) == (
        "lighting/day",
        "lighting/night",
    )
    assert autocomplete_counter.count == 1
    assert wildcard_counter.count == 1


def test_lora_and_spellcheck_fakes_return_prompt_editor_data() -> None:
    """LoRA and spellcheck fakes should expose stable application DTOs."""

    lora_counter = OperationCounter()
    catalog = cast(Any, lora_catalog("static", lora_counter))
    empty_catalog = cast(Any, lora_catalog("empty", OperationCounter()))
    spellcheck = cast(
        Any,
        spellcheck_service_for_scenario(
            Scenario("spellcheck", "mispelled prompt", spellcheck_enabled=True)
        ),
    )

    assert catalog.find_lora("detail_booster").display_name == "Detail Booster"
    assert tuple(item.prompt_name for item in catalog.list_loras()) == (
        "detail_booster",
    )
    assert empty_catalog.list_loras() == ()
    assert spellcheck.snapshot_for_text("mispelled prompt").issues[0].word == (
        "mispelled"
    )
    assert spellcheck.suggestions_for_word("mispelled").suggestions == ("misspelled",)
    assert lora_counter.count >= 2


def test_danbooru_and_scheduled_lora_fakes_are_deterministic() -> None:
    """Danbooru and scheduled-LoRA fakes should avoid network or backend work."""

    import_service = danbooru_url_import_service()
    result_log: list[int] = []
    error_log: list[BaseException] = []
    dispatcher = cast(Any, immediate_danbooru_import_dispatcher())
    scheduled = scheduled_lora_for_context_menu()
    resolver = scheduled_lora_resolver_for_scenario(
        Scenario(
            "scheduled",
            "<lora:detail_booster:0.8>",
            scheduled_lora_context_enabled=True,
        )
    )
    wiki = cast(
        Any,
        danbooru_wiki_service_for_scenario(
            Scenario("wiki", "blue_hair", danbooru_wiki_enabled=True)
        ),
    )

    classification = import_service.classify_url(DANBOORU_IMPORT_URL)
    dispatcher.submit(
        lambda: import_service.import_prompt_from_url(DANBOORU_IMPORT_URL),
        completed=lambda result: result_log.append(
            result.imported_prompt.source_post_id
        ),
        failed=error_log.append,
    )

    assert classification is not None
    assert classification.lookup_value == "123456"
    assert result_log == [123456]
    assert error_log == []
    assert scheduled.prompt_name == "detail_booster"
    assert scheduled.source == "cube_field"
    assert resolver is not None
    assert resolver("ignored")[0].prompt_name == "detail_booster"
    assert wiki.lookup_selection("blue_hair") == "blue_hair"


def test_segment_preset_source_uses_structural_menu_data_without_qt_scope() -> None:
    """Segment preset fake should expose the fields consumed by the controller."""

    source = cast(
        Any,
        segment_preset_source_for_scenario(
            Scenario("segment", "blue hair", segment_presets_enabled=True)
        ),
    )

    snapshot = source.list_prompt_segment_presets()
    menu_model = snapshot.menu_model

    assert snapshot.catalog_identity.source_revision == 1
    assert snapshot.status.readiness.value == "warm"
    assert menu_model.sections[0].presets[0].label == "Detailed portrait"
    assert menu_model.save_scopes[0].title == "Global"
    assert menu_model.save_scopes[0].association is not None


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
