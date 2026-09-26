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
from substitute.application.comfy_connection import ComfyConnectionRecoveryService
from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackResolutionService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessmentService,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.errors import SubstituteOperationContext
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from substitute.infrastructure.comfy.comfy_workflow_nodepack_catalog import (
    ComfyWorkflowNodepackCatalog,
)
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
)
from substitute.domain.onboarding import ComfyTargetConfiguration
from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.dialogs.workflow_nodepack_recovery_dialog import (
    WorkflowNodepackRecoveryPresenter,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher

from .direct_workflow_file_actions import DirectWorkflowFileActions
from .direct_workflow_model_resolution import (
    DirectWorkflowModelResolutionController,
)
from .direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)
from .workflow_nodepack_recovery_execution import WorkflowNodepackRecoveryRoute
from .workspace_controller_composition import (
    model_download_route,
    model_resolution_route,
)
from .comfy_connection_composition import ComfyConnectionRuntimeComposition
from .main_window_dependencies import MainWindowDependencies


@dataclass(frozen=True, slots=True)
class DirectWorkflowComposition:
    """Carry direct-workflow application and presentation collaborators."""

    load_service: DirectWorkflowLoadService
    file_actions: DirectWorkflowFileActions


@dataclass(frozen=True, slots=True)
class DirectWorkflowNodepackRecoveryComposition:
    """Carry the workflow nodepack recovery controller and review owner."""

    controller: DirectWorkflowNodepackRecoveryController
    presenter: WorkflowNodepackRecoveryPresenter


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
                shell.input_image_materialization_presenter.materialize_loaded_section(
                    workflow_id,
                    section_key,
                )
            ),
            error_presenter=error_presenter,
            model_resolution_controller_provider=(
                lambda: _model_resolution_controller(shell, manifest=manifest)
            ),
            nodepack_recovery_controller_provider=lambda: getattr(
                shell,
                "direct_workflow_nodepack_recovery_controller",
                None,
            ),
        ),
    )


def compose_direct_workflow_nodepack_recovery(
    shell: Any,
    *,
    target: ComfyTargetConfiguration,
    file_actions: DirectWorkflowFileActions,
    connection_recovery: ComfyConnectionRecoveryService,
    error_presenter: ErrorReportPresenterProtocol,
) -> DirectWorkflowNodepackRecoveryComposition:
    """Compose missing-node planning, review, install, restart, and rehydration."""

    presenter = WorkflowNodepackRecoveryPresenter(parent=shell)

    def route_factory(
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> WorkflowNodepackRecoveryRoute:
        """Create one owner-thread route on the package-maintenance lane."""

        submitter = shell.execution_runtime.submitter(
            "package_maintenance",
            owner_id=(f"workflow_nodepack_recovery_{target_workflow_id}_{request_id}"),
            dispatcher=QtOwnerThreadDispatcher(shell),
        )
        return WorkflowNodepackRecoveryRoute(
            submitter=submitter,
            close=submitter.close,
        )

    def present_failure(workflow_id: str, stage: str, error: BaseException) -> None:
        """Present one non-blocking recovery failure with stable workflow context."""

        error_presenter.show_exception_report(
            title=app_text("Custom node recovery failed"),
            message=app_text(
                "Substitute could not recover every custom node required by this workflow."
            ),
            stage=stage,
            error=error,
            context=SubstituteOperationContext(
                operation="recover_workflow_nodepacks",
                workflow_id=workflow_id,
            ),
        )

    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=WorkflowNodepackRecoveryPlanService(
            assessment=WorkflowNodeDefinitionAssessmentService(
                shell.node_definition_gateway
            ),
            resolution=WorkflowNodepackResolutionService(
                ComfyWorkflowNodepackCatalog()
            ),
        ),
        installer=WorkflowNodepackInstaller(),
        workspace=target.workspace_path,
        python_executable=(
            target.python_binding.executable
            if target.python_binding is not None
            else None
        ),
        editor_busy=shell.editor_busy,
        present_review=presenter.present,
        present_failure=present_failure,
        request_restart=connection_recovery.request_restart,
        rehydrate_workflow=file_actions.rehydrate_node_definitions,
        route_factory=route_factory,
    )
    connection_recovery.add_observer(controller.observe_connection)
    return DirectWorkflowNodepackRecoveryComposition(
        controller=controller,
        presenter=presenter,
    )


def bind_nodepack_recovery(
    shell: Any,
    dependencies: MainWindowDependencies,
    comfy_connection: ComfyConnectionRuntimeComposition,
    error_presenter: ErrorReportPresenterProtocol,
) -> None:
    """Compose workflow nodepack recovery and bind its shell lifecycle."""

    composition = compose_direct_workflow_nodepack_recovery(
        shell,
        target=dependencies.comfy_target,
        file_actions=shell.direct_workflow_file_actions,
        connection_recovery=comfy_connection.recovery_service,
        error_presenter=error_presenter,
    )
    shell.shell_resource_lifecycle.register(
        "direct_workflow_nodepack_recovery",
        composition.controller.close,
    )
    shell.shell_resource_lifecycle.register(
        "direct_workflow_nodepack_recovery_review",
        composition.presenter.close,
    )
    shell.direct_workflow_nodepack_recovery_controller = composition.controller


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


__all__ = [
    "DirectWorkflowComposition",
    "DirectWorkflowNodepackRecoveryComposition",
    "bind_nodepack_recovery",
    "compose_direct_workflow_file_actions",
    "compose_direct_workflow_nodepack_recovery",
]
