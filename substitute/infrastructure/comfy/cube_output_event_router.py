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

"""Validate Substitute cube-output events before artifact persistence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from substitute.infrastructure.comfy.cube_output_event import (
    CubeOutputEvent,
    SubstituteVisualIdentity,
    parse_cube_output_event,
)
from substitute.infrastructure.comfy.comfy_payload_fields import (
    list_index_rejection_reason,
)

CubeOutputDiagnosticLevel = Literal["debug", "info", "warning"]


@dataclass(frozen=True)
class CubeOutputRouteContext:
    """Describe listener context required for cube-output validation diagnostics."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str


@dataclass(frozen=True)
class CubeOutputSourceIdentity:
    """Describe final-output source identity carried by a cube-output event."""

    node_id: str
    source_key: str
    source_label: str
    cube_alias: str


@dataclass(frozen=True)
class CubeOutputDiagnostic:
    """Describe one prompt-safe cube-output routing diagnostic."""

    level: CubeOutputDiagnosticLevel
    message: str
    fields: Mapping[str, object]


@dataclass(frozen=True)
class CubeOutputRouteResult:
    """Describe the validated cube-output event selected for persistence."""

    cube_output: CubeOutputEvent | None = None
    source_identity: CubeOutputSourceIdentity | None = None
    diagnostic: CubeOutputDiagnostic | None = None


def route_cube_output_event(
    data: Mapping[str, object],
    *,
    context: CubeOutputRouteContext,
    identity_acceptor: Callable[
        [SubstituteVisualIdentity | None, str | None, str | None], bool
    ],
) -> CubeOutputRouteResult:
    """Validate one cube-output payload before artifact fetch and persistence."""

    cube_output = parse_cube_output_event(data)
    if cube_output is None:
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="warning",
                message="Ignoring malformed cube-output websocket event",
                fields=_context_fields(context),
            )
        )

    if cube_output.prompt_id is None:
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="warning",
                message="Ignoring cube-output event without prompt id",
                fields={
                    **_context_fields(context),
                    "node_id": cube_output.node_id,
                    "reason": "missing_prompt_id",
                },
            )
        )

    if cube_output.prompt_id != context.prompt_id:
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="debug",
                message="Ignoring cube-output event for different prompt",
                fields={
                    "workflow_id": context.workflow_id,
                    "generation_run_id": context.generation_run_id,
                    "expected_prompt_id": context.prompt_id,
                    "event_prompt_id": cube_output.prompt_id,
                    "node_id": cube_output.node_id,
                    "reason": "prompt_mismatch",
                },
            )
        )

    if not identity_acceptor(
        cube_output.substitute,
        cube_output.prompt_id,
        cube_output.node_id,
    ):
        return CubeOutputRouteResult()

    if cube_output.media_kind != "image":
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="info",
                message="Ignoring unsupported cube-output media kind",
                fields={
                    **_context_fields(context),
                    "media_kind": cube_output.media_kind,
                    "node_id": cube_output.node_id,
                },
            )
        )

    if cube_output.node_id is None:
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="warning",
                message="Ignoring cube-output event without node id",
                fields={
                    **_context_fields(context),
                    "cube_id": cube_output.cube_id,
                },
            )
        )

    visual_identity = cube_output.substitute
    if visual_identity is None:
        return CubeOutputRouteResult()

    list_index_rejection = list_index_rejection_reason(data.get("list_index"))
    if list_index_rejection is not None:
        return CubeOutputRouteResult(
            diagnostic=CubeOutputDiagnostic(
                level="warning",
                message="Ignoring cube-output event without usable list index",
                fields={
                    **_context_fields(context),
                    "client_id": visual_identity.client_id,
                    "node_id": cube_output.node_id,
                    "source_key": visual_identity.source_key,
                    "reason": list_index_rejection,
                },
            )
        )

    return CubeOutputRouteResult(
        cube_output=cube_output,
        source_identity=CubeOutputSourceIdentity(
            node_id=cube_output.node_id,
            source_key=visual_identity.source_key,
            source_label=visual_identity.source_label,
            cube_alias=visual_identity.source_label,
        ),
    )


def _context_fields(context: CubeOutputRouteContext) -> dict[str, object]:
    """Return common structured diagnostic fields."""

    return {
        "workflow_id": context.workflow_id,
        "generation_run_id": context.generation_run_id,
        "prompt_id": context.prompt_id,
    }


__all__ = [
    "CubeOutputDiagnostic",
    "CubeOutputDiagnosticLevel",
    "CubeOutputRouteContext",
    "CubeOutputRouteResult",
    "CubeOutputSourceIdentity",
    "route_cube_output_event",
]
