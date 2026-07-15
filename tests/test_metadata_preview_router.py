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

"""Tests for metadata-bearing Comfy preview routing."""

from __future__ import annotations

import ast
import json
import struct
from pathlib import Path

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.metadata_preview_router import (
    MetadataPreviewRoutingCallbacks,
    MetadataPreviewRoutingRequest,
    route_metadata_preview_image,
)
from substitute.infrastructure.comfy.preview_emission import PreviewEmissionRequest
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionDiagnostic,
    VisualEventRequestIdentity,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "metadata_preview_router.py"
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


def _payload(metadata: dict[str, object] | bytes, image: bytes = b"image") -> bytes:
    """Return a binary metadata-preview payload for tests."""

    metadata_payload = (
        metadata
        if isinstance(metadata, bytes)
        else json.dumps(metadata, sort_keys=True).encode("utf-8")
    )
    return struct.pack(">I", len(metadata_payload)) + metadata_payload + image


def _substitute_identity(**overrides: object) -> dict[str, object]:
    """Return a valid Substitute visual identity payload with selected overrides."""

    identity: dict[str, object] = {
        "schemaVersion": 1,
        "workflowId": "wf-1",
        "generationRunId": "run-1",
        "clientId": "client-1",
        "sourceKey": "wf-1:node-1",
        "sourceLabel": "Source",
    }
    identity.update(overrides)
    return identity


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
    )


def _request_identity() -> VisualEventRequestIdentity:
    """Return the listener request identity used by these tests."""

    return VisualEventRequestIdentity(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )


def _callbacks(
    preview_requests: list[PreviewEmissionRequest],
    binary_diagnostics: list[BinaryEventDiagnostic],
    visual_diagnostics: list[VisualEventRejectionDiagnostic],
) -> MetadataPreviewRoutingCallbacks:
    """Return routing callbacks that record all side effects."""

    return MetadataPreviewRoutingCallbacks(
        on_emit_preview=preview_requests.append,
        on_binary_diagnostic=binary_diagnostics.append,
        on_visual_diagnostic=visual_diagnostics.append,
    )


def _route(
    payload: bytes,
    *,
    all_node_ids: set[str] | None = None,
) -> tuple[
    list[PreviewEmissionRequest],
    list[BinaryEventDiagnostic],
    list[VisualEventRejectionDiagnostic],
]:
    """Route one payload and return captured side effects."""

    preview_requests: list[PreviewEmissionRequest] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []

    route_metadata_preview_image(
        MetadataPreviewRoutingRequest(
            payload=payload,
            binary_event_type=4,
            active_prompt_id="pid-1",
            all_node_ids=all_node_ids or {"node-1"},
        ),
        binary_context=_binary_context(),
        visual_context=_visual_context(),
        request_identity=_request_identity(),
        callbacks=_callbacks(
            preview_requests,
            binary_diagnostics,
            visual_diagnostics,
        ),
    )

    return preview_requests, binary_diagnostics, visual_diagnostics


def test_metadata_preview_router_imports_no_ui_or_listener_boundaries() -> None:
    """Metadata preview routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_metadata_preview_image_emits_preview_request() -> None:
    """Valid metadata previews should route one preview emission request."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _payload(
            {
                "node_id": "node-1",
                "display_node_id": "display-1",
                "parent_node_id": "parent-1",
                "real_node_id": "real-1",
                "prompt_id": "pid-1",
                "substitute": _substitute_identity(),
            },
            image=b"image-bytes",
        )
    )

    assert binary_diagnostics == []
    assert visual_diagnostics == []
    assert len(preview_requests) == 1
    assert preview_requests[0].image_bytes == b"image-bytes"
    assert preview_requests[0].prompt_id == "pid-1"
    assert preview_requests[0].binary_event_type == 4
    assert preview_requests[0].node_id == "node-1"
    assert preview_requests[0].metadata_node_id == "node-1"
    assert preview_requests[0].display_node_id == "display-1"
    assert preview_requests[0].parent_node_id == "parent-1"
    assert preview_requests[0].real_node_id == "real-1"
    assert preview_requests[0].visual_identity is not None
    assert preview_requests[0].visual_identity.source_key == "wf-1:node-1"
    assert preview_requests[0].image_format is None


def test_route_metadata_preview_image_reports_short_frame() -> None:
    """Short metadata-preview frames should report the binary framing diagnostic."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(b"\x00\x01")

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert (
        binary_diagnostics[0].message == "Ignoring short Comfy metadata preview frame"
    )
    assert binary_diagnostics[0].fields["payload_length"] == 2


def test_route_metadata_preview_image_reports_malformed_metadata_then_missing_prompt() -> (
    None
):
    """Malformed metadata JSON should preserve the listener's fallback diagnostics."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(_payload(b"{"))

    assert preview_requests == []
    assert visual_diagnostics == []
    assert [diagnostic.message for diagnostic in binary_diagnostics] == [
        "Ignoring malformed Comfy preview metadata",
        "Ignoring Comfy metadata preview without prompt id",
    ]


def test_route_metadata_preview_image_reports_prompt_mismatch() -> None:
    """Metadata for a different prompt should fail before identity validation."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _payload(
            {
                "node_id": "node-1",
                "prompt_id": "other-prompt",
                "substitute": _substitute_identity(),
            }
        )
    )

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].fields["event_prompt_id"] == "other-prompt"
    assert binary_diagnostics[0].fields["reason"] == "prompt_mismatch"


def test_route_metadata_preview_image_reports_visual_identity_rejection() -> None:
    """Stale or mismatched visual identity should emit a visual diagnostic."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _payload(
            {
                "node_id": "node-1",
                "display_node_id": "display-1",
                "prompt_id": "pid-1",
                "substitute": _substitute_identity(clientId="other-client"),
            }
        )
    )

    assert preview_requests == []
    assert binary_diagnostics == []
    assert len(visual_diagnostics) == 1
    assert visual_diagnostics[0].fields["expected_client_id"] == "client-1"
    assert visual_diagnostics[0].fields["event_client_id"] == "other-client"
    assert visual_diagnostics[0].fields["reason"] == "client_mismatch"


def test_route_metadata_preview_image_reports_missing_source_node() -> None:
    """Metadata without a resolvable source node should fail closed."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _payload(
            {
                "node_id": "missing-node",
                "display_node_id": "missing-display",
                "prompt_id": "pid-1",
                "substitute": _substitute_identity(),
            }
        ),
        all_node_ids={"node-1"},
    )

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].fields["reason"] == "missing_source_node"
    assert binary_diagnostics[0].fields["metadata_node_id"] == "missing-node"
    assert binary_diagnostics[0].fields["metadata_display_node_id"] == "missing-display"
