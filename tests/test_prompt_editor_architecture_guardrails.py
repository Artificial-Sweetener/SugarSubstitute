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

"""Prevent prompt-editor architecture debt from growing during migration."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tests.architecture_import_graph import (
    internal_import_graph,
    python_module_paths,
    strongly_connected_components,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DOMAIN_ROOT = PROJECT_ROOT / "substitute" / "domain" / "prompt"
PROMPT_APPLICATION_ROOT = PROJECT_ROOT / "substitute" / "application" / "prompt_editor"
PROMPT_PRESENTATION_ROOT = (
    PROJECT_ROOT / "substitute" / "presentation" / "editor" / "prompt_editor"
)
EDITOR_PANEL_ROOT = PROJECT_ROOT / "substitute" / "presentation" / "editor" / "panel"
PROMPT_ARCHITECTURE_ROOTS = (
    PROMPT_DOMAIN_ROOT,
    PROMPT_APPLICATION_ROOT,
    PROMPT_PRESENTATION_ROOT,
    EDITOR_PANEL_ROOT,
)
PANEL_MODULE_PREFIX = "substitute.presentation.editor.panel"

_EXPECTED_PROMPT_TO_PANEL_IMPORTS = {
    (
        "substitute.presentation.editor.prompt_editor.features."
        "prompt_segment_preset_source"
    ): frozenset(
        {
            "substitute.presentation.editor.panel.context.active_model_snapshot",
            "substitute.presentation.editor.panel.menus.preset_model_scope_policy",
        }
    )
}
_EXPECTED_IMPORT_CYCLES = (
    (
        "substitute.application.prompt_editor.prompt_lora_catalog_service",
        "substitute.application.prompt_editor.prompt_lora_ranking",
    ),
    (
        "substitute.presentation.editor.panel.view",
        "substitute.presentation.editor.panel.widgets.cube_section",
    ),
    (
        "substitute.presentation.editor.prompt_editor.commands",
        "substitute.presentation.editor.prompt_editor.commands.autocomplete_commands",
        "substitute.presentation.editor.prompt_editor.commands.clipboard_commands",
        "substitute.presentation.editor.prompt_editor.commands.diagnostic_commands",
        "substitute.presentation.editor.prompt_editor.commands.paste_import_commands",
        "substitute.presentation.editor.prompt_editor.commands.reorder_commands",
        "substitute.presentation.editor.prompt_editor.commands.trigger_word_commands",
        "substitute.presentation.editor.prompt_editor.commands.weight_commands",
    ),
    (
        "substitute.presentation.editor.prompt_editor.projection.hit_testing",
        "substitute.presentation.editor.prompt_editor.projection.layout_engine",
        "substitute.presentation.editor.prompt_editor.projection.painter",
        (
            "substitute.presentation.editor.prompt_editor.projection."
            "reorder_paint_snapshot_builder"
        ),
        "substitute.presentation.editor.prompt_editor.projection.selection_geometry",
        (
            "substitute.presentation.editor.prompt_editor.projection."
            "source_line_geometry"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _IntegrationRootBudget:
    """Limit one existing integration root while its ownership is extracted."""

    source_path: Path
    class_name: str
    maximum_lines: int
    maximum_methods: int


_INTEGRATION_ROOT_BUDGETS = (
    _IntegrationRootBudget(
        PROMPT_PRESENTATION_ROOT / "widget.py",
        "PromptEditor",
        2064,
        164,
    ),
    _IntegrationRootBudget(
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py",
        "PromptProjectionSurface",
        4877,
        276,
    ),
    _IntegrationRootBudget(
        PROMPT_PRESENTATION_ROOT / "projection" / "layout_engine.py",
        "PromptProjectionLayout",
        5682,
        115,
    ),
    _IntegrationRootBudget(
        PROMPT_PRESENTATION_ROOT / "interactions" / "controller.py",
        "PromptInteractionController",
        1154,
        94,
    ),
    _IntegrationRootBudget(
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py",
        "PromptEditorCompositionFactory",
        1098,
        14,
    ),
    _IntegrationRootBudget(
        EDITOR_PANEL_ROOT / "view.py",
        "EditorPanel",
        2425,
        148,
    ),
)


def test_prompt_editor_does_not_add_panel_dependency_inversions() -> None:
    """Freeze the known panel inversion until its migration slice removes it."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    actual = {
        module_name: frozenset(
            imported_module
            for imported_module in graph[module_name]
            if imported_module.startswith(PANEL_MODULE_PREFIX)
        )
        for module_name in module_paths
        if module_name.startswith(
            "substitute.presentation.editor.prompt_editor",
        )
    }

    assert {
        module_name: imports for module_name, imports in actual.items() if imports
    } == _EXPECTED_PROMPT_TO_PANEL_IMPORTS


def test_prompt_editor_import_cycles_do_not_grow() -> None:
    """Freeze known cycles so each authority transfer can only remove debt."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)

    assert strongly_connected_components(graph) == _EXPECTED_IMPORT_CYCLES


def test_prompt_editor_integration_roots_do_not_grow() -> None:
    """Require refactor slices to remove behavior from existing integration roots."""

    violations: dict[str, dict[str, int]] = {}
    for budget in _INTEGRATION_ROOT_BUDGETS:
        source = budget.source_path.read_text(encoding="utf-8")
        method_count = _class_method_count(source, budget.class_name)
        line_count = len(source.splitlines())
        if line_count > budget.maximum_lines or method_count > budget.maximum_methods:
            violations[budget.source_path.relative_to(PROJECT_ROOT).as_posix()] = {
                "lines": line_count,
                "maximum_lines": budget.maximum_lines,
                "methods": method_count,
                "maximum_methods": budget.maximum_methods,
            }

    assert violations == {}


def test_prompt_editor_private_and_protocol_debt_does_not_grow() -> None:
    """Freeze broad protocols, casts, and private-access exemptions for removal."""

    presentation_sources = tuple(PROMPT_PRESENTATION_ROOT.rglob("*.py"))
    prompt_test_sources = tuple(
        source_path
        for source_path in PROJECT_ROOT.glob("tests/*prompt*.py")
        if source_path != Path(__file__)
    )
    protocol_count = sum(
        _protocol_class_count(source_path) for source_path in presentation_sources
    )
    cast_count = sum(
        source_path.read_text(encoding="utf-8").count("cast(")
        for source_path in presentation_sources
    )
    production_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in presentation_sources
    )
    test_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in prompt_test_sources
    )

    assert {
        "protocols": protocol_count,
        "casts": cast_count,
        "production_private_exemptions": production_private_exemptions,
        "test_private_exemptions": test_private_exemptions,
    } == {
        "protocols": 201,
        "casts": 201,
        "production_private_exemptions": 11,
        "test_private_exemptions": 319,
    }


def _class_method_count(source: str, class_name: str) -> int:
    """Return direct method count for one named class."""

    tree = ast.parse(source)
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return sum(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        for node in class_node.body
    )


def _protocol_class_count(source_path: Path) -> int:
    """Return Protocol-derived class count in one source module."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return sum(
        isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id == "Protocol")
            or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
            for base in node.bases
        )
        for node in ast.walk(tree)
    )
