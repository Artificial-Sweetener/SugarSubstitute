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

"""Tests for top-level Comfy binary event diagnostic routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.binary_event_diagnostic_router import (
    BinaryEventDiagnosticRouter,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "binary_event_diagnostic_router.py"
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


def _router(diagnostics: list[BinaryEventDiagnostic]) -> BinaryEventDiagnosticRouter:
    """Return a router that records emitted diagnostics."""

    return BinaryEventDiagnosticRouter(
        binary_context=_context(),
        on_binary_diagnostic=diagnostics.append,
    )


def test_binary_event_diagnostic_router_imports_no_ui_or_listener_boundaries() -> None:
    """Top-level binary diagnostics must stay independent of UI/listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_non_bytes_payload_emits_payload_type_diagnostic() -> None:
    """Non-bytes payload routing should preserve payload type context."""

    diagnostics: list[BinaryEventDiagnostic] = []

    _router(diagnostics).route_non_bytes_payload("str")

    assert len(diagnostics) == 1
    assert diagnostics[0].message == "Ignoring non-bytes websocket payload"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_type": "str",
    }


def test_route_short_frame_emits_payload_length_diagnostic() -> None:
    """Short frame routing should preserve payload length context."""

    diagnostics: list[BinaryEventDiagnostic] = []

    _router(diagnostics).route_short_frame(3)

    assert len(diagnostics) == 1
    assert diagnostics[0].message == "Ignoring short Comfy binary websocket frame"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_length": 3,
    }


def test_route_unencoded_preview_event_emits_event_context_diagnostic() -> None:
    """Unencoded preview routing should preserve event type and payload length."""

    diagnostics: list[BinaryEventDiagnostic] = []

    _router(diagnostics).route_unencoded_preview_event(2, 128)

    assert len(diagnostics) == 1
    assert (
        diagnostics[0].message
        == "Ignoring unsupported Comfy unencoded preview binary event"
    )
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "binary_event_type": 2,
        "payload_length": 128,
    }


def test_route_unknown_event_emits_event_context_diagnostic() -> None:
    """Unknown event routing should preserve event type and payload length."""

    diagnostics: list[BinaryEventDiagnostic] = []

    _router(diagnostics).route_unknown_event(99, 64)

    assert len(diagnostics) == 1
    assert diagnostics[0].message == "Ignoring unknown Comfy binary websocket event"
    assert diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "binary_event_type": 99,
        "payload_length": 64,
    }
