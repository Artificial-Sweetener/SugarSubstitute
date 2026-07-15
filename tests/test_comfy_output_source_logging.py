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

"""Tests for Comfy listener output-source resolution diagnostics."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.listener_output_source_resolver import (
    ListenerOutputSourceResolver,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceDiagnostic,
)

_RESOLVER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_output_source_resolver.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_listener_output_source_resolver_imports_no_ui_or_listener_boundaries() -> None:
    """Listener source resolution must stay independent of UI and listener code."""

    source = _RESOLVER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_ambiguous_output_source_mapping_warns_once() -> None:
    """Repeated ambiguous output-source lookups should not repeat warnings."""

    diagnostics: list[OutputSourceDiagnostic] = []
    resolver = ListenerOutputSourceResolver(
        workflow_id="workflow-1",
        prompt_id="prompt-1",
        workflow_payload={
            "0": {"_meta": {"title": "Cube.output"}},
            "12": {
                "class_type": "SugarCubes.CubeOutput",
                "inputs": {"image": ["0", 0]},
            },
            "22": {
                "class_type": "SugarCubes.CubeOutput",
                "inputs": {"image": ["0", 0]},
            },
            "5": {
                "class_type": "SugarCubes.CubeOutput",
                "inputs": {"image": ["0", 0]},
            },
        },
        cube_output_node_ids={"12", "22", "5"},
        on_diagnostic=diagnostics.append,
    )

    first = resolver.resolve("0")
    second = resolver.resolve("0")

    assert first == second
    assert first.source_key == "workflow-1:0"
    assert [diagnostic.level for diagnostic in diagnostics] == ["warning", "debug"]
    assert all(
        diagnostic.message
        == "Using node-local output source after ambiguous cube-output mapping"
        for diagnostic in diagnostics
    )
