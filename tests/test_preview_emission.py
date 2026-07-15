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

"""Tests for Comfy preview callback emission."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports.comfy_gateway import PreviewImageUpdate
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.preview_emission import (
    PreviewEmissionCallbacks,
    PreviewEmissionRequest,
    emit_preview_image,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
)

_EMISSION_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "preview_emission.py"
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


def _binary_context() -> BinaryEventContext:
    """Return the canonical binary diagnostic context used by these tests."""

    return BinaryEventContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def _visual_context() -> VisualEventContext:
    """Return the canonical visual diagnostic context used by these tests."""

    return VisualEventContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        event_type="preview",
        node_id="node-1",
    )


def _visual_identity() -> SubstituteVisualIdentity:
    """Return a valid Substitute visual identity for preview emission."""

    return SubstituteVisualIdentity(
        workflow_id="wf-1",
        generation_run_id="run-1",
        client_id="client-1",
        source_key="wf-1:source",
        source_label="Source",
        scene_run_id="scene-run-1",
        scene_key="scene",
        scene_title="Scene",
        scene_order=2,
        scene_count=4,
    )


def _callbacks(
    *,
    decoded_image: object | None = None,
    decode_error: Exception | None = None,
    preview_events: list[PreviewImageUpdate],
    binary_diagnostics: list[BinaryEventDiagnostic],
    visual_diagnostics: list[VisualEventRejectionDiagnostic],
) -> PreviewEmissionCallbacks:
    """Return preview emission callbacks that record all side effects."""

    def decode_preview_image(image_bytes: bytes) -> object:
        assert image_bytes == b"preview-bytes"
        if decode_error is not None:
            raise decode_error
        assert decoded_image is not None
        return decoded_image

    return PreviewEmissionCallbacks(
        decode_preview_image=decode_preview_image,
        on_preview=preview_events.append,
        on_binary_diagnostic=binary_diagnostics.append,
        on_visual_diagnostic=visual_diagnostics.append,
    )


def test_preview_emission_imports_no_ui_or_listener_boundaries() -> None:
    """Preview emission orchestration must stay independent of UI and listener code."""

    source = _EMISSION_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_emit_preview_image_decodes_and_dispatches_preview_update() -> None:
    """Valid preview image bytes should produce one application preview callback."""

    decoded_image = object()
    preview_events: list[PreviewImageUpdate] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []

    emit_preview_image(
        PreviewEmissionRequest(
            image_bytes=b"preview-bytes",
            prompt_id="pid-1",
            binary_event_type=1,
            node_id="node-1",
            metadata_node_id="metadata-node",
            display_node_id="display-node",
            parent_node_id="parent-node",
            real_node_id="real-node",
            visual_identity=_visual_identity(),
        ),
        binary_context=_binary_context(),
        visual_context=_visual_context(),
        callbacks=_callbacks(
            decoded_image=decoded_image,
            preview_events=preview_events,
            binary_diagnostics=binary_diagnostics,
            visual_diagnostics=visual_diagnostics,
        ),
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
    assert preview_events[0].metadata_node_id == "metadata-node"
    assert preview_events[0].display_node_id == "display-node"
    assert preview_events[0].parent_node_id == "parent-node"
    assert preview_events[0].real_node_id == "real-node"
    assert preview_events[0].source_key == "wf-1:source"
    assert preview_events[0].source_label == "Source"
    assert preview_events[0].scene_run_id == "scene-run-1"


def test_emit_preview_image_reports_missing_visual_identity_without_decoding() -> None:
    """Missing Substitute visual identity should emit only the visual diagnostic."""

    preview_events: list[PreviewImageUpdate] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []

    emit_preview_image(
        PreviewEmissionRequest(
            image_bytes=b"preview-bytes",
            prompt_id="pid-1",
            binary_event_type=1,
            node_id="node-1",
        ),
        binary_context=_binary_context(),
        visual_context=_visual_context(),
        callbacks=_callbacks(
            preview_events=preview_events,
            binary_diagnostics=binary_diagnostics,
            visual_diagnostics=visual_diagnostics,
        ),
    )

    assert preview_events == []
    assert binary_diagnostics == []
    assert len(visual_diagnostics) == 1
    assert visual_diagnostics[0].level == "debug"
    assert visual_diagnostics[0].fields["reason"] == "missing_substitute_identity"
    assert visual_diagnostics[0].fields["node_id"] == "node-1"


def test_emit_preview_image_reports_decode_failure_without_dispatching() -> None:
    """Undecodable preview bytes should emit the binary diagnostic only."""

    preview_events: list[PreviewImageUpdate] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []
    decode_error = ValueError("bad preview")

    emit_preview_image(
        PreviewEmissionRequest(
            image_bytes=b"preview-bytes",
            prompt_id="pid-1",
            binary_event_type=99,
            node_id="node-1",
            visual_identity=_visual_identity(),
            image_format=2,
        ),
        binary_context=_binary_context(),
        visual_context=_visual_context(),
        callbacks=_callbacks(
            decode_error=decode_error,
            preview_events=preview_events,
            binary_diagnostics=binary_diagnostics,
            visual_diagnostics=visual_diagnostics,
        ),
    )

    assert preview_events == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].level == "warning"
    assert binary_diagnostics[0].fields["node_id"] == "node-1"
    assert binary_diagnostics[0].fields["image_format"] == 2
    assert binary_diagnostics[0].fields["binary_event_type"] == 99
    assert binary_diagnostics[0].fields["payload_length"] == len(b"preview-bytes")
    assert binary_diagnostics[0].fields["error"] is decode_error
