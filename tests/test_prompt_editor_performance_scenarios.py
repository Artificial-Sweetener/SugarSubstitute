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

"""Tests for prompt editor performance scenario definitions."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.devtools.prompt_editor_performance.scenarios import (
    ALL_PROMPT_EDITOR_FEATURES,
    DANBOORU_IMPORT_URL,
    Scenario,
    scenarios,
)
from substitute.domain.prompt.features import PromptEditorFeature


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "scenarios.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_scenarios_imports_no_qt_or_tools() -> None:
    """Scenario definitions must stay reusable outside the Qt benchmark runner."""

    imported_modules = _imported_module_names(
        ast.parse(SCENARIOS_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_scenarios_preserve_core_benchmark_cases() -> None:
    """The scenario corpus should keep the known benchmark coverage points."""

    corpus = scenarios("typed secret")
    scenarios_by_name = {scenario.name: scenario for scenario in corpus}

    assert len(corpus) == 59
    assert scenarios_by_name["plain-prompt-type"] == Scenario(
        "plain-prompt-type",
        "",
        "typed secret",
    )
    assert scenarios_by_name["5k-large-prompt-type"].typed_text == "typed secret"
    assert scenarios_by_name["10k-large-prompt-type"].typed_text == "typed secret"
    assert len(scenarios_by_name["10k-large-prompt-type"].initial_text) > len(
        scenarios_by_name["5k-large-prompt-type"].initial_text
    )


def test_scenarios_keep_service_and_clipboard_requirements() -> None:
    """Special scenarios should retain the service flags consumed by the runner."""

    scenarios_by_name = {scenario.name: scenario for scenario in scenarios("ignored")}

    assert scenarios_by_name["wildcard-autocomplete"].wildcard_gateway == "static"
    assert scenarios_by_name["lora-autocomplete"].lora_catalog == "static"
    assert scenarios_by_name["context-menu-danbooru-actions"].danbooru_wiki_enabled
    assert scenarios_by_name["danbooru-paste-import"].clipboard_text == (
        DANBOORU_IMPORT_URL
    )
    assert scenarios_by_name["danbooru-paste-import"].danbooru_import_enabled


def test_reorder_arrow_scenarios_use_pure_key_intent() -> None:
    """Alt-arrow scenarios should not encode Qt key enum values in pure data."""

    scenarios_by_name = {scenario.name: scenario for scenario in scenarios("ignored")}

    assert scenarios_by_name["alt-arrow-horizontal"].reorder_keys == (
        "left",
        "right",
        "left",
        "right",
    )
    assert scenarios_by_name["alt-arrow-linebreak-up"].reorder_keys == (
        "up",
        "down",
        "up",
        "down",
    )


def test_all_prompt_editor_features_matches_domain_registry() -> None:
    """Feature profile coverage should track the domain feature enum."""

    assert ALL_PROMPT_EDITOR_FEATURES == tuple(PromptEditorFeature)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
