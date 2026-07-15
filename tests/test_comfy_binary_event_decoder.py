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

"""Tests for Comfy websocket binary payload decoding."""

from __future__ import annotations

import json
import struct
import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_binary_event_decoder import (
    COMFY_BINARY_PREVIEW_IMAGE,
    COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA,
    COMFY_BINARY_TEXT,
    COMFY_BINARY_UNENCODED_PREVIEW_IMAGE,
    BinaryEventDispatchCallbacks,
    BinaryFrameDecodeError,
    BinaryPreviewMetadataDecodeError,
    BinaryTextDecodeError,
    MetadataPreviewPayloadDecodeError,
    decode_binary_websocket_event,
    decode_binary_websocket_frame,
    decode_binary_text_event,
    decode_metadata_preview_payload,
    decode_preview_metadata,
    dispatch_binary_websocket_event,
    unpack_u32,
)


_DECODER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "comfy_binary_event_decoder.py"
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


def test_decoder_imports_no_ui_or_listener_boundaries() -> None:
    """Binary parsing must remain independent of Qt and listener orchestration."""

    source = _DECODER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_decode_preview_metadata_normalizes_optional_fields() -> None:
    """Metadata decoding should strip empty strings and parse Substitute identity."""

    metadata = decode_preview_metadata(
        json.dumps(
            {
                "node_id": " 12 ",
                "display_node_id": "",
                "parent_node_id": "parent",
                "real_node_id": "real",
                "prompt_id": " pid-1 ",
                "substitute": {
                    "schemaVersion": 1,
                    "workflowId": "wf-1",
                    "generationRunId": "run-1",
                    "clientId": "client-1",
                    "sourceKey": "source-1",
                    "sourceLabel": "Source 1",
                },
            }
        ).encode("utf-8")
    )

    assert metadata.node_id == "12"
    assert metadata.display_node_id is None
    assert metadata.parent_node_id == "parent"
    assert metadata.real_node_id == "real"
    assert metadata.prompt_id == "pid-1"
    assert metadata.substitute is not None
    assert metadata.substitute.workflow_id == "wf-1"
    assert metadata.substitute.generation_run_id == "run-1"


def test_decode_binary_websocket_frame_splits_header_and_payload() -> None:
    """Frame decoding should isolate event type from the binary body."""

    frame = decode_binary_websocket_frame(struct.pack(">I", 4) + b"payload")

    assert frame.event_type == 4
    assert frame.payload == b"payload"


def test_decode_binary_websocket_frame_rejects_non_bytes_payload() -> None:
    """Non-binary websocket payloads should preserve type for listener logging."""

    with pytest.raises(BinaryFrameDecodeError) as error:
        decode_binary_websocket_frame("not-bytes")

    assert error.value.reason == "non_bytes_payload"
    assert error.value.payload_type == "str"
    assert error.value.payload_length is None


def test_decode_binary_websocket_frame_rejects_short_frame() -> None:
    """Short binary frames should preserve payload length for listener logging."""

    with pytest.raises(BinaryFrameDecodeError) as error:
        decode_binary_websocket_frame(b"\x00\x01")

    assert error.value.reason == "short_frame"
    assert error.value.payload_type is None
    assert error.value.payload_length == 2


def test_decode_binary_websocket_event_classifies_known_event_types() -> None:
    """Event decoding should map Comfy binary ids to semantic event kinds."""

    event_types = {
        COMFY_BINARY_PREVIEW_IMAGE: "preview_image",
        COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA: "metadata_preview_image",
        COMFY_BINARY_TEXT: "text",
        COMFY_BINARY_UNENCODED_PREVIEW_IMAGE: "unencoded_preview_image",
    }

    for event_type, expected_kind in event_types.items():
        event = decode_binary_websocket_event(struct.pack(">I", event_type) + b"body")

        assert event.kind == expected_kind
        assert event.event_type == event_type
        assert event.payload == b"body"


def test_decode_binary_websocket_event_classifies_unknown_event_type() -> None:
    """Unknown binary event ids should preserve the id and payload."""

    event = decode_binary_websocket_event(struct.pack(">I", 99) + b"body")

    assert event.kind == "unknown"
    assert event.event_type == 99
    assert event.payload == b"body"


def test_dispatch_binary_websocket_event_routes_known_events() -> None:
    """Top-level binary dispatch should call the semantic event callbacks."""

    calls: list[tuple[str, object, object | None]] = []
    callbacks = BinaryEventDispatchCallbacks(
        on_non_bytes_payload=lambda payload_type: calls.append(
            ("non_bytes", payload_type, None)
        ),
        on_short_frame=lambda payload_length: calls.append(
            ("short", payload_length, None)
        ),
        on_preview_image=lambda payload, event_type: calls.append(
            ("preview", payload, event_type)
        ),
        on_metadata_preview_image=lambda payload, event_type: calls.append(
            ("metadata_preview", payload, event_type)
        ),
        on_text=lambda payload: calls.append(("text", payload, None)),
        on_unencoded_preview_image=lambda event_type, payload_length: calls.append(
            ("unencoded", event_type, payload_length)
        ),
        on_unknown=lambda event_type, payload_length: calls.append(
            ("unknown", event_type, payload_length)
        ),
    )

    dispatch_binary_websocket_event(
        struct.pack(">I", COMFY_BINARY_PREVIEW_IMAGE) + b"legacy",
        callbacks,
    )
    dispatch_binary_websocket_event(
        struct.pack(">I", COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA) + b"metadata",
        callbacks,
    )
    dispatch_binary_websocket_event(
        struct.pack(">I", COMFY_BINARY_TEXT) + b"text",
        callbacks,
    )
    dispatch_binary_websocket_event(
        struct.pack(">I", COMFY_BINARY_UNENCODED_PREVIEW_IMAGE) + b"raw",
        callbacks,
    )
    dispatch_binary_websocket_event(struct.pack(">I", 99) + b"unknown", callbacks)

    assert calls == [
        ("preview", b"legacy", COMFY_BINARY_PREVIEW_IMAGE),
        ("metadata_preview", b"metadata", COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA),
        ("text", b"text", None),
        ("unencoded", COMFY_BINARY_UNENCODED_PREVIEW_IMAGE, 3),
        ("unknown", 99, 7),
    ]


def test_dispatch_binary_websocket_event_routes_frame_errors() -> None:
    """Top-level binary dispatch should route malformed frame diagnostics."""

    calls: list[tuple[str, object | None]] = []
    callbacks = BinaryEventDispatchCallbacks(
        on_non_bytes_payload=lambda payload_type: calls.append(
            ("non_bytes", payload_type)
        ),
        on_short_frame=lambda payload_length: calls.append(("short", payload_length)),
        on_preview_image=lambda _payload, _event_type: None,
        on_metadata_preview_image=lambda _payload, _event_type: None,
        on_text=lambda _payload: None,
        on_unencoded_preview_image=lambda _event_type, _payload_length: None,
        on_unknown=lambda _event_type, _payload_length: None,
    )

    dispatch_binary_websocket_event("not-bytes", callbacks)
    dispatch_binary_websocket_event(b"\x00\x01", callbacks)

    assert calls == [("non_bytes", "str"), ("short", 2)]


def test_decode_preview_metadata_rejects_malformed_json() -> None:
    """Malformed metadata JSON should report a decoding error to the caller."""

    with pytest.raises(BinaryPreviewMetadataDecodeError):
        decode_preview_metadata(b"{")


def test_decode_metadata_preview_payload_splits_metadata_and_image() -> None:
    """Metadata preview splitting should separate JSON bytes from image bytes."""

    metadata = b'{"prompt_id":"pid-1"}'
    image = b"image-bytes"
    payload = struct.pack(">I", len(metadata)) + metadata + image

    split_payload = decode_metadata_preview_payload(payload)

    assert split_payload.metadata_payload == metadata
    assert split_payload.image_payload == image
    assert split_payload.metadata_length == len(metadata)


def test_decode_metadata_preview_payload_reports_short_frame() -> None:
    """Short metadata-preview payloads should report payload length."""

    with pytest.raises(MetadataPreviewPayloadDecodeError) as error:
        decode_metadata_preview_payload(b"\x00")

    assert error.value.reason == "short_frame"
    assert error.value.payload_length == 1
    assert error.value.metadata_length is None


def test_decode_metadata_preview_payload_reports_malformed_length() -> None:
    """Oversized metadata lengths should report requested and actual lengths."""

    with pytest.raises(MetadataPreviewPayloadDecodeError) as error:
        decode_metadata_preview_payload(struct.pack(">I", 20) + b"{}")

    assert error.value.reason == "malformed_frame"
    assert error.value.payload_length == 6
    assert error.value.metadata_length == 20


def test_decode_binary_text_event_splits_node_id_and_text() -> None:
    """Text decoding should read the node-id length prefix as big-endian."""

    payload = struct.pack(">I", 2) + b"26hello"

    event = decode_binary_text_event(payload)

    assert event.node_id == "26"
    assert event.text == "hello"
    assert unpack_u32(payload[:4]) == 2


def test_decode_binary_text_event_reports_short_frame() -> None:
    """Short text frames should expose payload length for listener logging."""

    with pytest.raises(BinaryTextDecodeError) as error:
        decode_binary_text_event(b"\x00")

    assert error.value.reason == "short_frame"
    assert error.value.payload_length == 1
    assert error.value.node_id_length is None


def test_decode_binary_text_event_reports_malformed_node_length() -> None:
    """Oversized node-id lengths should expose node length and payload length."""

    with pytest.raises(BinaryTextDecodeError) as error:
        decode_binary_text_event(struct.pack(">I", 20) + b"26")

    assert error.value.reason == "malformed_frame"
    assert error.value.payload_length == 6
    assert error.value.node_id_length == 20
