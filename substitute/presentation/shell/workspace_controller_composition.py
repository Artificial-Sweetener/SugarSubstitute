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

"""Compose collaborators owned by the shell workspace controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from PySide6.QtCore import QTimer

from substitute.application.generation import (
    GenerationRequest,
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.cubes import CubeStackService
from substitute.application.workflows import (
    CubeDuplicationService,
    WorkflowDuplicateService,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.shell.cube_loader import (
    CubeLoadExecutionRoute,
    CubeLoadUiCallbacks,
)
from substitute.presentation.shell.loaded_cube_surface_controller import (
    WorkspaceLoadedCubeSurfaceActions,
)
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeTabIconResolver,
)
from substitute.presentation.shell.cube_duplication_link_reconciler import (
    DeferredCubeDuplicationLinkReconciler,
)
from substitute.presentation.shell.cube_surface_projection_coordinator import (
    CubeSurfaceProjectionCoordinator,
)
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)
from substitute.presentation.shell.workspace_canvas_actions import (
    WorkspaceCanvasActionView,
    WorkspaceCanvasActions,
)
from substitute.presentation.shell.workspace_cube_picker_actions import (
    CatalogRefreshRoute,
    WorkspaceCubePickerActionView,
    WorkspaceCubePickerActions,
)
from substitute.presentation.shell.workspace_cube_stack_actions import (
    WorkspaceCubeStackActionView,
    WorkspaceCubeStackActions,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)
from substitute.presentation.shell.workspace_file_actions import (
    RecipeModelDownloadRoute,
    RecipeModelResolutionRoute,
    WorkspaceFileActionView,
    WorkspaceFileActions,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    WorkspaceGenerationActions,
    randomize_generation_request_seeds,
)
from substitute.presentation.shell import workspace_generation_controller
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)
from substitute.presentation.shell.workspace_ports import WorkspaceGenerationView
from substitute.presentation.shell.workspace_scene_generation_controller import (
    WorkspaceSceneGenerationActions,
)
from substitute.presentation.shell.workspace_search_actions import (
    WorkspaceSearchActionView,
    WorkspaceSearchActions,
)
from substitute.presentation.shell.seed_value_projector import SeedValueProjector
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from substitute.shared.logging.logger import log_exception


@dataclass(frozen=True)
class WorkspaceControllerViews:
    """Carry typed shell views consumed by workspace controller methods."""

    generation: WorkspaceGenerationView
    workflow_workspace: WorkflowWorkspaceView
    file: WorkspaceFileActionView
    cube: WorkspaceCubePickerActionView
    canvas: WorkspaceCanvasActionView
    search: WorkspaceSearchActionView


@dataclass(frozen=True)
class WorkspaceControllerCollaborators:
    """Carry composed action collaborators for one workspace controller."""

    workflow_workspace: WorkflowWorkspaceCoordinator
    workflow_duplicate_service: WorkflowDuplicateService
    canvas_actions: WorkspaceCanvasActions
    cube_picker_actions: WorkspaceCubePickerActions
    cube_stack_actions: WorkspaceCubeStackActions
    file_actions: WorkspaceFileActions
    search_actions: WorkspaceSearchActions
    generation_seed_randomizer: Callable[..., SeedRandomizationResult]
    generation_actions: WorkspaceGenerationActions
    scene_generation_actions: WorkspaceSceneGenerationActions
    loaded_cube_surface_actions: WorkspaceLoadedCubeSurfaceActions
    cube_load_execution_route_factory: Callable[..., CubeLoadExecutionRoute]


class _WorkspaceCanvasOutputImageRegistrar:
    """Adapt WorkspaceCanvasActions to the file-action Output registrar port."""

    def __init__(self, canvas_actions: WorkspaceCanvasActions) -> None:
        """Store the Output canvas orchestration owner."""

        self._canvas_actions = canvas_actions

    def add_output_image(
        self,
        workflow_id: str,
        image: object,
        image_meta: object,
    ) -> None:
        """Register one Output image through canvas orchestration."""

        self._canvas_actions.handle_loaded_output_image(workflow_id, image, image_meta)


def workspace_controller_views(view: Any) -> WorkspaceControllerViews:
    """Return typed structural views for one shell workspace host."""

    return WorkspaceControllerViews(
        generation=cast(WorkspaceGenerationView, view),
        workflow_workspace=cast(WorkflowWorkspaceView, view),
        file=cast(WorkspaceFileActionView, view),
        cube=cast(WorkspaceCubePickerActionView, view),
        canvas=cast(WorkspaceCanvasActionView, view),
        search=cast(WorkspaceSearchActionView, view),
    )


def compose_workspace_controller_collaborators(
    *,
    host: object,
    views: WorkspaceControllerViews,
    build_cube_load_ui_callbacks: Callable[..., object],
    materialize_loaded_cube_input_canvas: Callable[[str, str], None],
    build_generation_bindings: Callable[[], GenerationUiBindings],
    build_scene_generation_snapshot: Callable[[str], object],
    scene_generation_preflight_error: Callable[..., object],
) -> WorkspaceControllerCollaborators:
    """Build the collaborator bundle used by the workspace controller."""

    workflow_workspace = WorkflowWorkspaceCoordinator(views.workflow_workspace)
    workflow_duplicate_service = WorkflowDuplicateService()
    loaded_cube_surface_actions = WorkspaceLoadedCubeSurfaceActions(
        cube_view=views.cube,
        workflow_workspace_view=views.workflow_workspace,
        workflow_workspace=workflow_workspace,
        schedule_deferred_rebuild=lambda callback: QTimer.singleShot(0, callback),
        schedule_indicator_realign=lambda callback: QTimer.singleShot(0, callback),
    )
    error_presenter = cast(
        ErrorReportPresenterProtocol | None,
        getattr(host, "_error_presenter", None),
    )
    canvas_actions = WorkspaceCanvasActions(
        views.canvas,
        error_presenter=error_presenter,
        asset_reveal_service=getattr(host, "asset_reveal_service", None),
    )
    cube_picker_actions = WorkspaceCubePickerActions(
        views.cube,
        build_cube_load_ui_callbacks=build_cube_load_ui_callbacks,
        error_presenter=error_presenter,
        catalog_refresh_route_factory=(
            lambda cube_load_trace_id: _cube_catalog_refresh_route(
                host=host,
                cube_load_trace_id=cube_load_trace_id,
            )
        ),
    )
    cube_duplication_service = CubeDuplicationService(
        cube_stack_service=CubeStackService(),
        link_reconciler=DeferredCubeDuplicationLinkReconciler(views.cube),
    )
    cube_stack_actions = WorkspaceCubeStackActions(
        cast(WorkspaceCubeStackActionView, views.cube),
        duplication_service=cube_duplication_service,
        stack_presenter=CubeStackPresenter(
            icon_resolver=CubeTabIconResolver(
                cube_icon_factory=getattr(views.cube, "cube_icon_factory", None),
            )
        ),
        surface_projector=CubeSurfaceProjectionCoordinator(
            surface_actions=loaded_cube_surface_actions,
            active_surface_refresher=ActiveWorkflowSurfaceRefresher(views.cube),
            materialize_input_canvas=materialize_loaded_cube_input_canvas,
        ),
    )

    def cube_load_execution_route_factory(
        cube_load_trace_id: str,
    ) -> CubeLoadExecutionRoute:
        """Create an execution route for one cube-load request."""

        return _cube_load_execution_route(
            host=host,
            cube_load_trace_id=cube_load_trace_id,
        )

    file_actions = WorkspaceFileActions(
        views.file,
        add_workflow_tab_requested=lambda: _add_workflow_tab(workflow_workspace),
        build_cube_load_ui_callbacks=cast(
            Callable[..., CubeLoadUiCallbacks],
            build_cube_load_ui_callbacks,
        ),
        output_image_registrar=_WorkspaceCanvasOutputImageRegistrar(canvas_actions),
        error_presenter=error_presenter,
        recipe_output_sibling_discovery_service=getattr(
            host,
            "recipe_output_sibling_discovery_service",
            None,
        ),
        recipe_model_resolution_handler=cast(
            Callable[[Any], object | None] | None,
            getattr(
                getattr(host, "shell_recipe_model_resolution_controller", None),
                "resolve_missing_recipe_models",
                None,
            ),
        ),
        recipe_model_resolution_route_factory=(
            lambda request_id, target_workflow_id: _recipe_model_resolution_route(
                host=host,
                request_id=request_id,
                target_workflow_id=target_workflow_id,
            )
        ),
        recipe_model_download_route_factory=(
            lambda request_id, target_workflow_id: _recipe_model_download_route(
                host=host,
                request_id=request_id,
                target_workflow_id=target_workflow_id,
            )
        ),
        log_exception_func=log_exception,
    )
    search_actions = WorkspaceSearchActions(views.search)
    seed_randomization_service = SeedRandomizationService()
    seed_value_projector = SeedValueProjector(views.generation)

    def generation_seed_randomizer(
        *,
        request: object,
        behavior_snapshot: object,
    ) -> SeedRandomizationResult:
        """Randomize request seeds through the composed application service."""

        seed_randomizer = cast(
            Callable[..., SeedRandomizationResult], randomize_generation_request_seeds
        )
        result = seed_randomizer(
            seed_randomization_service=seed_randomization_service,
            request=cast(GenerationRequest, request),
            behavior_snapshot=cast(Any, behavior_snapshot),
        )
        seed_value_projector.project(cast(GenerationRequest, request).workflow, result)
        if result.changed:
            request_autosave = getattr(
                views.generation, "request_session_autosave", None
            )
            if callable(request_autosave):
                request_autosave()
        return result

    generation_actions = WorkspaceGenerationActions(
        views.generation,
        build_generation_bindings=build_generation_bindings,
    )
    scene_generation_actions = WorkspaceSceneGenerationActions(
        cast(Any, views.generation),
        build_bindings=cast(Any, build_generation_bindings),
        build_scene_snapshot=cast(Any, build_scene_generation_snapshot),
        preflight_error=cast(Any, scene_generation_preflight_error),
        preflight_error_type=getattr(
            workspace_generation_controller,
            "GenerationPreflightError",
        ),
        preflight_failure=getattr(
            workspace_generation_controller,
            "generation_preflight_failure",
        ),
    )
    return WorkspaceControllerCollaborators(
        workflow_workspace=workflow_workspace,
        workflow_duplicate_service=workflow_duplicate_service,
        canvas_actions=canvas_actions,
        cube_picker_actions=cube_picker_actions,
        cube_stack_actions=cube_stack_actions,
        file_actions=file_actions,
        search_actions=search_actions,
        generation_seed_randomizer=generation_seed_randomizer,
        generation_actions=generation_actions,
        scene_generation_actions=scene_generation_actions,
        loaded_cube_surface_actions=loaded_cube_surface_actions,
        cube_load_execution_route_factory=cube_load_execution_route_factory,
    )


def _cube_catalog_refresh_route(
    *,
    host: object,
    cube_load_trace_id: str,
) -> CatalogRefreshRoute:
    """Create the runtime route for one cube-picker catalog refresh task."""

    execution_runtime = getattr(host, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError("execution_runtime is required for cube catalog refresh.")
    runtime_submitter = execution_runtime.submitter(
        "disk_io_low_priority",
        owner_id=f"cube_picker_catalog_refresh_{cube_load_trace_id}",
        dispatcher=QtOwnerThreadDispatcher(),
    )
    return CatalogRefreshRoute(
        submitter=runtime_submitter,
        close=runtime_submitter.close,
    )


def _cube_load_execution_route(
    *,
    host: object,
    cube_load_trace_id: str,
) -> CubeLoadExecutionRoute:
    """Create the runtime route for one cube-load request."""

    execution_runtime = getattr(host, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError("execution_runtime is required for cube loading.")
    execution_owner_id = f"cube_load_{cube_load_trace_id}_{uuid4().hex}"
    runtime_submitter = execution_runtime.submitter(
        "cube_load",
        owner_id=execution_owner_id,
        dispatcher=QtOwnerThreadDispatcher(),
    )
    return CubeLoadExecutionRoute(
        submitter=runtime_submitter,
        close=runtime_submitter.close,
    )


def _add_workflow_tab(workflow_workspace: WorkflowWorkspaceCoordinator) -> None:
    """Add a workflow tab while hiding the coordinator's return value."""

    workflow_workspace.add_workflow()


def _recipe_model_resolution_route(
    *,
    host: object,
    request_id: int,
    target_workflow_id: str,
) -> RecipeModelResolutionRoute:
    """Create the runtime route for one recipe model resolution task."""

    execution_runtime = getattr(host, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError("execution_runtime is required for recipe model resolution.")
    submitter = execution_runtime.submitter(
        "recipe_model_resolution",
        owner_id=f"recipe_model_resolution_{target_workflow_id}_{request_id}",
        dispatcher=QtOwnerThreadDispatcher(),
    )
    return RecipeModelResolutionRoute(
        submitter=submitter,
        close=submitter.close,
    )


def _recipe_model_download_route(
    *,
    host: object,
    request_id: int,
    target_workflow_id: str,
) -> RecipeModelDownloadRoute:
    """Create the runtime route for one deferred recipe model download."""

    execution_runtime = getattr(host, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError("execution_runtime is required for model downloads.")
    submitter = execution_runtime.submitter(
        "model_download",
        owner_id=f"recipe_model_download_{target_workflow_id}_{request_id}",
        dispatcher=QtOwnerThreadDispatcher(),
    )
    return RecipeModelDownloadRoute(
        submitter=submitter,
        progress_dispatcher=QtOwnerThreadDispatcher(),
        close=submitter.close,
    )


__all__ = [
    "WorkspaceControllerCollaborators",
    "WorkspaceControllerViews",
    "compose_workspace_controller_collaborators",
    "workspace_controller_views",
]
