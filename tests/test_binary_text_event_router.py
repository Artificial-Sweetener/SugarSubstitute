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

"""Tests for Comfy binary text event routing."""

from __future__ import annotations

import ast
import struct
from pathlib import Path

from substitute.infrastructure.comfy.binary_text_event_router import (
    route_binary_text_event,
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
    / "binary_text_event_router.py"
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


def _payload(node_id: str, text: str) -> bytes:
    """Return a binary text payload for tests."""

    node_id_bytes = node_id.encode("utf-8")
    text_bytes = text.encode("utf-8")
    return struct.pack(">I", len(node_id_bytes)) + node_id_bytes + text_bytes


def _route(payload: bytes) -> list[BinaryEventDiagnostic]:
    """Route one payload and return emitted diagnostics."""

    diagnostics: list[BinaryEventDiagnostic] = []
    route_binary_text_event(
        payload,
        binary_context=_context(),
        on_binary_diagnostic=diagnostics.append,
    )
    return diagnostics


def test_binary_text_event_router_imports_no_ui_or_listener_boundaries() -> None:
    """Binary text routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_binary_text_event_reports_decoded_text_event() -> None:
    """Decoded text events should emit the existing informational diagnostic."""

    diagnostics = _route(_payload("node-1", "hello"))

    assert len(diagnostics) == 1
    assert diagnostics[0].level == "info"
    assert diagnostics[0].message == "Received Comfy binary text event"
    assert diagnostics[0].fields["workflow_id"] == "wf-1"
    assert diagnostics[0].fields["prompt_id"] == "pid-1"
    assert diagnostics[0].fields["node_id"] == "node-1"
    assert diagnostics[0].fields["text_length"] == len("hello")
    assert diagnostics[0].fields["text_preview"] == "hello"


def test_route_binary_text_event_reports_short_frame() -> None:
    """Short text frames should emit the existing short-frame diagnostic."""

    diagnostics = _route(b"\x00\x01")

    assert len(diagnostics) == 1
    assert diagnostics[0].level == "warning"
    assert diagnostics[0].message == "Ignoring short Comfy binary text frame"
    assert diagnostics[0].fields["payload_length"] == 2


def test_route_binary_text_event_reports_malformed_frame() -> None:
    """Malformed text frames should preserve payload and node-id length context."""

    diagnostics = _route(struct.pack(">I", 10) + b"node")

    assert len(diagnostics) == 1
    assert diagnostics[0].level == "warning"
    assert diagnostics[0].message == "Ignoring malformed Comfy binary text frame"
    assert diagnostics[0].fields["node_id_length"] == 10
    assert diagnostics[0].fields["payload_length"] == 8
