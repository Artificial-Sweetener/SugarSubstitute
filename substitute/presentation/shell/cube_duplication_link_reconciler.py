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

"""Resolve cube-duplication link providers only when duplication runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast

from substitute.application.workflows import (
    NodeLinkEndpointIndex,
    PromptEndpointIndex,
    WorkflowLinkReconciliationService,
)
from substitute.domain.workflow import CubeState


class CubeLinkEndpointProviderProtocol(Protocol):
    """Describe combined prompt and node-link endpoint discovery."""

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Build prompt endpoints for a workflow stack."""

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Build whole-node endpoints for a workflow stack."""


class DeferredCubeDuplicationLinkReconciler:
    """Build link reconciliation from the live shell provider on first use."""

    def __init__(self, view: object) -> None:
        """Store the shell view that owns the node-behavior provider."""

        self._view = view

    def reconcile_transition(
        self,
        *,
        previous_cube_states: dict[str, CubeState],
        previous_stack_order: list[str],
        current_cube_states: dict[str, CubeState],
        current_stack_order: list[str],
    ) -> None:
        """Resolve providers and reconcile one duplication transition."""

        self._service().reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=current_cube_states,
            current_stack_order=current_stack_order,
        )

    def sanitize_current_state(
        self,
        *,
        cube_states: dict[str, CubeState],
        stack_order: list[str],
    ) -> None:
        """Resolve providers and normalize current duplicate link state."""

        self._service().sanitize_current_state(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def _service(self) -> WorkflowLinkReconciliationService:
        """Return a reconciler backed by the shell's authoritative provider."""

        provider = getattr(self._view, "node_behavior_service", None)
        if provider is None:
            raise RuntimeError(
                "node_behavior_service is required to duplicate a cube safely"
            )
        endpoint_provider = cast(CubeLinkEndpointProviderProtocol, provider)
        return WorkflowLinkReconciliationService(
            prompt_endpoint_provider=endpoint_provider,
            node_link_endpoint_provider=endpoint_provider,
        )


__all__ = ["DeferredCubeDuplicationLinkReconciler"]
