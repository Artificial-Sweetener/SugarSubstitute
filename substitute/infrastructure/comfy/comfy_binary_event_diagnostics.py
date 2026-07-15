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

"""Build prompt-safe diagnostics for Comfy binary websocket events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BinaryEventLogLevel = Literal["debug", "info", "warning"]
BINARY_TEXT_PREVIEW_LIMIT = 200


@dataclass(frozen=True)
class BinaryEventContext:
    """Describe listener context shared by binary event diagnostics."""

    workflow_id: str
    prompt_id: str
    generation_run_id: str | None = None


@dataclass(frozen=True)
class BinaryEventDiagnostic:
    """Describe how one binary event diagnostic should be logged."""

    level: BinaryEventLogLevel
    message: str
    fields: dict[str, object]


def non_bytes_binary_payload_diagnostic(
    context: BinaryEventContext,
    *,
    payload_type: str | None,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for a non-bytes payload in the binary path."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring non-bytes websocket payload",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "payload_type": payload_type,
        },
    )


def short_binary_frame_diagnostic(
    context: BinaryEventContext,
    *,
    payload_length: int | None,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for a binary frame shorter than its header."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring short Comfy binary websocket frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "payload_length": payload_length,
        },
    )


def short_binary_text_frame_diagnostic(
    context: BinaryEventContext,
    *,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for a text frame shorter than its length header."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring short Comfy binary text frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "payload_length": payload_length,
        },
    )


def malformed_binary_text_frame_diagnostic(
    context: BinaryEventContext,
    *,
    node_id_length: int | None,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for malformed binary text payload framing."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring malformed Comfy binary text frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "node_id_length": node_id_length,
            "payload_length": payload_length,
        },
    )


def binary_text_event_diagnostic(
    context: BinaryEventContext,
    *,
    node_id: str,
    text: str,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for a decoded Comfy binary text event."""

    text_preview = (
        text
        if len(text) <= BINARY_TEXT_PREVIEW_LIMIT
        else f"{text[:BINARY_TEXT_PREVIEW_LIMIT]}..."
    )
    return BinaryEventDiagnostic(
        level="info",
        message="Received Comfy binary text event",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "node_id": node_id,
            "text_length": len(text),
            "text_preview": text_preview,
        },
    )


def metadata_less_preview_frame_diagnostic(
    context: BinaryEventContext,
    *,
    event_type: int,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for metadata-less preview frames."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring metadata-less Comfy preview frame",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "prompt_id": context.prompt_id,
            "binary_event_type": event_type,
            "payload_length": payload_length,
            "reason": "missing_preview_metadata",
        },
    )


def short_metadata_preview_frame_diagnostic(
    context: BinaryEventContext,
    *,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for a metadata-preview frame shorter than its header."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring short Comfy metadata preview frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "payload_length": payload_length,
        },
    )


def malformed_metadata_preview_frame_diagnostic(
    context: BinaryEventContext,
    *,
    metadata_length: int | None,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for malformed metadata-preview payload framing."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring malformed Comfy metadata preview frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "metadata_length": metadata_length,
            "payload_length": payload_length,
        },
    )


def malformed_preview_metadata_diagnostic(
    context: BinaryEventContext,
    *,
    payload_length: int,
    error: object,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for malformed preview metadata JSON."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring malformed Comfy preview metadata",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "payload_length": payload_length,
            "error": error,
        },
    )


def metadata_preview_missing_prompt_id_diagnostic(
    context: BinaryEventContext,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for metadata previews without a prompt id."""

    return BinaryEventDiagnostic(
        level="debug",
        message="Ignoring Comfy metadata preview without prompt id",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "prompt_id": context.prompt_id,
            "reason": "missing_prompt_id",
        },
    )


def metadata_preview_prompt_mismatch_diagnostic(
    context: BinaryEventContext,
    *,
    event_prompt_id: str,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for metadata previews from a different prompt."""

    return BinaryEventDiagnostic(
        level="debug",
        message="Ignoring Comfy metadata preview for different prompt",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "expected_prompt_id": context.prompt_id,
            "event_prompt_id": event_prompt_id,
            "reason": "prompt_mismatch",
        },
    )


def metadata_preview_missing_source_node_diagnostic(
    context: BinaryEventContext,
    *,
    metadata_node_id: str | None,
    metadata_display_node_id: str | None,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for metadata previews without a resolvable source."""

    return BinaryEventDiagnostic(
        level="debug",
        message="Ignoring Comfy metadata preview without resolvable source node",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "prompt_id": context.prompt_id,
            "metadata_node_id": metadata_node_id,
            "metadata_display_node_id": metadata_display_node_id,
            "reason": "missing_source_node",
        },
    )


def unencoded_binary_preview_event_diagnostic(
    context: BinaryEventContext,
    *,
    event_type: int,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for an unsupported unencoded preview event."""

    return BinaryEventDiagnostic(
        level="info",
        message="Ignoring unsupported Comfy unencoded preview binary event",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "binary_event_type": event_type,
            "payload_length": payload_length,
        },
    )


def undecodable_preview_image_diagnostic(
    context: BinaryEventContext,
    *,
    node_id: str | None,
    image_format: int | None,
    event_type: int,
    payload_length: int,
    error: object,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for preview image bytes that cannot be decoded."""

    return BinaryEventDiagnostic(
        level="warning",
        message="Ignoring undecodable Comfy preview image frame",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "node_id": node_id,
            "image_format": image_format,
            "binary_event_type": event_type,
            "payload_length": payload_length,
            "error": error,
        },
    )


def unknown_binary_event_diagnostic(
    context: BinaryEventContext,
    *,
    event_type: int,
    payload_length: int,
) -> BinaryEventDiagnostic:
    """Return the diagnostic for an unknown Comfy binary event type."""

    return BinaryEventDiagnostic(
        level="info",
        message="Ignoring unknown Comfy binary websocket event",
        fields={
            "workflow_id": context.workflow_id,
            "prompt_id": context.prompt_id,
            "binary_event_type": event_type,
            "payload_length": payload_length,
        },
    )


__all__ = [
    "BINARY_TEXT_PREVIEW_LIMIT",
    "BinaryEventContext",
    "BinaryEventDiagnostic",
    "BinaryEventLogLevel",
    "binary_text_event_diagnostic",
    "malformed_metadata_preview_frame_diagnostic",
    "malformed_binary_text_frame_diagnostic",
    "malformed_preview_metadata_diagnostic",
    "metadata_less_preview_frame_diagnostic",
    "metadata_preview_missing_prompt_id_diagnostic",
    "metadata_preview_missing_source_node_diagnostic",
    "metadata_preview_prompt_mismatch_diagnostic",
    "non_bytes_binary_payload_diagnostic",
    "short_binary_frame_diagnostic",
    "short_binary_text_frame_diagnostic",
    "short_metadata_preview_frame_diagnostic",
    "unencoded_binary_preview_event_diagnostic",
    "undecodable_preview_image_diagnostic",
    "unknown_binary_event_diagnostic",
]
