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

"""Tests for Comfy binary websocket event routing orchestration."""

from __future__ import annotations

import ast
import json
import struct
from pathlib import Path

from substitute.infrastructure.comfy.binary_websocket_event_router import (
    BinaryWebsocketEventRouter,
    BinaryWebsocketRoutingCallbacks,
    BinaryWebsocketRoutingContext,
)
from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    COMFY_BINARY_PREVIEW_IMAGE,
    COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA,
    COMFY_BINARY_TEXT,
    COMFY_BINARY_UNENCODED_PREVIEW_IMAGE,
)
from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventContext,
    BinaryEventDiagnostic,
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
    / "binary_websocket_event_router.py"
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


def _frame(event_type: int, payload: bytes) -> bytes:
    """Return a full Comfy binary websocket frame."""

    return struct.pack(">I", event_type) + payload


def _metadata_preview_payload(metadata: dict[str, object], image: bytes) -> bytes:
    """Return a metadata-preview event payload without the outer event header."""

    metadata_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")
    return struct.pack(">I", len(metadata_bytes)) + metadata_bytes + image


def _text_payload(node_id: str, text: str) -> bytes:
    """Return a text event payload without the outer event header."""

    node_id_bytes = node_id.encode("utf-8")
    return struct.pack(">I", len(node_id_bytes)) + node_id_bytes + text.encode("utf-8")


def _context() -> BinaryWebsocketRoutingContext:
    """Return the canonical router context used by these tests."""

    return BinaryWebsocketRoutingContext(
        active_prompt_id="pid-1",
        binary_context=BinaryEventContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
        visual_context=VisualEventContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            event_type="preview",
        ),
        request_identity=VisualEventRequestIdentity(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
        ),
    )


def _router(
    preview_requests: list[PreviewEmissionRequest],
    binary_diagnostics: list[BinaryEventDiagnostic],
    visual_diagnostics: list[VisualEventRejectionDiagnostic],
) -> BinaryWebsocketEventRouter:
    """Return a binary websocket router that records all side effects."""

    return BinaryWebsocketEventRouter(
        context=_context(),
        callbacks=BinaryWebsocketRoutingCallbacks(
            on_emit_preview=preview_requests.append,
            on_binary_diagnostic=binary_diagnostics.append,
            on_visual_diagnostic=visual_diagnostics.append,
        ),
    )


def _route(
    event_payload: object,
    *,
    all_node_ids: set[str] | None = None,
) -> tuple[
    list[PreviewEmissionRequest],
    list[BinaryEventDiagnostic],
    list[VisualEventRejectionDiagnostic],
]:
    """Route one event payload and return captured side effects."""

    preview_requests: list[PreviewEmissionRequest] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []
    _router(
        preview_requests,
        binary_diagnostics,
        visual_diagnostics,
    ).route_event(event_payload, all_node_ids=all_node_ids or {"node-1"})
    return preview_requests, binary_diagnostics, visual_diagnostics


def test_binary_websocket_event_router_imports_no_ui_or_listener_boundaries() -> None:
    """Binary websocket routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_event_reports_top_level_frame_diagnostics() -> None:
    """Raw frame errors should route through the diagnostic router."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route("not-bytes")

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].message == "Ignoring non-bytes websocket payload"
    assert binary_diagnostics[0].fields["payload_type"] == "str"


def test_route_event_drops_legacy_preview_with_one_warning() -> None:
    """Legacy preview frames should warn once and never emit previews."""

    preview_requests: list[PreviewEmissionRequest] = []
    binary_diagnostics: list[BinaryEventDiagnostic] = []
    visual_diagnostics: list[VisualEventRejectionDiagnostic] = []
    router = _router(preview_requests, binary_diagnostics, visual_diagnostics)

    router.route_event(
        _frame(COMFY_BINARY_PREVIEW_IMAGE, b"legacy-1"),
        all_node_ids={"node-1"},
    )
    router.route_event(
        _frame(COMFY_BINARY_PREVIEW_IMAGE, b"legacy-2"),
        all_node_ids={"node-1"},
    )

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].fields["reason"] == "missing_preview_metadata"
    assert binary_diagnostics[0].fields["payload_length"] == len(b"legacy-1")


def test_route_event_emits_metadata_preview_request() -> None:
    """Metadata-bearing preview frames should produce one preview emission request."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _frame(
            COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA,
            _metadata_preview_payload(
                {
                    "node_id": "node-1",
                    "prompt_id": "pid-1",
                    "substitute": {
                        "schemaVersion": 1,
                        "workflowId": "wf-1",
                        "generationRunId": "run-1",
                        "clientId": "client-1",
                        "sourceKey": "wf-1:node-1",
                        "sourceLabel": "Node",
                    },
                },
                b"image-bytes",
            ),
        )
    )

    assert binary_diagnostics == []
    assert visual_diagnostics == []
    assert len(preview_requests) == 1
    assert preview_requests[0].image_bytes == b"image-bytes"
    assert preview_requests[0].node_id == "node-1"
    assert preview_requests[0].visual_identity is not None
    assert preview_requests[0].visual_identity.source_label == "Node"


def test_route_event_routes_binary_text_diagnostic() -> None:
    """Binary text frames should route through the text event owner."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _frame(COMFY_BINARY_TEXT, _text_payload("node-1", "hello"))
    )

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert binary_diagnostics[0].message == "Received Comfy binary text event"
    assert binary_diagnostics[0].fields["node_id"] == "node-1"
    assert binary_diagnostics[0].fields["text_preview"] == "hello"


def test_route_event_reports_unencoded_preview_diagnostic() -> None:
    """Unsupported unencoded preview frames should emit the existing diagnostic."""

    preview_requests, binary_diagnostics, visual_diagnostics = _route(
        _frame(COMFY_BINARY_UNENCODED_PREVIEW_IMAGE, b"raw")
    )

    assert preview_requests == []
    assert visual_diagnostics == []
    assert len(binary_diagnostics) == 1
    assert (
        binary_diagnostics[0].message
        == "Ignoring unsupported Comfy unencoded preview binary event"
    )
    assert binary_diagnostics[0].fields["payload_length"] == 3
