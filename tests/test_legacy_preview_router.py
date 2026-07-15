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

"""Tests for legacy metadata-less Comfy preview routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.legacy_preview_router import LegacyPreviewRouter

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "legacy_preview_router.py"
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


def _context() -> BinaryEventContext:
    """Return the canonical binary diagnostic context used by these tests."""

    return BinaryEventContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def test_legacy_preview_router_imports_no_ui_or_listener_boundaries() -> None:
    """Legacy preview routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_legacy_preview_router_reports_metadata_less_preview_once() -> None:
    """Metadata-less preview frames should emit one warning per router instance."""

    diagnostics: list[BinaryEventDiagnostic] = []
    router = LegacyPreviewRouter()

    router.route_preview_image(
        b"first-preview",
        binary_event_type=1,
        binary_context=_context(),
        on_binary_diagnostic=diagnostics.append,
    )
    router.route_preview_image(
        b"second-preview",
        binary_event_type=1,
        binary_context=_context(),
        on_binary_diagnostic=diagnostics.append,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].level == "warning"
    assert diagnostics[0].message == "Ignoring metadata-less Comfy preview frame"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "binary_event_type": 1,
        "payload_length": len(b"first-preview"),
        "reason": "missing_preview_metadata",
    }
