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

"""Coordinate shell-level workspace actions through focused collaborators."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast

from substitute.application.generation import (
    GenerationJobSnapshot,
    GenerationRequest,
    GenerationPreparationService,
)
from substitute.application.direct_workflows import (
    DirectWorkflowGenerationPlanService,
)
from substitute.application.workflows import WorkflowDuplicateService
from substitute.presentation.shell.cube_loader import CubeLoadUiCallbacks
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
)
from substitute.presentation.shell.workspace_canvas_actions import (
    WorkspaceCanvasActions,
)
from substitute.presentation.shell.loaded_cube_surface_controller import (
    WorkspaceLoadedCubeSurfaceActions,
    build_cube_load_ui_callbacks_for_view,
)
from substitute.presentation.shell.workspace_cube_picker_actions import (
    WorkspaceCubePickerActions,
)
from substitute.presentation.shell.workspace_cube_stack_actions import (
    WorkspaceCubeStackActions,
)
from substitute.presentation.shell.workspace_file_actions import (
    WorkspaceFileActions,
)
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationPreflightError,
    GenerationUiBindings,
    QueuedGenerationPreparationJob,
    WorkspaceGenerationController,
)
from substitute.presentation.shell.workspace_generation_action_adapter import (
    WorkspaceGenerationActions,
    build_generation_action_bindings,
)
from substitute.presentation.shell.workspace_generation_request_builder import (
    GenerationWorkflowPruneReport,
    active_behavior_snapshot,
    build_generation_request_for_view,
)
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    capture_queued_snapshot_preparation,
    generation_snapshot_from_request,
)
from substitute.presentation.shell.workspace_input_canvas_adapter import (
    handle_input_canvas_image_loaded_for_view,
    handle_input_image_changed_for_view,
    handle_input_image_clicked_for_view,
    handle_input_mask_changed_for_view,
    handle_input_mask_clicked_for_view,
    handle_mask_save_completed_for_view,
    materialize_loaded_cube_input_canvas_for_view,
    reconcile_active_input_canvas_image_for_view,
    refresh_active_mask_pickers_for_view,
)
from substitute.presentation.shell.workspace_controller_composition import (
    compose_workspace_controller_collaborators,
    workspace_controller_views,
)
from substitute.presentation.shell.workspace_scene_generation_controller import (
    SceneGenerationContext,
    SceneRunBookkeeping,
    WorkspaceSceneGenerationActions,
    build_scene_generation_snapshot_from_context,
    build_scene_generation_snapshots_from_context,
    scene_generation_context,
)
from substitute.presentation.shell.workspace_search_actions import (
    WorkspaceSearchActions,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.workspace_controller")

if TYPE_CHECKING:
    from substitute.application.node_behavior import EditorBehaviorSnapshot


class WorkspaceController:
    """Coordinate workspace event handlers through focused shell collaborators."""

    def __init__(self, view: object) -> None:
        """Store the shell view and construct focused action collaborators."""

        self._views = workspace_controller_views(view)
        self._collaborators = compose_workspace_controller_collaborators(
            host=view,
            views=self._views,
            build_cube_load_ui_callbacks=self._build_cube_load_ui_callbacks,
            materialize_loaded_cube_input_canvas=(
                lambda workflow_id, cube_alias: (
                    materialize_loaded_cube_input_canvas_for_view(
                        self._views.canvas,
                        workflow_id,
                        cube_alias,
                    )
                )
            ),
            build_generation_bindings=self.build_generation_bindings,
            build_scene_generation_snapshot=self.build_scene_generation_snapshot,
            scene_generation_preflight_error=self._scene_generation_preflight_error,
        )

    def build_generation_request(self) -> GenerationRequest:
        """Build generation request from the active workflow context."""

        view = self._views.generation
        workflow_id = view.workflow_session_service.active_workflow_id
        return build_generation_request_for_view(
            view=view,
            workflow_id=workflow_id,
            reconcile_active_input_canvas_image=lambda: (
                reconcile_active_input_canvas_image_for_view(self._views.canvas)
            ),
            dirty_mask_error=lambda: GenerationPreflightError(
                workflow_id=workflow_id,
                message=app_text("Failed to save dirty input mask before generation."),
            ),
            live_node_preflight_error=lambda _error: GenerationPreflightError(
                workflow_id=workflow_id,
                message=(
                    app_text(
                        "Substitute could not load required live Comfy node definitions."
                    )
                ),
                report_error=False,
            ),
            empty_workflow_error=lambda: GenerationPreflightError(
                workflow_id=workflow_id,
                message=(
                    app_text(
                        "Generation cannot run because every cube has a runtime error."
                    )
                ),
                report_error=False,
            ),
            missing_panel_logger=self._log_missing_live_node_preflight_panel,
            omission_logger=self._log_pruned_generation_workflow,
            legacy_scope_logger=self._log_legacy_global_override_scope,
        )

    @property
    def file_actions(self) -> WorkspaceFileActions:
        """Return file command actions composed for shell signal wiring."""

        return self._collaborators.file_actions

    @property
    def workflow_workspace(self) -> WorkflowWorkspaceCoordinator:
        """Return workflow lifecycle coordinator for shell signal wiring."""

        return self._collaborators.workflow_workspace

    @property
    def search_actions(self) -> WorkspaceSearchActions:
        """Return search command actions composed for shell signal wiring."""

        return self._collaborators.search_actions

    @property
    def cube_picker_actions(self) -> WorkspaceCubePickerActions:
        """Return cube picker actions composed for shell signal wiring."""

        return self._collaborators.cube_picker_actions

    @property
    def cube_stack_actions(self) -> WorkspaceCubeStackActions:
        """Return cube-card actions composed for shell signal wiring."""

        return self._collaborators.cube_stack_actions

    @property
    def canvas_actions(self) -> WorkspaceCanvasActions:
        """Return canvas command actions composed for shell signal wiring."""

        return self._collaborators.canvas_actions

    @property
    def workflow_duplicate_service(self) -> WorkflowDuplicateService:
        """Return workflow duplication service composed for shell signal wiring."""

        return self._collaborators.workflow_duplicate_service

    @property
    def generation_actions(self) -> WorkspaceGenerationActions:
        """Return generation command actions composed for host wiring."""

        return self._collaborators.generation_actions

    @property
    def scene_generation_actions(self) -> WorkspaceSceneGenerationActions:
        """Return prompt-scene generation actions composed for shell wiring."""

        return self._collaborators.scene_generation_actions

    @property
    def loaded_cube_surface_actions(self) -> WorkspaceLoadedCubeSurfaceActions:
        """Return loaded-cube surface actions composed for shell wiring."""

        return self._collaborators.loaded_cube_surface_actions

    def build_generation_snapshot(self) -> GenerationJobSnapshot:
        """Capture the active workflow as immutable queued Sugar script text."""

        request = self.build_generation_request()
        return self._build_single_generation_snapshot_from_request(
            request=request,
            behavior_snapshot=active_behavior_snapshot(
                self._views.generation,
                request.workflow_id,
            ),
        )

    def build_queued_generation_snapshots(self) -> tuple[GenerationJobSnapshot, ...]:
        """Capture the active workflow as one or more queued generation snapshots."""

        preparation_job = self.capture_queued_generation_preparation()
        return preparation_job.on_prepared(preparation_job.prepare_snapshots())

    def capture_queued_generation_preparation(self) -> QueuedGenerationPreparationJob:
        """Capture a detached queue preparation job after UI preflight and seeds."""

        request = self.build_generation_request()
        behavior_snapshot = active_behavior_snapshot(
            self._views.generation,
            request.workflow_id,
        )
        self._collaborators.generation_seed_randomizer(
            request=request,
            behavior_snapshot=behavior_snapshot,
        )
        view = self._views.generation
        preparation = capture_queued_snapshot_preparation(
            request=request,
            behavior_snapshot=behavior_snapshot,
            preparation_service=self._generation_preparation_service(),
            on_scene_run_prepared=SceneRunBookkeeping(
                workflows=getattr(view.workflow_session_service, "workflows", None),
                output_canvas_state_service=getattr(
                    view,
                    "output_canvas_state_service",
                    None,
                ),
                output_scene_run_service=getattr(
                    view,
                    "output_scene_run_service",
                    None,
                ),
            ),
        )

        return QueuedGenerationPreparationJob(
            prepare_snapshots=preparation.prepare_snapshots,
            on_prepared=preparation.on_prepared,
        )

    def _build_single_generation_snapshot_from_request(
        self,
        *,
        request: GenerationRequest,
        behavior_snapshot: "EditorBehaviorSnapshot | None",
    ) -> GenerationJobSnapshot:
        """Capture one queued Sugar script snapshot from an active request."""

        self._collaborators.generation_seed_randomizer(
            request=request,
            behavior_snapshot=behavior_snapshot,
        )
        return generation_snapshot_from_request(
            request=request,
            behavior_snapshot=behavior_snapshot,
            recipe_io_service=self._views.generation.recipe_io_service,
            prompt_wildcard_preprocessing_service=getattr(
                self._views.generation,
                "prompt_wildcard_preprocessing_service",
                None,
            ),
        )

    def build_scene_generation_snapshots(self) -> tuple[GenerationJobSnapshot, ...]:
        """Capture one immutable queued Sugar script snapshot for each scene."""

        context = self._scene_generation_context()
        view = self._views.generation
        return build_scene_generation_snapshots_from_context(
            context=context,
            preparation_service=self._generation_preparation_service(),
            randomize_request_seeds=self._collaborators.generation_seed_randomizer,
            scene_run_bookkeeping=SceneRunBookkeeping(
                workflows=view.workflow_session_service.workflows,
                output_canvas_state_service=view.output_canvas_state_service,
                output_scene_run_service=getattr(
                    view,
                    "output_scene_run_service",
                    None,
                ),
            ),
        )

    def build_scene_generation_snapshot(self, scene_key: str) -> GenerationJobSnapshot:
        """Capture one immutable queued Sugar script snapshot for a workflow scene."""

        return build_scene_generation_snapshot_from_context(
            context=self._scene_generation_context(),
            scene_key=scene_key,
            preparation_service=self._generation_preparation_service(),
            randomize_request_seeds=self._collaborators.generation_seed_randomizer,
            preflight_error=self._scene_generation_preflight_error,
        )

    def _scene_generation_context(self) -> SceneGenerationContext:
        """Return active generation request, prompt index, and scene analysis."""

        request = self.build_generation_request()
        behavior_snapshot = active_behavior_snapshot(
            self._views.generation,
            request.workflow_id,
        )
        return scene_generation_context(
            request=request,
            behavior_snapshot=behavior_snapshot,
            preflight_error=self._scene_generation_preflight_error,
        )

    @staticmethod
    def _scene_generation_preflight_error(
        *,
        workflow_id: str,
        message: str,
    ) -> GenerationPreflightError:
        """Return the shell preflight exception used by scene generation."""

        return GenerationPreflightError(workflow_id=workflow_id, message=message)

    def _generation_preparation_service(self) -> GenerationPreparationService:
        """Return the application service that prepares queue snapshots."""

        view = self._views.generation
        return GenerationPreparationService(
            recipe_io_service=cast(Any, view.recipe_io_service),
            prompt_wildcard_preprocessing_service=cast(
                Any,
                getattr(view, "prompt_wildcard_preprocessing_service", None),
            ),
            direct_workflow_graph_service=DirectWorkflowGenerationPlanService(
                node_definition_hydrator=cast(
                    Any,
                    getattr(view, "node_definition_gateway", None),
                ),
                node_definition_gateway=cast(
                    Any,
                    getattr(view, "node_definition_gateway", None),
                ),
            ),
        )

    @staticmethod
    def _log_pruned_generation_workflow(
        report: GenerationWorkflowPruneReport,
    ) -> None:
        """Log errored-cube omissions from a generation workflow."""

        log_info(
            _LOGGER,
            "Omitted errored cubes from generation workflow",
            workflow_id=report.workflow_id,
            workflow_name=report.workflow_name,
            omitted_cube_aliases=report.omitted_cube_aliases,
            remaining_cube_count=report.remaining_cube_count,
            reason="cube_runtime_error",
        )

    @staticmethod
    def _log_missing_live_node_preflight_panel(workflow_id: str) -> None:
        """Log when generation live-node preflight cannot find an editor panel."""

        log_warning(
            _LOGGER,
            "Skipped generation live node definition preflight without editor panel",
            workflow_id=workflow_id,
        )

    @staticmethod
    def _log_legacy_global_override_scope(reason: str) -> None:
        """Log when generation falls back to legacy global override serialization."""

        log_info(
            _LOGGER,
            "Generation serialization using legacy global override scope",
            reason=reason,
        )

    def build_generation_bindings(self) -> GenerationUiBindings:
        """Build generation callback bindings for the shell generation controller."""

        return build_generation_action_bindings(
            view=self._views.generation,
            build_generation_request=self.build_generation_request,
            randomize_generation_request_seeds=(
                self._collaborators.generation_seed_randomizer
            ),
            build_queued_generation_snapshots=self.build_queued_generation_snapshots,
            capture_queued_generation_preparation=(
                self.capture_queued_generation_preparation
            ),
        )

    def _build_cube_load_ui_callbacks(self, **_context: object) -> CubeLoadUiCallbacks:
        """Assemble explicit cube-loader callbacks from controller collaborators."""

        return build_cube_load_ui_callbacks_for_view(
            cube_view=self._views.cube,
            callbacks_type=CubeLoadUiCallbacks,
            materialize_loaded_cube_input_canvas=lambda workflow_id, cube_alias: (
                materialize_loaded_cube_input_canvas_for_view(
                    self._views.canvas,
                    workflow_id,
                    cube_alias,
                )
            ),
            refresh_workflow_after_cube_load=(
                self._collaborators.loaded_cube_surface_actions.refresh_workflow_after_cube_load
            ),
            prepare_node_behavior_runtime=(
                self._collaborators.cube_picker_actions.prepare_node_behavior_runtime
            ),
            refresh_loaded_cube_surface=(
                self._collaborators.loaded_cube_surface_actions.refresh_loaded_cube_surface
            ),
            activate_loaded_cube=(
                self._collaborators.loaded_cube_surface_actions.activate_loaded_cube
            ),
            refresh_workflow_after_cube_load_async=(
                self._collaborators.loaded_cube_surface_actions.refresh_workflow_after_cube_load_async
            ),
            refresh_loaded_cube_surface_async=(
                self._collaborators.loaded_cube_surface_actions.refresh_loaded_cube_surface_async
            ),
            cube_load_execution_route_factory=(
                self._collaborators.cube_load_execution_route_factory
            ),
        )

    def on_reconfigure_clicked(self) -> None:
        """Open the shared onboarding surface in reconfigure mode."""

        self._views.generation.request_reconfigure()

    def on_settings_tab_selected(self) -> None:
        """Project the integrated Settings workspace from the pinned tab."""

        self._views.generation.settings_route_controller.project_settings_workspace()

    def switch_workflow_tab(self, index: int) -> None:
        """Activate workflow selected by a legacy index-based tab signal."""

        tabbar = self._views.workflow_workspace.workflow_tabbar
        if index < 0 or index >= tabbar.count():
            return
        self._collaborators.workflow_workspace.activate_workflow(
            tabbar.tabItem(index).routeKey(),
            source="legacy_index_signal",
        )

    def project_workflow(
        self,
        workflow_id: str,
        *,
        force_refresh: bool = False,
        on_surface_complete: Callable[[], None] | None = None,
    ) -> None:
        """Project one workflow route from non-tab orchestration paths."""

        view = self._views.workflow_workspace
        workflow_session_service = getattr(view, "workflow_session_service", None)
        workflows = getattr(workflow_session_service, "workflows", {})
        log_info(
            _LOGGER,
            "workspace controller project workflow",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            view_present=view is not None,
            active_route_before=getattr(view, "_active_workspace_route", ""),
            active_workflow_before=getattr(
                workflow_session_service,
                "active_workflow_id",
                "",
            ),
            workflow_ids=tuple(workflows) if isinstance(workflows, Mapping) else (),
            cube_stack_ids=tuple(getattr(view, "cube_stacks", {})),
            editor_panel_ids=tuple(getattr(view, "editor_panels", {})),
        )
        if on_surface_complete is not None:
            self._collaborators.workflow_workspace.activate_workflow(
                workflow_id,
                source="workspace_projection",
                force_refresh=force_refresh,
                on_surface_complete=on_surface_complete,
            )
        else:
            self._collaborators.workflow_workspace.activate_workflow(
                workflow_id,
                source="workspace_projection",
                force_refresh=force_refresh,
            )
        log_info(
            _LOGGER,
            "workspace controller project workflow completed",
            workflow_id=workflow_id,
            active_route_after=getattr(view, "_active_workspace_route", ""),
            active_workflow_after=getattr(
                workflow_session_service,
                "active_workflow_id",
                "",
            ),
        )

    def on_input_image_changed(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Delegate input-image change handling to the Input canvas presenter."""

        handle_input_image_changed_for_view(
            self._views.canvas,
            cube_alias,
            node_name,
            image_path,
        )

    def on_input_image_clicked(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Delegate input-image focus handling to the Input canvas presenter."""

        handle_input_image_clicked_for_view(
            self._views.canvas,
            cube_alias,
            node_name,
            image_path,
        )

    def on_input_canvas_image_loaded(
        self,
        image_id: object,
        image_path: str,
    ) -> None:
        """Delegate active input-canvas image loads to the Input canvas presenter."""

        handle_input_canvas_image_loaded_for_view(
            self._views.canvas,
            image_id,
            image_path,
        )

    def refresh_active_mask_pickers(self) -> None:
        """Delegate active mask-picker refresh to the Input canvas presenter."""

        refresh_active_mask_pickers_for_view(self._views.canvas)

    def on_input_mask_changed(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Delegate input-mask update handling to the Input canvas presenter."""

        handle_input_mask_changed_for_view(
            self._views.canvas,
            cube_alias,
            node_name,
            mask_path,
        )

    def on_input_mask_clicked(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Delegate mask focus handling to the Input canvas presenter."""

        handle_input_mask_clicked_for_view(
            self._views.canvas,
            cube_alias,
            node_name,
            mask_path,
        )

    def on_mask_save_completed(
        self,
        mask_id: str,
        path: str,
    ) -> None:
        """Delegate mask-save completion handling to the Input canvas presenter."""

        handle_mask_save_completed_for_view(self._views.canvas, mask_id, path)


__all__ = [
    "GenerationUiBindings",
    "QueuedGenerationPreparationJob",
    "WorkspaceController",
    "WorkspaceGenerationController",
]
