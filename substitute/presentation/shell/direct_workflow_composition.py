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
from pathlib import Path
from typing import Any, cast
from qfluentwidgets import InfoBar  # type: ignore[import-untyped]

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
from substitute.infrastructure.comfy.managed_validation import (
    is_workspace_installed,
    workspace_python_path,
)
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)
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
    NodepackRecoveryHandoffPort,
)
from .workflow_nodepack_recovery_execution import WorkflowNodepackRecoveryRoute
from .workspace_controller_composition import (
    model_download_route,
    model_resolution_route,
)
from .comfy_connection_composition import ComfyConnectionRuntimeComposition
from .main_window_dependencies import MainWindowDependencies
from .open_workflow_nodepack_reassessment import OpenWorkflowNodepackReassessment
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.shell.direct_workflow_composition")


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
    connection_recovery: ComfyConnectionRecoveryService,
) -> DirectWorkflowNodepackRecoveryComposition:
    """Compose missing-node planning, review, install, restart, and rehydration."""

    presenter = WorkflowNodepackRecoveryPresenter(parent=shell)

    def route_factory(
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> WorkflowNodepackRecoveryRoute:
        """Create one owner-thread route on the package-maintenance lane."""

        dispatcher = QtOwnerThreadDispatcher(shell)
        submitter = shell.execution_runtime.submitter(
            "package_maintenance",
            owner_id=(f"workflow_nodepack_recovery_{target_workflow_id}_{request_id}"),
            dispatcher=dispatcher,
        )
        return WorkflowNodepackRecoveryRoute(
            submitter=submitter,
            close=submitter.close,
            publish=lambda callback, reason: dispatcher.publish(
                callback, reason=reason
            ),
        )

    def present_failure(workflow_id: str, stage: str, error: BaseException) -> None:
        """Keep a failed repair visible without blocking the loaded workflow."""

        log_exception(
            _LOGGER,
            "Custom node recovery did not complete",
            error=error,
            workflow_id=workflow_id,
            stage=stage,
        )
        InfoBar.warning(
            title=render_application_text(app_text("Custom node recovery failed")),
            content=render_application_text(
                app_text(
                    "Substitute could not recover every custom node required by this workflow."
                )
            ),
            duration=5000,
            parent=shell,
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
        python_executable=_nodepack_install_python(target),
        present_review=presenter.present,
        present_failure=present_failure,
        can_restart=lambda: connection_recovery.state.can_restart,
        handoff_provider=lambda: cast(
            NodepackRecoveryHandoffPort | None,
            getattr(shell, "nodepack_recovery_handoff", None),
        ),
        request_restart=connection_recovery.request_restart,
        route_factory=route_factory,
    )
    connection_recovery.add_observer(controller.observe_connection)
    return DirectWorkflowNodepackRecoveryComposition(
        controller=controller,
        presenter=presenter,
    )


def _nodepack_install_python(target: ComfyTargetConfiguration) -> Path | None:
    """Use the selected binding or an installed, owned managed runtime."""

    if target.python_binding is not None:
        return target.python_binding.executable
    workspace = target.workspace_path
    if (
        target.mode is ComfyTargetMode.MANAGED_LOCAL
        and target.install_owned
        and workspace is not None
        and is_workspace_installed(workspace)
    ):
        return workspace_python_path(workspace)
    return None


def bind_nodepack_recovery(
    shell: Any,
    dependencies: MainWindowDependencies,
    comfy_connection: ComfyConnectionRuntimeComposition,
) -> None:
    """Compose workflow nodepack recovery and bind its shell lifecycle."""

    composition = compose_direct_workflow_nodepack_recovery(
        shell,
        target=dependencies.comfy_target,
        connection_recovery=comfy_connection.recovery_service,
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
    reassessment = OpenWorkflowNodepackReassessment(
        shell=shell,
        recovery=composition.controller,
    )
    connection = comfy_connection.recovery_service
    connection.add_observer(reassessment.observe_connection)
    shell.restore_finalized.connect(reassessment.schedule_after_restore)

    def close_reassessment() -> None:
        """Detach both runtime notifications before the shell is destroyed."""

        connection.remove_observer(reassessment.observe_connection)
        shell.restore_finalized.disconnect(reassessment.schedule_after_restore)

    shell.shell_resource_lifecycle.register(
        "open_workflow_nodepack_reassessment",
        close_reassessment,
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
            shell.shell_recipe_model_resolution_controller.prompt_for_direct_workflow_download
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
