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

"""Resolve immutable prompt conditioning semantics from workflow topology."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.prompt_editor.conditioning.context")


class PromptConditioningMode(StrEnum):
    """Describe how structural prompt partitions produce conditioning batches."""

    INDEPENDENT = "independent"
    REGIONAL = "regional"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class PromptConditioningContext:
    """Carry graph-derived conditioning semantics for one exact prompt endpoint."""

    mode: PromptConditioningMode
    endpoint: PromptEndpoint
    topology_key: tuple[object, ...] = ()

    @property
    def identity(self) -> tuple[object, ...]:
        """Return a stable identity suitable for asynchronous freshness checks."""

        return (
            self.mode.value,
            self.endpoint.cube_alias,
            self.endpoint.role.value,
            self.endpoint.node_name,
            self.endpoint.field_key,
            *self.topology_key,
        )


class PromptConditioningContextService:
    """Classify one exact prompt endpoint using regional workflow authority."""

    def __init__(
        self,
        regional_topology: RegionalPromptTopologyService | None = None,
    ) -> None:
        """Store the workflow topology collaborator."""

        self._regional_topology = regional_topology or RegionalPromptTopologyService()

    def resolve(
        self,
        workflow: WorkflowState | None,
        endpoint: PromptEndpoint,
    ) -> PromptConditioningContext:
        """Return graph-derived conditioning semantics for one prompt endpoint."""

        if workflow is None:
            context = PromptConditioningContext(
                mode=PromptConditioningMode.UNRESOLVED,
                endpoint=endpoint,
            )
            _log_context_resolution(context, workflow_available=False)
            return context
        topology = self._regional_topology.topology_for_prompt_endpoint(
            workflow,
            endpoint.cube_alias,
            endpoint.node_name,
            endpoint.field_key,
        )
        if topology is None:
            context = PromptConditioningContext(
                mode=PromptConditioningMode.INDEPENDENT,
                endpoint=endpoint,
            )
            _log_context_resolution(context, workflow_available=True)
            return context
        context = PromptConditioningContext(
            mode=PromptConditioningMode.REGIONAL,
            endpoint=endpoint,
            topology_key=(
                *topology.association_key,
                topology.prompt_node_names,
            ),
        )
        _log_context_resolution(context, workflow_available=True)
        return context


def unbound_prompt_conditioning_context() -> PromptConditioningContext:
    """Return an explicit unresolved context for prompt editors without workflow ownership."""

    return PromptConditioningContext(
        mode=PromptConditioningMode.UNRESOLVED,
        endpoint=PromptEndpoint(
            cube_alias="",
            role=PromptRole.POSITIVE,
            node_name="",
            field_key="",
            linkable=False,
        ),
    )


def _log_context_resolution(
    context: PromptConditioningContext,
    *,
    workflow_available: bool,
) -> None:
    """Log one prompt-safe conditioning classification decision."""

    endpoint = context.endpoint
    log_debug(
        _LOGGER,
        "Resolved prompt conditioning context",
        cube_alias=endpoint.cube_alias,
        node_name=endpoint.node_name,
        field_key=endpoint.field_key,
        prompt_role=endpoint.role.value,
        conditioning_mode=context.mode.value,
        workflow_available=workflow_available,
    )


__all__ = [
    "PromptConditioningContext",
    "PromptConditioningContextService",
    "PromptConditioningMode",
    "unbound_prompt_conditioning_context",
]
