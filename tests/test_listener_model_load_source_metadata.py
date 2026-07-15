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

"""Tests for listener-scoped model-load source metadata resolution."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.listener_model_load_source_metadata import (
    ListenerModelLoadSourceMetadataResolver,
)
from substitute.infrastructure.comfy.model_load_source_metadata_resolver import (
    ModelLoadSourceMetadataDiagnostic,
)

_RESOLVER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_model_load_source_metadata.py"
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


def test_listener_model_load_source_metadata_imports_no_ui_or_listener_boundaries() -> (
    None
):
    """Listener metadata resolution must stay independent of UI and listener code."""

    source = _RESOLVER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_listener_model_load_source_metadata_resolves_and_emits_diagnostic() -> None:
    """Listener resolver should return metadata and emit selected diagnostics."""

    diagnostics: list[ModelLoadSourceMetadataDiagnostic] = []
    resolver = ListenerModelLoadSourceMetadataResolver(
        workflow_payload={
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "_meta": {
                    "substitute": {
                        "cube_alias": "Cube",
                        "node_name": "checkpoint",
                    }
                },
            }
        },
        workflow_id="wf-1",
        prompt_id="pid-1",
        on_diagnostic=diagnostics.append,
    )

    cube_alias, node_name = resolver.resolve("2.dynamic", {"2"})

    assert cube_alias == "Cube"
    assert node_name == "checkpoint"
    assert len(diagnostics) == 1
    assert diagnostics[0].level == "info"
    assert diagnostics[0].message == "Model-load source metadata resolved"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "source_node_id": "2.dynamic",
        "cube_alias": "Cube",
        "node_name": "checkpoint",
    }


def test_listener_model_load_source_metadata_reports_unresolved_metadata() -> None:
    """Listener resolver should emit diagnostics for unresolved metadata."""

    diagnostics: list[ModelLoadSourceMetadataDiagnostic] = []
    resolver = ListenerModelLoadSourceMetadataResolver(
        workflow_payload={"2": {"class_type": "CheckpointLoaderSimple"}},
        workflow_id="wf-1",
        prompt_id="pid-1",
        on_diagnostic=diagnostics.append,
    )

    cube_alias, node_name = resolver.resolve("2", {"2"})

    assert cube_alias is None
    assert node_name is None
    assert len(diagnostics) == 1
    assert diagnostics[0].message == "Model-load source node has no structured metadata"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "source_node_id": "2",
    }
