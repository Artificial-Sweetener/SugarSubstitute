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

"""Tests for listener-scoped visual event identity guarding."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)

_GUARD_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_visual_event_guard.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _visual_identity(**overrides: str) -> SubstituteVisualIdentity:
    """Return a valid visual identity with selected field overrides."""

    return SubstituteVisualIdentity(
        workflow_id=overrides.get("workflow_id", "wf-1"),
        generation_run_id=overrides.get("generation_run_id", "run-1"),
        client_id=overrides.get("client_id", "client-1"),
        source_key=overrides.get("source_key", "wf-1:source"),
        source_label=overrides.get("source_label", "Source"),
    )


def _guard(
    diagnostics: list[VisualEventRejectionDiagnostic],
) -> ListenerVisualEventGuard:
    """Return a listener visual guard for tests."""

    return ListenerVisualEventGuard(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        on_diagnostic=diagnostics.append,
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


def test_listener_visual_event_guard_imports_no_ui_or_listener_boundaries() -> None:
    """Listener visual guard must stay independent of UI and listener code."""

    source = _GUARD_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_listener_visual_event_guard_builds_context_and_request_identity() -> None:
    """Visual guard should expose listener run identity and event context."""

    guard = _guard([])

    context = guard.context(
        event_type="preview",
        node_id="node-1",
        display_node_id="display-1",
    )
    request_identity = guard.request_identity()

    assert context.workflow_id == "wf-1"
    assert context.generation_run_id == "run-1"
    assert context.prompt_id == "pid-1"
    assert context.client_id == "client-1"
    assert context.event_type == "preview"
    assert context.node_id == "node-1"
    assert context.display_node_id == "display-1"
    assert request_identity.workflow_id == "wf-1"
    assert request_identity.generation_run_id == "run-1"
    assert request_identity.prompt_id == "pid-1"
    assert request_identity.client_id == "client-1"


def test_listener_visual_event_guard_accepts_matching_identity() -> None:
    """Matching visual identities should pass without diagnostics."""

    diagnostics: list[VisualEventRejectionDiagnostic] = []

    accepted = _guard(diagnostics).accepts(
        _visual_identity(),
        prompt_id="pid-1",
        event_type="final_output",
        node_id="node-1",
    )

    assert accepted is True
    assert diagnostics == []


def test_listener_visual_event_guard_emits_rejection_diagnostic() -> None:
    """Rejected visual identities should emit a prompt-safe diagnostic."""

    diagnostics: list[VisualEventRejectionDiagnostic] = []

    accepted = _guard(diagnostics).accepts(
        _visual_identity(client_id="other-client"),
        prompt_id="pid-1",
        event_type="final_output",
        node_id="node-1",
        display_node_id="display-1",
    )

    assert accepted is False
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring visual event for different client"
    assert diagnostic.fields["workflow_id"] == "wf-1"
    assert diagnostic.fields["expected_client_id"] == "client-1"
    assert diagnostic.fields["event_client_id"] == "other-client"
    assert diagnostic.fields["event_type"] == "final_output"
    assert diagnostic.fields["reason"] == "client_mismatch"
