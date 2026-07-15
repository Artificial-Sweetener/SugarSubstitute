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

"""Tests for listener binary websocket runtime assembly."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.listener_binary_event_runtime import (
    build_listener_binary_event_runtime,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)

_RUNTIME_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_binary_event_runtime.py"
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


def test_listener_binary_event_runtime_imports_no_ui_or_listener_boundaries() -> None:
    """Binary runtime assembly must stay independent of UI and listener code."""

    source = _RUNTIME_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_listener_binary_event_runtime_routes_diagnostics_with_context() -> None:
    """Binary runtime should wire listener identity into binary diagnostics."""

    binary_diagnostics: list[BinaryEventDiagnostic] = []
    runtime = build_listener_binary_event_runtime(
        request=_request(),
        callbacks=_callbacks(),
        visual_event_guard=_visual_event_guard(),
        decode_preview_image=lambda _image_bytes: object(),
        on_binary_diagnostic=binary_diagnostics.append,
        on_visual_diagnostic=lambda _diagnostic: None,
    )

    runtime.binary_event_router.route_event("not-bytes", all_node_ids=set())

    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].message == "Ignoring non-bytes websocket payload"
    assert binary_diagnostics[0].fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_type": "str",
    }


def _request() -> ListenerStartRequest:
    """Build a listener start request for binary-runtime tests."""

    return ListenerStartRequest(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client-1",
        listener_session=ListenerSessionHandle(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
            session=object(),
        ),
        output_dir=Path("out"),
        workflow_payload={"1": {"class_type": "KSampler"}},
        sugar_script="line one",
        workflow_id="wf-1",
        workflow_name="Workflow",
    )


def _callbacks() -> ListenerCallbacks:
    """Build callbacks required by binary-runtime construction."""

    return ListenerCallbacks(
        on_progress=lambda _event: None,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )


def _visual_event_guard() -> ListenerVisualEventGuard:
    """Build a visual event guard for binary-runtime construction."""

    return ListenerVisualEventGuard(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        on_diagnostic=lambda _diagnostic: None,
    )
