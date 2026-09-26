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

"""Project immutable direct-workflow plans into instrumented Comfy prompts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from substitute.domain.comfy_workflow.output_manifest import (
    ComfyOutputSocket,
    DirectWorkflowGenerationPlan,
)
from substitute.domain.common import JsonObject
from substitute.domain.output_media import OutputMediaKind


@dataclass(frozen=True, slots=True)
class ProjectedOutputIdentity:
    """Bind one executable output node to its authored visual source."""

    node_id: str
    source_socket: ComfyOutputSocket
    source_key: str
    source_label: str
    order: int
    media_kind: OutputMediaKind


@dataclass(frozen=True, slots=True)
class DirectWorkflowExecutionProjection:
    """Carry one instrumented prompt and its explicit output targets."""

    prompt: JsonObject
    execution_targets: tuple[str, ...]
    output_sources: tuple[ProjectedOutputIdentity, ...]


class DirectWorkflowExecutionProjector:
    """Project typed visual sources without mutating the authored plan."""

    def project(
        self,
        plan: DirectWorkflowGenerationPlan,
    ) -> DirectWorkflowExecutionProjection:
        """Return a detached recovery prompt with deterministic target identity."""

        prompt = deepcopy(plan.authored_api_graph)
        occupied_ids = {str(node_id) for node_id in prompt}
        output_sources: list[ProjectedOutputIdentity] = []
        for source in plan.output_manifest.sources:
            if not source.requires_image_recovery:
                output_sources.append(
                    ProjectedOutputIdentity(
                        node_id=source.output_node_id,
                        source_socket=source.socket,
                        source_key=source.source_key,
                        source_label=source.label,
                        order=source.order,
                        media_kind=source.media_kind,
                    )
                )
                continue
            recovery_node_id = _allocate_recovery_node_id(
                order=source.order,
                occupied_ids=occupied_ids,
            )
            occupied_ids.add(recovery_node_id)
            prompt[recovery_node_id] = {
                "class_type": "PreviewImage",
                "inputs": {
                    "images": [
                        source.socket.node_id,
                        source.socket.output_index,
                    ]
                },
                "_meta": {"title": source.label},
            }
            output_sources.append(
                ProjectedOutputIdentity(
                    node_id=recovery_node_id,
                    source_socket=source.socket,
                    source_key=source.source_key,
                    source_label=source.label,
                    order=source.order,
                    media_kind=source.media_kind,
                )
            )
        return DirectWorkflowExecutionProjection(
            prompt=prompt,
            execution_targets=(
                *plan.output_manifest.preserved_output_node_ids,
                *(
                    source.node_id
                    for source in output_sources
                    if source.media_kind is OutputMediaKind.IMAGE
                ),
            ),
            output_sources=tuple(output_sources),
        )


def _allocate_recovery_node_id(
    *,
    order: int,
    occupied_ids: set[str],
) -> str:
    """Return a deterministic recovery node ID that cannot replace authored data."""

    base = f"__substitute_image_output_{order + 1}"
    candidate = base
    suffix = 2
    while candidate in occupied_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


__all__ = [
    "DirectWorkflowExecutionProjection",
    "DirectWorkflowExecutionProjector",
    "ProjectedOutputIdentity",
]
