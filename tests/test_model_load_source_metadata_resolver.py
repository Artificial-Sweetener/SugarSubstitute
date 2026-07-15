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

"""Tests for model-load source metadata resolution."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.model_load_source_metadata_resolver import (
    resolve_model_load_source_metadata,
)

_RESOLVER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "model_load_source_metadata_resolver.py"
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


def test_model_load_source_metadata_resolver_imports_no_ui_or_listener_boundaries() -> (
    None
):
    """Source metadata resolution must stay independent of UI and listener code."""

    source = _RESOLVER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_resolve_model_load_source_metadata_returns_substitute_metadata() -> None:
    """Structured Substitute metadata should resolve to editor source identity."""

    resolution = resolve_model_load_source_metadata(
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
        source_node_id="2.dynamic",
        all_node_ids={"2"},
    )

    assert resolution.cube_alias == "Cube"
    assert resolution.workflow_node_name == "checkpoint"
    assert resolution.diagnostic.level == "info"
    assert resolution.diagnostic.message == "Model-load source metadata resolved"
    assert resolution.diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "source_node_id": "2.dynamic",
        "cube_alias": "Cube",
        "node_name": "checkpoint",
    }


@pytest.mark.parametrize(
    ("workflow_payload", "all_node_ids", "expected_message"),
    [
        (
            {"2": {"_meta": {"substitute": {"cube_alias": "Cube"}}}},
            {"3"},
            "Model-load source node was not found in queued workflow",
        ),
        (
            {"2": "malformed"},
            {"2"},
            "Model-load source node metadata was unavailable",
        ),
        (
            {"2": {"class_type": "CheckpointLoaderSimple"}},
            {"2"},
            "Model-load source node has no structured metadata",
        ),
        (
            {"2": {"_meta": {}}},
            {"2"},
            "Model-load source node has no Substitute metadata",
        ),
        (
            {"2": {"_meta": {"substitute": {"cube_alias": "Cube"}}}},
            {"2"},
            "Model-load source node Substitute metadata was incomplete",
        ),
    ],
)
def test_resolve_model_load_source_metadata_reports_unresolved_metadata(
    workflow_payload: dict[str, object],
    all_node_ids: set[str],
    expected_message: str,
) -> None:
    """Unresolvable source metadata should return the current diagnostic message."""

    resolution = resolve_model_load_source_metadata(
        workflow_payload=workflow_payload,
        workflow_id="wf-1",
        prompt_id="pid-1",
        source_node_id="2",
        all_node_ids=all_node_ids,
    )

    assert resolution.cube_alias is None
    assert resolution.workflow_node_name is None
    assert resolution.diagnostic.level == "info"
    assert resolution.diagnostic.message == expected_message
    assert resolution.diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "source_node_id": "2",
    }
