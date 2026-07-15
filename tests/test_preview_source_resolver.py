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

"""Tests for Comfy preview metadata source-node resolution."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    BinaryPreviewMetadata,
)
from substitute.infrastructure.comfy.preview_source_resolver import (
    resolve_preview_metadata_node_id,
)

_RESOLVER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "preview_source_resolver.py"
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


def test_preview_source_resolver_imports_no_ui_or_listener_boundaries() -> None:
    """Preview source resolution must stay independent of UI and listener code."""

    source = _RESOLVER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            BinaryPreviewMetadata(
                node_id="node",
                display_node_id="display",
                parent_node_id="parent",
                real_node_id="real",
            ),
            "display",
        ),
        (
            BinaryPreviewMetadata(
                node_id="node",
                display_node_id="missing",
                parent_node_id="parent",
                real_node_id="real",
            ),
            "node",
        ),
        (
            BinaryPreviewMetadata(node_id="missing", parent_node_id="parent"),
            "parent",
        ),
        (
            BinaryPreviewMetadata(node_id="missing", real_node_id="real"),
            "real",
        ),
    ],
)
def test_resolve_preview_metadata_node_id_preserves_backend_field_priority(
    metadata: BinaryPreviewMetadata,
    expected: str,
) -> None:
    """Metadata source resolution should match existing listener field priority."""

    assert (
        resolve_preview_metadata_node_id(
            metadata,
            all_node_ids={"display", "node", "parent", "real"},
        )
        == expected
    )


@pytest.mark.parametrize("node_id", ["owner.1.2", "owner:dynamic"])
def test_resolve_preview_metadata_node_id_uses_dynamic_owner_prefix(
    node_id: str,
) -> None:
    """Dynamic backend preview node ids should resolve to their workflow owner."""

    assert (
        resolve_preview_metadata_node_id(
            BinaryPreviewMetadata(node_id=node_id),
            all_node_ids={"owner"},
        )
        == "owner"
    )


def test_resolve_preview_metadata_node_id_returns_none_for_unknown_source() -> None:
    """Unknown preview metadata nodes should stay unresolved."""

    assert (
        resolve_preview_metadata_node_id(
            BinaryPreviewMetadata(node_id="missing"),
            all_node_ids={"owner"},
        )
        is None
    )
