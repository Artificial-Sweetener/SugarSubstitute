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

"""Project prompt-field overlays onto detached direct Comfy generation plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuilder,
    DirectWorkflowGenerationPlan,
    DirectWorkflowState,
)

from .prompt_field_overlay import DirectWorkflowPromptFieldOverlayService


@dataclass(frozen=True, slots=True)
class DirectWorkflowPromptView:
    """Expose one direct document through shared prompt-analysis protocols."""

    document: DirectWorkflowState

    @property
    def stack_order(self) -> tuple[str, ...]:
        """Return the single direct-workflow prompt section."""

        return (DIRECT_WORKFLOW_SECTION_KEY,)

    @property
    def cubes(self) -> Mapping[str, DirectWorkflowState]:
        """Map the shared section identity to the direct document."""

        return {DIRECT_WORKFLOW_SECTION_KEY: self.document}

    @property
    def global_overrides(self) -> Mapping[str, object]:
        """Return empty legacy override storage for wildcard seed selection."""

        return {}


class DirectWorkflowPromptProjector:
    """Lower scene-specific prompt overlays through normal Comfy graph semantics."""

    def __init__(
        self,
        *,
        overlay_service: DirectWorkflowPromptFieldOverlayService | None = None,
        graph_builder: ComfyApiGraphBuilder | None = None,
    ) -> None:
        """Store the focused overlay and graph-lowering collaborators."""

        self._overlay_service = (
            overlay_service or DirectWorkflowPromptFieldOverlayService()
        )
        self._graph_builder = graph_builder or ComfyApiGraphBuilder()

    def project(
        self,
        document: DirectWorkflowState,
        plan: DirectWorkflowGenerationPlan,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], str],
    ) -> DirectWorkflowGenerationPlan:
        """Return a detached plan lowered from scene-specific authoring state."""

        buffer = self._overlay_service.apply(
            document,
            prompt_field_overrides=prompt_field_overrides,
        )
        graph = self._graph_builder.build(buffer)
        return DirectWorkflowGenerationPlan(
            authored_api_graph=graph,
            output_manifest=plan.output_manifest,
        )


__all__ = ["DirectWorkflowPromptProjector", "DirectWorkflowPromptView"]
