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

"""Compose the portable-model save and generation service slice."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.generation.graph_backed_cube_workflow_builder import (
    GraphBackedCubeWorkflowBuilder,
)
from substitute.application.generation.native_cube_workflow_builder import (
    NativeCubeWorkflowBuilder,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.ports.recipe_repository import WorkflowRepository
from substitute.application.ports.workflow_payload_compiler import (
    WorkflowPayloadCompiler,
)
from substitute.application.recipes.model_hash_lookup import RecipeModelHashLookup
from substitute.application.recipes.workflow_export_service import (
    WorkflowExportService,
)
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)


@dataclass(frozen=True, slots=True)
class PortableModelServices:
    """Carry one shared manifest owner and its configured consumers."""

    manifest: PortableModelManifestService
    workflow_builder: NativeCubeWorkflowBuilder
    workflow_export: WorkflowExportService


def build_portable_model_services(
    *,
    model_hash_lookup: RecipeModelHashLookup,
    workflow_repository: WorkflowRepository,
    workflow_payload_compiler: WorkflowPayloadCompiler,
    node_definition_gateway: NodeDefinitionGateway,
) -> PortableModelServices:
    """Build save and generation services around one manifest authority."""

    manifest = PortableModelManifestService(model_hash_lookup)
    return PortableModelServices(
        manifest=manifest,
        workflow_builder=NativeCubeWorkflowBuilder(
            graph_backed_builder=GraphBackedCubeWorkflowBuilder(
                model_manifest_annotator=manifest,
            )
        ),
        workflow_export=WorkflowExportService(
            workflow_repository=workflow_repository,
            workflow_payload_compiler=workflow_payload_compiler,
            node_definition_gateway=node_definition_gateway,
            model_manifest_annotator=manifest,
        ),
    )


__all__ = ["PortableModelServices", "build_portable_model_services"]
