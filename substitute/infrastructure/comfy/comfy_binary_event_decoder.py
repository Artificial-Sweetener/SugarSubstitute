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

"""Decode Comfy websocket binary frame payloads without UI dependencies."""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from substitute.infrastructure.comfy.cube_output_event import (
    SubstituteVisualIdentity,
    parse_substitute_visual_identity,
)

COMFY_BINARY_PREVIEW_IMAGE = 1
COMFY_BINARY_UNENCODED_PREVIEW_IMAGE = 2
COMFY_BINARY_TEXT = 3
COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA = 4
BINARY_HEADER_SIZE = 4
ComfyBinaryEventKind = Literal[
    "preview_image",
    "metadata_preview_image",
    "text",
    "unencoded_preview_image",
    "unknown",
]


@dataclass(frozen=True)
class BinaryPreviewMetadata:
    """Describe optional metadata attached to one Comfy preview frame."""

    node_id: str | None = None
    display_node_id: str | None = None
    parent_node_id: str | None = None
    real_node_id: str | None = None
    prompt_id: str | None = None
    substitute: SubstituteVisualIdentity | None = None


@dataclass(frozen=True)
class ComfyBinaryTextEvent:
    """Describe a decoded Comfy binary text event."""

    node_id: str
    text: str


@dataclass(frozen=True)
class ComfyBinaryFrame:
    """Describe a decoded Comfy binary frame header and payload."""

    event_type: int
    payload: bytes


@dataclass(frozen=True)
class ComfyBinaryEvent:
    """Describe a classified Comfy binary websocket event."""

    kind: ComfyBinaryEventKind
    event_type: int
    payload: bytes


@dataclass(frozen=True)
class BinaryEventDispatchCallbacks:
    """Collect callbacks for top-level Comfy binary event dispatch."""

    on_non_bytes_payload: Callable[[str | None], None]
    on_short_frame: Callable[[int | None], None]
    on_preview_image: Callable[[bytes, int], None]
    on_metadata_preview_image: Callable[[bytes, int], None]
    on_text: Callable[[bytes], None]
    on_unencoded_preview_image: Callable[[int, int], None]
    on_unknown: Callable[[int, int], None]


@dataclass(frozen=True)
class MetadataPreviewPayload:
    """Describe a metadata-bearing preview payload split into parts."""

    metadata_payload: bytes
    image_payload: bytes
    metadata_length: int


@dataclass(frozen=True)
class BinaryFrameDecodeError(ValueError):
    """Report invalid websocket frame shape before event-type dispatch."""

    reason: str
    payload_type: str | None = None
    payload_length: int | None = None


class BinaryPreviewMetadataDecodeError(ValueError):
    """Report malformed preview metadata that should be logged and ignored."""


@dataclass(frozen=True)
class MetadataPreviewPayloadDecodeError(ValueError):
    """Report malformed metadata-preview payload framing."""

    reason: str
    payload_length: int
    metadata_length: int | None = None


@dataclass(frozen=True)
class BinaryTextDecodeError(ValueError):
    """Report malformed binary text payloads with diagnostic context."""

    reason: str
    payload_length: int
    node_id_length: int | None = None


def unpack_u32(payload: bytes) -> int:
    """Return one unsigned 32-bit big-endian integer from exactly four bytes."""

    return int(struct.unpack(">I", payload)[0])


def decode_binary_websocket_frame(event_payload: object) -> ComfyBinaryFrame:
    """Decode a raw websocket payload into a Comfy binary frame."""

    if not isinstance(event_payload, (bytes, bytearray)):
        raise BinaryFrameDecodeError(
            reason="non_bytes_payload",
            payload_type=type(event_payload).__name__,
        )
    raw_payload = bytes(event_payload)
    if len(raw_payload) < BINARY_HEADER_SIZE:
        raise BinaryFrameDecodeError(
            reason="short_frame",
            payload_length=len(raw_payload),
        )
    return ComfyBinaryFrame(
        event_type=unpack_u32(raw_payload[:BINARY_HEADER_SIZE]),
        payload=raw_payload[BINARY_HEADER_SIZE:],
    )


def decode_binary_websocket_event(event_payload: object) -> ComfyBinaryEvent:
    """Decode and classify a raw Comfy binary websocket payload."""

    frame = decode_binary_websocket_frame(event_payload)
    return classify_binary_frame(frame)


def classify_binary_frame(frame: ComfyBinaryFrame) -> ComfyBinaryEvent:
    """Classify a decoded Comfy binary frame by event type."""

    if frame.event_type == COMFY_BINARY_PREVIEW_IMAGE:
        kind: ComfyBinaryEventKind = "preview_image"
    elif frame.event_type == COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA:
        kind = "metadata_preview_image"
    elif frame.event_type == COMFY_BINARY_TEXT:
        kind = "text"
    elif frame.event_type == COMFY_BINARY_UNENCODED_PREVIEW_IMAGE:
        kind = "unencoded_preview_image"
    else:
        kind = "unknown"
    return ComfyBinaryEvent(
        kind=kind,
        event_type=frame.event_type,
        payload=frame.payload,
    )


def dispatch_binary_websocket_event(
    event_payload: object,
    callbacks: BinaryEventDispatchCallbacks,
) -> None:
    """Route one raw Comfy binary websocket payload to semantic callbacks."""

    try:
        event = decode_binary_websocket_event(event_payload)
    except BinaryFrameDecodeError as error:
        if error.reason == "non_bytes_payload":
            callbacks.on_non_bytes_payload(error.payload_type)
            return
        callbacks.on_short_frame(error.payload_length)
        return

    if event.kind == "preview_image":
        callbacks.on_preview_image(event.payload, event.event_type)
        return
    if event.kind == "metadata_preview_image":
        callbacks.on_metadata_preview_image(event.payload, event.event_type)
        return
    if event.kind == "text":
        callbacks.on_text(event.payload)
        return
    if event.kind == "unencoded_preview_image":
        callbacks.on_unencoded_preview_image(event.event_type, len(event.payload))
        return
    callbacks.on_unknown(event.event_type, len(event.payload))


def decode_preview_metadata(payload: bytes) -> BinaryPreviewMetadata:
    """Decode Comfy preview metadata JSON into normalized optional fields."""

    if not payload:
        return BinaryPreviewMetadata()
    try:
        metadata = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BinaryPreviewMetadataDecodeError(str(error)) from error
    if not isinstance(metadata, dict):
        return BinaryPreviewMetadata()
    return BinaryPreviewMetadata(
        node_id=_string_or_none(metadata.get("node_id")),
        display_node_id=_string_or_none(metadata.get("display_node_id")),
        parent_node_id=_string_or_none(metadata.get("parent_node_id")),
        real_node_id=_string_or_none(metadata.get("real_node_id")),
        prompt_id=_string_or_none(metadata.get("prompt_id")),
        substitute=parse_substitute_visual_identity(metadata.get("substitute")),
    )


def decode_metadata_preview_payload(payload: bytes) -> MetadataPreviewPayload:
    """Split a metadata-bearing preview payload into metadata and image bytes."""

    if len(payload) < BINARY_HEADER_SIZE:
        raise MetadataPreviewPayloadDecodeError(
            reason="short_frame",
            payload_length=len(payload),
        )
    metadata_length = unpack_u32(payload[:BINARY_HEADER_SIZE])
    metadata_start = BINARY_HEADER_SIZE
    image_start = metadata_start + metadata_length
    if image_start > len(payload):
        raise MetadataPreviewPayloadDecodeError(
            reason="malformed_frame",
            payload_length=len(payload),
            metadata_length=metadata_length,
        )
    return MetadataPreviewPayload(
        metadata_payload=payload[metadata_start:image_start],
        image_payload=payload[image_start:],
        metadata_length=metadata_length,
    )


def decode_binary_text_event(payload: bytes) -> ComfyBinaryTextEvent:
    """Decode Comfy TEXT binary payload into node id and text."""

    if len(payload) < BINARY_HEADER_SIZE:
        raise BinaryTextDecodeError(
            reason="short_frame",
            payload_length=len(payload),
        )
    node_id_length = unpack_u32(payload[:BINARY_HEADER_SIZE])
    node_id_start = BINARY_HEADER_SIZE
    text_start = node_id_start + node_id_length
    if text_start > len(payload):
        raise BinaryTextDecodeError(
            reason="malformed_frame",
            payload_length=len(payload),
            node_id_length=node_id_length,
        )
    node_id = payload[node_id_start:text_start].decode("utf-8", errors="replace")
    text = payload[text_start:].decode("utf-8", errors="replace")
    return ComfyBinaryTextEvent(node_id=node_id, text=text)


def _string_or_none(value: object) -> str | None:
    """Return a stripped string value when present."""

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


__all__ = [
    "BINARY_HEADER_SIZE",
    "COMFY_BINARY_PREVIEW_IMAGE",
    "COMFY_BINARY_PREVIEW_IMAGE_WITH_METADATA",
    "COMFY_BINARY_TEXT",
    "COMFY_BINARY_UNENCODED_PREVIEW_IMAGE",
    "BinaryEventDispatchCallbacks",
    "ComfyBinaryEvent",
    "ComfyBinaryEventKind",
    "BinaryFrameDecodeError",
    "BinaryPreviewMetadata",
    "BinaryPreviewMetadataDecodeError",
    "BinaryTextDecodeError",
    "ComfyBinaryFrame",
    "ComfyBinaryTextEvent",
    "MetadataPreviewPayload",
    "MetadataPreviewPayloadDecodeError",
    "classify_binary_frame",
    "decode_binary_websocket_event",
    "decode_binary_websocket_frame",
    "decode_binary_text_event",
    "decode_metadata_preview_payload",
    "decode_preview_metadata",
    "dispatch_binary_websocket_event",
    "unpack_u32",
]
