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

"""Compose the complete Input-canvas application and presentation slice."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from substitute.application.workflows.generation_input_image_association_service import (
    GenerationInputImageAssociationService,
)
from substitute.application.workflows.generation_input_image_selection_service import (
    GenerationInputImageSelectionService,
)
from substitute.application.workflows.input_canvas_capability_service import (
    InputCanvasCapabilityService,
)
from substitute.application.workflows.input_canvas_interaction_profile_service import (
    InputCanvasInteractionProfileService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.restored_ordered_mask_collection_service import (
    RestoredOrderedMaskCollectionService,
)
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.synthetic_canvas_resolution_transaction_service import (
    SyntheticCanvasResolutionTransactionService,
)
from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)
from substitute.presentation.canvas.input.input_canvas_presenter import (
    InputCanvasPresenter,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_tool_layout import (
    create_input_canvas_tool_layout,
)
from substitute.presentation.canvas.input.input_canvas_tool_profile_controller import (
    InputCanvasToolProfileController,
)
from substitute.presentation.canvas.input.input_contextual_toolbar_installation import (
    install_input_contextual_toolbar,
)
from substitute.presentation.canvas.input.input_document_change_observer import (
    InputDocumentChangeObserver,
)
from substitute.presentation.canvas.input.input_editable_document_change_tracker import (
    InputEditableDocumentChangeTracker,
)
from substitute.presentation.canvas.input.input_editable_document_lifecycle import (
    InputEditableDocumentLifecycle,
)
from substitute.presentation.canvas.input.input_generation_image_materializer import (
    InputGenerationImageMaterializer,
)
from substitute.presentation.canvas.input.input_generation_mask_materializer import (
    InputGenerationMaskMaterializer,
)
from substitute.presentation.canvas.input.input_generation_snapshot_service import (
    InputGenerationSnapshotService,
)
from substitute.presentation.canvas.input.input_node_interaction_controller import (
    InputNodeInteractionController,
)
from substitute.presentation.canvas.input.input_mask_visual_opacity_controller import (
    InputMaskVisualOpacityController,
)
from substitute.presentation.canvas.input.input_scene_mapping_changes import (
    InputSceneMappingChanges,
)
from substitute.presentation.canvas.input.input_shared_edge_resize_policy import (
    InputSharedEdgeResizePolicy,
)
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_tool_options import (
    install_input_tool_options,
)
from substitute.presentation.canvas.input.synthetic_canvas_geometry_adapter import (
    SyntheticCanvasGeometryAdapter,
)
from substitute.presentation.editor.panel.mask_visual_opacity_projection import (
    project_mask_visual_opacity_value,
)
from substitute.presentation.regional import region_color
from substitute.presentation.regional.canvas_hover_presenter import (
    RegionalCanvasHoverPresenter,
)
from substitute.presentation.regional.interaction_coordinator import (
    RegionalInteractionCoordinator,
)
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)
from substitute.presentation.shell.canvas_route_controller import (
    canvas_route_controller_for,
)
from substitute.presentation.shell.input_canvas_shell_adapter import (
    InputCanvasShellAdapter,
)
from substitute.presentation.shell.regional_mask_action_controller import (
    RegionalMaskActionController,
)
from substitute.presentation.shell.synthetic_canvas_resolution_controller import (
    SyntheticCanvasResolutionController,
)


@dataclass(frozen=True)
class MainWindowInputCanvasComposition:
    """Hold Input-canvas collaborators composed after canvas widgets exist."""

    workflow_input_canvas_service: Any
    input_canvas_tool_controller: Any
    input_canvas_tool_profile_controller: Any
    input_shared_edge_resize_policy: InputSharedEdgeResizePolicy
    input_scene_mapping_changes: InputSceneMappingChanges
    input_canvas_shell_adapter: Any
    input_canvas_presenter: Any
    input_node_interaction_controller: Any
    input_mask_visual_opacity_controller: Any
    input_document_change_observer: Any
    input_editable_document_change_tracker: InputEditableDocumentChangeTracker
    input_generation_snapshot_service: Any
    input_editable_document_lifecycle: Any
    input_canvas_capability_service: Any
    regional_interaction_coordinator: Any
    restored_ordered_mask_collections: Any
    synthetic_canvas_resolution_role_service: Any
    synthetic_canvas_resolution_transaction_service: Any
    synthetic_canvas_geometry_adapter: Any
    synthetic_canvas_resolution_controller: Any


def compose_input_canvas_controllers(shell: Any) -> MainWindowInputCanvasComposition:
    """Create Input-canvas services and presenter controllers for the shell."""

    input_canvas = shell.canvas_host.canvas_for("Input")
    if input_canvas is None:
        raise RuntimeError("Canvas tabs must include an Input canvas.")
    canvas_route_controller = canvas_route_controller_for(shell)

    workflow_input_canvas_service = WorkflowInputCanvasService(
        input_canvas_plan_service=shell.input_canvas_plan_service,
        input_canvas_state_service=shell.input_canvas_state_service,
        canvas_io_service=shell.canvas_io_service,
        workflow_asset_service=shell.workflow_asset_service,
        graph_section_service=shell.graph_section_service,
    )
    restored_ordered_mask_collections = RestoredOrderedMaskCollectionService(
        endpoint_service=shell.input_asset_endpoint_service,
        graph_sections=shell.graph_section_service,
        graph_values=OrderedMaskGraphValueService(shell.graph_section_service),
    )
    input_tool_runtime = create_input_canvas_tool_system()
    input_tool_layout = create_input_canvas_tool_layout()
    install_input_tool_options(
        input_tool_runtime,
        input_canvas.document.tool_options,
    )
    install_input_contextual_toolbar(
        input_tool_runtime,
        input_canvas.document.tool_options,
    )
    input_shared_edge_resize_policy = InputSharedEdgeResizePolicy(
        input_canvas.document.canvas,
        parent=input_canvas.document.canvas,
    )
    input_scene_mapping_changes = InputSceneMappingChanges(
        input_canvas.document.canvas,
        parent=input_canvas.document.canvas,
    )
    input_canvas_tool_controller = InputCanvasToolController(
        transform_activator=input_canvas.document.tool_context.activate_transform,
        operation_setter=input_canvas.document.set_canvas_operation,
        current_operation_provider=input_canvas.document.current_canvas_operation,
        runtime=input_tool_runtime,
        layout=input_tool_layout,
    )
    input_canvas.bind_tool_runtime(
        input_tool_runtime,
        input_tool_layout,
        restore_operation=input_canvas_tool_controller.restore_operation,
    )
    input_canvas_interaction_profiles = InputCanvasInteractionProfileService(
        input_canvas_plan_service=shell.input_canvas_plan_service,
        graph_section_service=shell.graph_section_service,
    )
    input_canvas_tool_profile_controller = InputCanvasToolProfileController(
        document_context=input_canvas.document.tool_context,
        active_workflow=lambda: shell.workflow_session_service.workflows.get(
            shell.workflow_session_service.active_workflow_id
        ),
        interaction_profile=input_canvas_interaction_profiles.profile_for,
        palette=input_tool_runtime.palette,
        activation=input_canvas_tool_controller,
    )
    input_canvas.document.tool_context.changed.connect(
        input_canvas_tool_profile_controller.refresh_document_context
    )
    input_canvas.document.canvasToolChanged.connect(
        input_canvas_tool_controller.synchronize_native_tool
    )
    input_canvas.destroyed.connect(input_canvas_tool_profile_controller.close)
    input_canvas.toolRequested.connect(input_canvas_tool_controller.request_tool)
    input_canvas_tool_profile_controller.refresh_workflow_profile()
    input_canvas_shell_adapter = InputCanvasShellAdapter(shell)
    input_node_preview_coordinator = InputNodePreviewCoordinator(
        bindings=input_canvas.document.preview_bindings,
        active_panel=lambda: shell.active_editor_panel,
    )
    regional_mask_presenter = RegionalMaskCollectionPresenter(
        input_document=input_canvas.document,
        active_workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        mask_color=region_color,
        preview_coordinator=input_node_preview_coordinator,
    )
    input_canvas_presenter = InputCanvasPresenter(
        input_document=input_canvas.document,
        current_image_id_provider=input_canvas.current_image_id_for_event,
        active_workflow_provider=shell.get_active_workflow,
        active_editor_panel_provider=lambda: shell.active_editor_panel,
        workflow_session_service=shell.workflow_session_service,
        workflow_input_canvas_service=workflow_input_canvas_service,
        input_canvas_state_service=shell.input_canvas_state_service,
        workflow_name_provider=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir_provider=lambda: Path(shell.path_bundle.projects_dir),
        mask_color_provider=region_color,
        regional_mask_presenter=regional_mask_presenter,
        preview_coordinator=input_node_preview_coordinator,
        mark_canvas_changed=input_canvas_shell_adapter.mark_input_canvas_changed,
        error_presenter=getattr(shell, "_error_presenter", None),
    )
    regional_interaction_coordinator = RegionalInteractionCoordinator(
        workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        canvas_hover=RegionalCanvasHoverPresenter(
            workflow=shell.get_active_workflow,
            color_target=input_canvas.document,
        ),
    )
    regional_mask_actions = RegionalMaskActionController(
        active_workflow=shell.get_active_workflow,
        active_workflow_id=lambda: shell.workflow_session_service.active_workflow_id,
        workflow_name=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir=lambda: Path(shell.path_bundle.projects_dir),
        workflow_service=workflow_input_canvas_service,
        state_service=shell.input_canvas_state_service,
        presenter=regional_mask_presenter,
        accept_canvas_selection=lambda: (
            getattr(
                shell,
                "_shell_restore_lifecycle",
                "running",
            )
            == "running"
        ),
    )
    input_canvas.document.activeMaskChanged.connect(
        regional_mask_actions.select_canvas_mask
    )
    input_node_interaction_controller = InputNodeInteractionController(
        active_workflow=shell.get_active_workflow,
        active_workflow_id=lambda: shell.workflow_session_service.active_workflow_id,
        workflow_input_canvas_service=workflow_input_canvas_service,
        input_canvas_state_service=shell.input_canvas_state_service,
        materialize_image_selection=input_canvas_presenter.materialize_image_selection,
        apply_mask_selection=input_canvas_presenter.apply_mask_selection,
        handle_ordered_mask_action=regional_mask_actions.handle,
        activate_input_canvas=lambda: bool(
            canvas_route_controller.activate_route(
                "Input",
                keyboard_focus=True,
            )
        ),
        refresh_mask_pickers=input_canvas_presenter.refresh_active_mask_pickers,
    )
    input_mask_visual_opacity_controller = InputMaskVisualOpacityController(
        active_workflow=shell.get_active_workflow,
        active_workflow_id=lambda: shell.workflow_session_service.active_workflow_id,
        binding_service=workflow_input_canvas_service,
        state_service=shell.input_canvas_state_service,
        document=input_canvas.document,
        project_opacity=lambda workflow_id, association_key, opacity: (
            _project_mask_visual_opacity(
                shell,
                workflow_id,
                association_key,
                opacity,
            )
        ),
        mark_changed=input_canvas_shell_adapter.mark_input_canvas_presentation_changed,
        request_autosave=shell.request_session_autosave,
    )
    input_canvas.document.canvas.sceneEditHistoryChanged.connect(
        input_mask_visual_opacity_controller.reconcile_history
    )
    input_editable_document_lifecycle = InputEditableDocumentLifecycle(
        document=input_canvas.document.editable_persistence,
        archive_path=(
            Path(shell.path_bundle.session_dir) / "input-editable-document.ccanvas"
        ),
    )
    input_editable_document_change_tracker = InputEditableDocumentChangeTracker(
        changes=(
            input_canvas.document.canvas.compositionChanged,
            input_canvas.document.maskContentChanged,
            input_scene_mapping_changes.changed,
        ),
        mark_changed=input_editable_document_lifecycle.mark_changed,
    )
    input_document_change_observer = InputDocumentChangeObserver(
        changes=(
            input_canvas.document.maskContentChanged,
            input_scene_mapping_changes.changed,
        ),
        active_workflow_id=lambda: shell.workflow_session_service.active_workflow_id,
        mark_workflow_changed=input_canvas_shell_adapter.mark_input_canvas_changed,
        request_autosave=shell.request_session_autosave,
    )
    image_association_service = GenerationInputImageAssociationService(
        input_canvas_plan_service=shell.input_canvas_plan_service,
        graph_section_service=shell.graph_section_service,
        workflow_asset_service=shell.workflow_asset_service,
    )
    image_selection_service = GenerationInputImageSelectionService(
        input_canvas_plan_service=shell.input_canvas_plan_service,
        graph_section_service=shell.graph_section_service,
    )
    input_generation_image_materializer = InputGenerationImageMaterializer(
        canvas_io_service=shell.canvas_io_service,
        association_service=image_association_service,
        workflow_name_provider=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir_provider=lambda: Path(shell.path_bundle.projects_dir),
    )
    input_generation_mask_materializer = InputGenerationMaskMaterializer(
        canvas_io_service=shell.canvas_io_service,
        workflow_input_canvas_service=workflow_input_canvas_service,
        workflow_name_provider=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir_provider=lambda: Path(shell.path_bundle.projects_dir),
    )
    input_generation_snapshot_service = InputGenerationSnapshotService(
        capture_inputs=input_canvas.document.generation_capture.capture,
        select_generation_images=image_selection_service.select,
        image_materializer=input_generation_image_materializer,
        mask_materializer=input_generation_mask_materializer,
    )
    input_canvas_capability_service = InputCanvasCapabilityService(
        shell.input_canvas_plan_service,
        shell.graph_section_service,
    )
    synthetic_resolution_roles = SyntheticCanvasResolutionRoleService(
        shell.input_canvas_plan_service
    )
    synthetic_resolution_transactions = SyntheticCanvasResolutionTransactionService(
        roles=synthetic_resolution_roles,
        graph_sections=shell.graph_section_service,
    )
    synthetic_canvas_geometry = SyntheticCanvasGeometryAdapter(
        input_canvas.document.canvas,
        parent=input_canvas.document,
    )
    synthetic_resolution_controller = SyntheticCanvasResolutionController(
        geometry=synthetic_canvas_geometry,
        roles=synthetic_resolution_roles,
        transactions=synthetic_resolution_transactions,
        graph_sections=shell.graph_section_service,
        workflows=lambda: shell.workflow_session_service.workflows,
        modal_parent=lambda: shell,
        preset_source=lambda workflow_id: _dimension_presets_for(shell, workflow_id),
        refresh_editor=lambda workflow_id: _refresh_editor_after_resolution(
            shell,
            workflow_id,
        ),
        mark_changed=input_canvas_shell_adapter.mark_input_canvas_changed,
        request_autosave=shell.request_session_autosave,
        parent=shell,
    )
    composition = MainWindowInputCanvasComposition(
        workflow_input_canvas_service=workflow_input_canvas_service,
        input_canvas_tool_controller=input_canvas_tool_controller,
        input_canvas_tool_profile_controller=input_canvas_tool_profile_controller,
        input_shared_edge_resize_policy=input_shared_edge_resize_policy,
        input_scene_mapping_changes=input_scene_mapping_changes,
        input_canvas_shell_adapter=input_canvas_shell_adapter,
        input_canvas_presenter=input_canvas_presenter,
        input_node_interaction_controller=input_node_interaction_controller,
        input_mask_visual_opacity_controller=input_mask_visual_opacity_controller,
        input_document_change_observer=input_document_change_observer,
        input_editable_document_change_tracker=(input_editable_document_change_tracker),
        input_generation_snapshot_service=input_generation_snapshot_service,
        input_editable_document_lifecycle=input_editable_document_lifecycle,
        input_canvas_capability_service=input_canvas_capability_service,
        regional_interaction_coordinator=regional_interaction_coordinator,
        restored_ordered_mask_collections=restored_ordered_mask_collections,
        synthetic_canvas_resolution_role_service=synthetic_resolution_roles,
        synthetic_canvas_resolution_transaction_service=(
            synthetic_resolution_transactions
        ),
        synthetic_canvas_geometry_adapter=synthetic_canvas_geometry,
        synthetic_canvas_resolution_controller=synthetic_resolution_controller,
    )
    shell.workflow_input_canvas_service = composition.workflow_input_canvas_service
    shell.input_canvas_tool_controller = composition.input_canvas_tool_controller
    shell.input_canvas_tool_profile_controller = (
        composition.input_canvas_tool_profile_controller
    )
    shell.input_shared_edge_resize_policy = composition.input_shared_edge_resize_policy
    shell.input_scene_mapping_changes = composition.input_scene_mapping_changes
    shell.input_canvas_shell_adapter = composition.input_canvas_shell_adapter
    shell.input_canvas_presenter = composition.input_canvas_presenter
    shell.input_node_interaction_controller = (
        composition.input_node_interaction_controller
    )
    shell.input_mask_visual_opacity_controller = (
        composition.input_mask_visual_opacity_controller
    )
    shell.input_document_change_observer = composition.input_document_change_observer
    shell.input_editable_document_change_tracker = (
        composition.input_editable_document_change_tracker
    )
    shell.input_generation_snapshot_service = (
        composition.input_generation_snapshot_service
    )
    shell.input_editable_document_lifecycle = (
        composition.input_editable_document_lifecycle
    )
    shell.input_canvas_capability_service = composition.input_canvas_capability_service
    shell.regional_interaction_coordinator = (
        composition.regional_interaction_coordinator
    )
    shell.restored_ordered_mask_collections = (
        composition.restored_ordered_mask_collections
    )
    shell.synthetic_canvas_resolution_role_service = (
        composition.synthetic_canvas_resolution_role_service
    )
    shell.synthetic_canvas_resolution_transaction_service = (
        composition.synthetic_canvas_resolution_transaction_service
    )
    shell.synthetic_canvas_geometry_adapter = (
        composition.synthetic_canvas_geometry_adapter
    )
    shell.synthetic_canvas_resolution_controller = (
        composition.synthetic_canvas_resolution_controller
    )
    return composition


def _dimension_presets_for(shell: Any, workflow_id: str) -> Any:
    """Return the shared prepared preset source for one live editor panel."""

    panel = getattr(shell, "editor_panels", {}).get(workflow_id)
    return getattr(panel, "dimension_preset_source", None)


def _refresh_editor_after_resolution(shell: Any, workflow_id: str) -> None:
    """Reproject the active editor after an authoritative size mutation."""

    coordinator = getattr(shell, "workflow_workspace", None)
    if coordinator is not None:
        coordinator.project_workflow(
            workflow_id,
            force_refresh=True,
            source="synthetic_canvas_resolution",
        )


def _project_mask_visual_opacity(
    shell: Any,
    workflow_id: str,
    association_key: tuple[str, str],
    opacity: float,
) -> None:
    """Project one document-history value into its workflow's mounted node card."""

    panel = getattr(shell, "editor_panels", {}).get(workflow_id)
    if panel is not None:
        project_mask_visual_opacity_value(
            panel,
            cube_alias=association_key[0],
            node_name=association_key[1],
            opacity=opacity,
        )


__all__ = ["MainWindowInputCanvasComposition", "compose_input_canvas_controllers"]
