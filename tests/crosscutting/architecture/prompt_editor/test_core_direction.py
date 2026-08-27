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

"""Keep prompt-editor core, layout, edit, and paint boundaries directional."""

from __future__ import annotations

import ast

from .inventory import (
    PROJECT_ROOT,
    PROMPT_PRESENTATION_ROOT,
    PANEL_MODULE_PREFIX,
    _EXPECTED_PROMPT_TO_PANEL_IMPORTS,
    _EXPECTED_IMPORT_CYCLES,
    prompt_editor_architecture_inventory,
)
from tests.crosscutting.architecture.import_graph import (
    strongly_connected_components,
)


def test_prompt_editor_does_not_depend_on_its_panel_host() -> None:
    """Keep every prompt-editor owner independent of its panel host."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
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

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph

    assert strongly_connected_components(graph) == _EXPECTED_IMPORT_CYCLES


def test_prompt_editor_core_cannot_depend_on_qt_or_outer_presentation() -> None:
    """Keep lower prompt-editor policy independent of Qt and presentation edges."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    core_prefix = "substitute.presentation.editor.prompt_editor.core"
    graph_violations = {
        module_name: tuple(
            sorted(
                imported_module
                for imported_module in graph[module_name]
                if imported_module.startswith(
                    "substitute.presentation.editor.prompt_editor"
                )
                and not imported_module.startswith(core_prefix)
            )
        )
        for module_name in graph
        if module_name.startswith(f"{core_prefix}.")
    }
    graph_violations = {
        module_name: imports
        for module_name, imports in graph_violations.items()
        if imports
    }
    qt_violations: list[str] = []
    for source_path in (PROMPT_PRESENTATION_ROOT / "core").rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        qt_violations.extend(
            f"{source_path.relative_to(PROJECT_ROOT).as_posix()}:{node.lineno}"
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "PySide6"
                    or node.module.startswith("PySide6.")
                    or node.module == "qfluentwidgets"
                    or node.module.startswith("qfluentwidgets.")
                )
            )
            or (
                isinstance(node, ast.Import)
                and any(
                    alias.name == "PySide6"
                    or alias.name.startswith("PySide6.")
                    or alias.name == "qfluentwidgets"
                    or alias.name.startswith("qfluentwidgets.")
                    for alias in node.names
                )
            )
        )

    assert graph_violations == {}
    assert qt_violations == []
