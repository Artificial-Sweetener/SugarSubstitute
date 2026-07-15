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

"""Import guardrails for the pure shared canvas session module."""

from __future__ import annotations

import ast
from pathlib import Path


_SESSION_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "domain"
    / "workflow"
    / "canvas_session.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qpane",
    "qfluentwidgets",
    "substitute.application.ports.comfy_gateway",
    "substitute.infrastructure.comfy",
    "substitute.presentation.canvas",
    "substitute.presentation.editor",
)

_FORBIDDEN_SOURCE_TOKENS = (
    "QPane",
    "QImage",
    "QPixmap",
    "setCurrentImageID",
    "addImage",
    "removeImageByID",
    "setLinkedGroups",
    "loadMaskFromFile",
    "OutputVisualIdentity",
    "LiveFinalOutputEvent",
    "PreviewImageUpdate",
    "OutputImageUpdate",
    "materialize_input_image",
    "graph_material",
    "decode",
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


def test_canvas_session_module_imports_no_forbidden_boundaries() -> None:
    """Shared session identity must stay independent of UI and backend adapters."""

    source = _SESSION_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_canvas_session_module_references_no_forbidden_adapter_tokens() -> None:
    """Shared session identity must not absorb widget, DTO, graph, or decode policy."""

    source = _SESSION_MODULE.read_text(encoding="utf-8")

    forbidden_tokens = {token for token in _FORBIDDEN_SOURCE_TOKENS if token in source}

    assert forbidden_tokens == set()
