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

"""Validate Substitute visual event identity without listener side effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity

VisualEventLogLevel = Literal["debug", "warning"]

VisualEventRejectionReason = Literal[
    "missing_substitute_identity",
    "prompt_mismatch",
    "client_mismatch",
    "workflow_mismatch",
    "generation_run_mismatch",
    "unknown_source",
]


@dataclass(frozen=True)
class VisualEventContext:
    """Describe listener context attached to rejected visual event diagnostics."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    event_type: str
    node_id: str | None = None
    display_node_id: str | None = None


@dataclass(frozen=True)
class VisualEventRejectionDiagnostic:
    """Describe how a rejected visual event should be logged."""

    level: VisualEventLogLevel
    message: str
    fields: dict[str, object]


@dataclass(frozen=True)
class VisualEventRequestIdentity:
    """Describe the listener run identity expected for visual events."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str


def substitute_visual_identity_rejection_reason(
    identity: SubstituteVisualIdentity | None,
    request: VisualEventRequestIdentity,
    *,
    prompt_id: str | None,
) -> VisualEventRejectionReason | None:
    """Return why a Substitute visual event does not belong to a listener run."""

    if identity is None:
        return "missing_substitute_identity"
    if prompt_id != request.prompt_id:
        return "prompt_mismatch"
    if identity.client_id != request.client_id:
        return "client_mismatch"
    if identity.workflow_id != request.workflow_id:
        return "workflow_mismatch"
    if identity.generation_run_id != request.generation_run_id:
        return "generation_run_mismatch"
    if not identity.source_key or not identity.source_label:
        return "unknown_source"
    return None


def visual_event_rejection_diagnostic(
    reason: VisualEventRejectionReason,
    identity: SubstituteVisualIdentity | None,
    context: VisualEventContext,
    *,
    event_prompt_id: str | None,
) -> VisualEventRejectionDiagnostic:
    """Return the structured diagnostic for a rejected visual event."""

    if reason == "missing_substitute_identity":
        return VisualEventRejectionDiagnostic(
            level="warning",
            message="Ignoring visual event without Substitute identity",
            fields={
                "workflow_id": context.workflow_id,
                "generation_run_id": context.generation_run_id,
                "prompt_id": context.prompt_id,
                "node_id": context.node_id,
                "display_node_id": context.display_node_id,
                "event_type": context.event_type,
                "reason": reason,
            },
        )

    if reason == "prompt_mismatch":
        return VisualEventRejectionDiagnostic(
            level="debug",
            message="Ignoring visual event for different prompt",
            fields={
                "workflow_id": context.workflow_id,
                "generation_run_id": context.generation_run_id,
                "expected_prompt_id": context.prompt_id,
                "event_prompt_id": event_prompt_id,
                "event_type": context.event_type,
                "reason": reason,
            },
        )

    if identity is None:
        return VisualEventRejectionDiagnostic(
            level="warning",
            message="Ignoring visual event without Substitute identity",
            fields={
                "workflow_id": context.workflow_id,
                "generation_run_id": context.generation_run_id,
                "prompt_id": context.prompt_id,
                "node_id": context.node_id,
                "display_node_id": context.display_node_id,
                "event_type": context.event_type,
                "reason": "missing_substitute_identity",
            },
        )

    if reason == "client_mismatch":
        return VisualEventRejectionDiagnostic(
            level="warning",
            message="Ignoring visual event for different client",
            fields={
                "workflow_id": context.workflow_id,
                "generation_run_id": context.generation_run_id,
                "prompt_id": context.prompt_id,
                "expected_client_id": context.client_id,
                "event_client_id": identity.client_id,
                "event_type": context.event_type,
                "reason": reason,
            },
        )

    if reason == "workflow_mismatch":
        return VisualEventRejectionDiagnostic(
            level="warning",
            message="Ignoring visual event for different workflow",
            fields={
                "workflow_id": context.workflow_id,
                "event_workflow_id": identity.workflow_id,
                "generation_run_id": context.generation_run_id,
                "prompt_id": context.prompt_id,
                "event_type": context.event_type,
                "reason": reason,
            },
        )

    if reason == "generation_run_mismatch":
        return VisualEventRejectionDiagnostic(
            level="debug",
            message="Ignoring visual event for stale generation run",
            fields={
                "workflow_id": context.workflow_id,
                "expected_generation_run_id": context.generation_run_id,
                "event_generation_run_id": identity.generation_run_id,
                "prompt_id": context.prompt_id,
                "event_type": context.event_type,
                "reason": reason,
            },
        )

    return VisualEventRejectionDiagnostic(
        level="warning",
        message="Ignoring visual event without source identity",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "prompt_id": context.prompt_id,
            "node_id": context.node_id,
            "event_type": context.event_type,
            "reason": reason,
        },
    )


def visual_preview_missing_identity_diagnostic(
    context: VisualEventContext,
) -> VisualEventRejectionDiagnostic:
    """Return the diagnostic for a preview emission without visual identity."""

    return VisualEventRejectionDiagnostic(
        level="debug",
        message="Ignoring Comfy preview without Substitute visual identity",
        fields={
            "workflow_id": context.workflow_id,
            "generation_run_id": context.generation_run_id,
            "prompt_id": context.prompt_id,
            "node_id": context.node_id,
            "reason": "missing_substitute_identity",
        },
    )


__all__ = [
    "VisualEventContext",
    "VisualEventLogLevel",
    "VisualEventRejectionDiagnostic",
    "VisualEventRejectionReason",
    "VisualEventRequestIdentity",
    "substitute_visual_identity_rejection_reason",
    "visual_event_rejection_diagnostic",
    "visual_preview_missing_identity_diagnostic",
]
