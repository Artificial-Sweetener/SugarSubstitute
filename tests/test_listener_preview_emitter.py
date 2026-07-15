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

"""Tests for listener-scoped preview emission wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports.comfy_gateway import PreviewImageUpdate
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.listener_preview_emitter import (
    ListenerPreviewEmitter,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.preview_emission import PreviewEmissionRequest
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)

_EMITTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_preview_emitter.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _visual_identity() -> SubstituteVisualIdentity:
    """Return a valid Substitute visual identity for preview emission."""

    return SubstituteVisualIdentity(
        workflow_id="wf-1",
        generation_run_id="run-1",
        client_id="client-1",
        source_key="wf-1:source",
        source_label="Source",
    )


def _visual_guard(
    visual_diagnostics: list[VisualEventRejectionDiagnostic],
) -> ListenerVisualEventGuard:
    """Return a listener visual guard for preview emitter tests."""

    return ListenerVisualEventGuard(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        on_diagnostic=visual_diagnostics.append,
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


def test_listener_preview_emitter_imports_no_ui_or_listener_boundaries() -> None:
    """Preview emission wiring must stay independent of UI and listener code."""

    source = _EMITTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_listener_preview_emitter_dispatches_preview_update() -> None:
    """Listener preview emitter should supply binary, visual, and callback ports."""

    decoded_image = object()
    preview_events: list[PreviewImageUpdate] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []

    def decode_preview_image(image_bytes: bytes) -> object:
        assert image_bytes == b"preview-bytes"
        return decoded_image

    emitter = ListenerPreviewEmitter(
        binary_context=BinaryEventContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
        visual_event_guard=_visual_guard(visual_diagnostics),
        decode_preview_image=decode_preview_image,
        on_preview=preview_events.append,
        on_binary_diagnostic=binary_diagnostics.append,
        on_visual_diagnostic=visual_diagnostics.append,
    )

    emitter.emit(
        PreviewEmissionRequest(
            image_bytes=b"preview-bytes",
            prompt_id="pid-1",
            binary_event_type=1,
            node_id="node-1",
            visual_identity=_visual_identity(),
        )
    )

    assert binary_diagnostics == []
    assert visual_diagnostics == []
    assert len(preview_events) == 1
    assert preview_events[0].image is decoded_image
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].generation_run_id == "run-1"
    assert preview_events[0].prompt_id == "pid-1"
    assert preview_events[0].client_id == "client-1"
    assert preview_events[0].node_id == "node-1"


def test_listener_preview_emitter_reports_missing_identity_with_visual_context() -> (
    None
):
    """Missing preview identity should use listener visual context for diagnostics."""

    preview_events: list[PreviewImageUpdate] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []

    emitter = ListenerPreviewEmitter(
        binary_context=BinaryEventContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
        visual_event_guard=_visual_guard(visual_diagnostics),
        decode_preview_image=lambda _image_bytes: object(),
        on_preview=preview_events.append,
        on_binary_diagnostic=binary_diagnostics.append,
        on_visual_diagnostic=visual_diagnostics.append,
    )

    emitter.emit(
        PreviewEmissionRequest(
            image_bytes=b"preview-bytes",
            prompt_id="pid-1",
            binary_event_type=1,
            node_id="node-1",
        )
    )

    assert preview_events == []
    assert binary_diagnostics == []
    assert len(visual_diagnostics) == 1
    assert visual_diagnostics[0].fields["workflow_id"] == "wf-1"
    assert visual_diagnostics[0].fields["generation_run_id"] == "run-1"
    assert visual_diagnostics[0].fields["prompt_id"] == "pid-1"
    assert visual_diagnostics[0].fields["node_id"] == "node-1"
    assert visual_diagnostics[0].fields["reason"] == "missing_substitute_identity"
