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


@dataclass(frozen=True, slots=True)
class RecoveryOutputIdentity:
    """Bind one execution-only recovery node to its authored source socket."""

    recovery_node_id: str
    source_socket: ComfyOutputSocket
    source_key: str
    source_label: str
    order: int


@dataclass(frozen=True, slots=True)
class DirectWorkflowExecutionProjection:
    """Carry one instrumented prompt and its explicit output targets."""

    prompt: JsonObject
    execution_targets: tuple[str, ...]
    recovery_outputs: tuple[RecoveryOutputIdentity, ...]


class DirectWorkflowExecutionProjector:
    """Inject standard temporary image recovery nodes without mutating a plan."""

    def project(
        self,
        plan: DirectWorkflowGenerationPlan,
    ) -> DirectWorkflowExecutionProjection:
        """Return a detached recovery prompt with deterministic target identity."""

        prompt = deepcopy(plan.authored_api_graph)
        occupied_ids = {str(node_id) for node_id in prompt}
        recoveries: list[RecoveryOutputIdentity] = []
        for source in plan.output_manifest.sources:
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
            recoveries.append(
                RecoveryOutputIdentity(
                    recovery_node_id=recovery_node_id,
                    source_socket=source.socket,
                    source_key=source.source_key,
                    source_label=source.label,
                    order=source.order,
                )
            )
        return DirectWorkflowExecutionProjection(
            prompt=prompt,
            execution_targets=(
                *plan.output_manifest.preserved_output_node_ids,
                *(recovery.recovery_node_id for recovery in recoveries),
            ),
            recovery_outputs=tuple(recoveries),
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
    "RecoveryOutputIdentity",
]
