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

"""Materialize graph-backed Cube edits without discarding ordinary Comfy regions."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from substitute.domain.common import GlobalOverrideScope, JsonObject
from substitute.domain.workflow import WorkflowState
from substitute.application.workflows.composed_value_annotation_service import (
    ComposedValueAnnotationService,
)

from .cube_convenience_materializer import CubeConvenienceMaterializer


class GraphBackedCubeWorkflowBuilder:
    """Build an execution copy from the Comfy graph that owns Cube topology."""

    def __init__(
        self,
        materializer: CubeConvenienceMaterializer | None = None,
    ) -> None:
        """Capture the shared Substitute-convenience materializer."""

        self._materializer = materializer or CubeConvenienceMaterializer()
        self._composition_annotations = ComposedValueAnnotationService()

    def build(
        self,
        workflow: WorkflowState,
        *,
        global_override_scopes: Mapping[str, GlobalOverrideScope] | None = None,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
    ) -> JsonObject:
        """Return the authoritative graph with detached edited Cube documents."""

        direct = workflow.direct_workflow
        if direct is None or not workflow.is_graph_backed_cube_workflow:
            raise ValueError("Workflow is not backed by a canonical Cube graph.")
        if not any(not cube.bypassed for cube in workflow.cubes.values()):
            raise ValueError(
                "Cannot generate because the workflow has no active cubes."
            )
        graph = deepcopy(direct.source_workflow)
        buffers = self._materializer.materialize_buffers(
            workflow,
            prompt_field_overrides=prompt_field_overrides,
        )
        nodes = graph.get("nodes")
        definitions = graph.get("definitions")
        subgraphs = (
            definitions.get("subgraphs") if isinstance(definitions, dict) else None
        )
        if not isinstance(nodes, list) or not isinstance(subgraphs, list):
            raise ValueError("Canonical Cube graph is missing nodes or definitions.")
        nodes_by_id = {
            str(node.get("id")): node for node in nodes if isinstance(node, dict)
        }
        definitions_by_id = {
            definition.get("id"): definition
            for definition in subgraphs
            if isinstance(definition, dict)
        }
        for alias in workflow.stack_order:
            cube = workflow.cubes[alias]
            ui = cube.ui
            node_id = ui.get("graph_node_id") if isinstance(ui, dict) else None
            node = nodes_by_id.get(str(node_id))
            if not isinstance(node, dict):
                raise ValueError(f"Cube {alias!r} has no owning Comfy graph node.")
            definition = definitions_by_id.get(node.get("type"))
            extra = definition.get("extra") if isinstance(definition, dict) else None
            if not isinstance(extra, dict):
                raise ValueError(f"Cube {alias!r} has no canonical graph definition.")
            node["mode"] = 4 if cube.bypassed else 0
            extra["sugarcubes_document"] = self._materializer.cube_document(
                cube,
                buffers[alias],
            )
        self._composition_annotations.annotate(
            graph,
            global_override_scopes=global_override_scopes,
        )
        return graph


__all__ = ["GraphBackedCubeWorkflowBuilder"]
