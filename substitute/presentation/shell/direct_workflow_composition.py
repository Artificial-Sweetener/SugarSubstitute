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

"""Compose portable model recovery for direct canonical workflow loads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from substitute.application.direct_workflows import (
    DirectWorkflowLoadService,
    PortableWorkflowModelResolutionService,
)
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol

from .direct_workflow_file_actions import DirectWorkflowFileActions
from .direct_workflow_model_resolution import (
    DirectWorkflowModelResolutionController,
)
from .workspace_controller_composition import (
    model_download_route,
    model_resolution_route,
)


@dataclass(frozen=True, slots=True)
class DirectWorkflowComposition:
    """Carry direct-workflow application and presentation collaborators."""

    load_service: DirectWorkflowLoadService
    file_actions: DirectWorkflowFileActions


def compose_direct_workflow_file_actions(
    shell: Any,
    *,
    manifest: PortableModelManifestService,
    add_workflow_tab: Callable[[], object],
    workflow_workspace: Any,
    error_presenter: ErrorReportPresenterProtocol,
) -> DirectWorkflowComposition:
    """Compose canonical loading, model recovery, and shell materialization."""

    load_service = DirectWorkflowLoadService(
        ComfyWorkflowDocumentRepository(),
        shell.cube_graph_gateway,
        node_definition_gateway=shell.node_definition_gateway,
    )
    return DirectWorkflowComposition(
        load_service=load_service,
        file_actions=DirectWorkflowFileActions(
            view=shell,
            load_service=load_service,
            add_workflow_tab=add_workflow_tab,
            refresh_active_workflow=lambda: workflow_workspace.project_workflow(
                shell.workflow_session_service.active_workflow_id,
                force_refresh=True,
                source="direct_workflow_loaded",
            ),
            materialize_loaded_section=lambda workflow_id, section_key: (
                shell.input_canvas_presenter.materialize_loaded_workflow_section(
                    workflow_id,
                    section_key,
                )
            ),
            error_presenter=error_presenter,
            model_resolution_controller_provider=(
                lambda: _model_resolution_controller(shell, manifest=manifest)
            ),
        ),
    )


def _model_resolution_controller(
    shell: Any,
    *,
    manifest: PortableModelManifestService,
) -> DirectWorkflowModelResolutionController | None:
    """Return a controller when the shell has a configured model resolver."""

    create_model_resolver = shell.create_recipe_model_load_resolver
    if not callable(create_model_resolver):
        return None
    return DirectWorkflowModelResolutionController(
        service=PortableWorkflowModelResolutionService(
            manifest,
            create_model_resolver,
        ),
        editor_busy=shell.editor_busy,
        prompt_for_download=(
            shell.shell_recipe_model_resolution_controller.resolve_missing_recipe_models
        ),
        resolution_route_factory=(
            lambda request_id, target_workflow_id: model_resolution_route(
                host=shell,
                request_id=request_id,
                target_workflow_id=target_workflow_id,
            )
        ),
        download_route_factory=(
            lambda request_id, target_workflow_id: model_download_route(
                host=shell,
                request_id=request_id,
                target_workflow_id=target_workflow_id,
            )
        ),
    )


__all__ = ["DirectWorkflowComposition", "compose_direct_workflow_file_actions"]
