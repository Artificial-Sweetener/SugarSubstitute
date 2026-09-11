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

"""Build detached execution graphs from graph-backed Cube workflow state."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.common import GlobalOverrideScope, JsonObject
from substitute.domain.workflow import WorkflowState

from .cube_convenience_materializer import (
    CubeConvenienceMaterializer,
)
from .graph_backed_cube_workflow_builder import GraphBackedCubeWorkflowBuilder


class NativeCubeWorkflowBuilder:
    """Materialize Substitute conveniences into a canonical generation-only graph."""

    def __init__(
        self,
        materializer: CubeConvenienceMaterializer | None = None,
        graph_backed_builder: GraphBackedCubeWorkflowBuilder | None = None,
    ) -> None:
        """Capture shared convenience and graph-backed materialization owners."""

        resolved_materializer = materializer or CubeConvenienceMaterializer()
        self._graph_backed_builder = graph_backed_builder or (
            GraphBackedCubeWorkflowBuilder(resolved_materializer)
        )

    def build(
        self,
        workflow: WorkflowState,
        *,
        global_override_scopes: Mapping[str, GlobalOverrideScope] | None = None,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
    ) -> JsonObject:
        """Return a detached copy of the one authoritative native graph."""

        if not isinstance(workflow, WorkflowState) or not (
            workflow.is_graph_backed_cube_workflow
        ):
            raise ValueError(
                "Cube workflow has not been migrated to a canonical Comfy graph."
            )
        return self._graph_backed_builder.build(
            workflow,
            global_override_scopes=global_override_scopes,
            prompt_field_overrides=prompt_field_overrides,
        )


__all__ = ["NativeCubeWorkflowBuilder"]
