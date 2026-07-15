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

"""Workflow application services for session and tab orchestration."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.application.workflows.asset_reveal_service import AssetRevealService
    from substitute.application.workflows.canvas_image_registry import (
        CanvasImageRecord,
        CanvasImageRegistry,
    )
    from substitute.application.workflows.canvas_io_service import (
        CanvasIoService,
        ExternalImageEditorGateway,
    )
    from substitute.application.workflows.closed_workflow_buffer import (
        CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES,
        ClosedWorkflowBuffer,
        ClosedWorkflowPushResult,
        ClosedWorkflowRecord,
        ClosedWorkflowSummary,
    )
    from substitute.application.workflows.closed_workflow_snapshot_service import (
        ClosedWorkflowSnapshotError,
        ClosedWorkflowSnapshotService,
    )
    from substitute.application.workflows.cube_issue_diagnosis_service import (
        CubeIssueDiagnosisService,
    )
    from substitute.application.workflows.cube_duplication_service import (
        CubeDuplicationResult,
        CubeDuplicationService,
        CubeLinkReconcilerProtocol,
    )
    from substitute.application.workflows.cube_runtime_issues import (
        CubeRuntimeIssue,
        CubeRuntimeIssueKind,
        CubeRuntimeIssueSeverity,
        CubeRuntimeIssueSource,
        WorkflowIssueState,
        live_node_definition_error_to_cube_issues,
    )
    from substitute.application.workflows.input_canvas_capability_service import (
        InputCanvasCapabilityService,
    )
    from substitute.application.workflows.input_canvas_state_service import (
        InputCanvasStateService,
    )
    from substitute.application.workflows.node_link_endpoint_service import (
        NodeLinkEndpointService,
    )
    from substitute.application.workflows.node_link_group_service import (
        NodeLinkEndpointProvider,
        NodeLinkGroupService,
    )
    from substitute.application.workflows.output_canvas_projection import (
        OutputCanvasImageItem,
        OutputCanvasProjection,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
        build_output_canvas_projection,
    )
    from substitute.application.workflows.output_canvas_projection_coordinator import (
        OutputCanvasProjectionCoordinator,
        OutputProjectionCatalogWarmer,
        OutputProjectionPayloadHydrator,
    )
    from substitute.application.workflows.output_canvas_session import (
        OutputCanvasSession,
        OutputCanvasSessionBoundary,
        allowed_output_composition_ids,
        allowed_output_image_ids,
        allowed_output_scene_keys,
        allowed_output_source_keys,
        bind_output_canvas_session,
        deterministic_host_composition_id,
        output_route_identity_for_projection,
    )
    from substitute.application.workflows.output_canvas_state_service import (
        OutputCanvasStateService,
        OutputFocusMutationResult,
        OutputFocusSnapshot,
        OutputImageRegistrationResult,
        OutputPreviewCloseIdentity,
        OutputProjectionSchedulingIntent,
        OutputPruneResult,
        OutputTimingUpdateResult,
    )
    from substitute.application.workflows.output_compare_resolution import (
        default_output_compare_state,
        default_output_compare_state_for_context,
        output_compare_available,
        output_compare_candidates,
        output_compare_image_ids,
        reconcile_output_compare_state,
        resolve_output_compare_selection,
    )
    from substitute.application.workflows.output_compare_state import (
        OutputCompareSelection,
        OutputCompareState,
    )
    from substitute.application.workflows.output_preview_registry import (
        OutputPreviewAcceptance,
        OutputPreviewCloseResult,
        OutputPreviewLane,
        OutputPreviewLaneKey,
        OutputPreviewLanePlacement,
        OutputPreviewRegistry,
        OutputPreviewRejectionReason,
    )
    from substitute.application.workflows.output_scene_run_service import (
        OutputSceneRunService,
        SceneRunEntry,
        SceneRunState,
        SceneRunStatus,
    )
    from substitute.application.workflows.output_visual_events import (
        LiveFinalOutputEvent,
        LivePreviewEvent,
        OutputSceneIdentity,
        OutputVisualIdentity,
        PreviewNodeIdentity,
        SourceOnlyOutputIdentity,
    )
    from substitute.application.workflows.prompt_endpoint_service import (
        PromptEndpointService,
    )
    from substitute.application.workflows.prompt_link_group_service import (
        LegacyPromptLinkMigrationService,
        PromptEndpointProvider,
        PromptLinkGroupService,
    )
    from substitute.application.workflows.workflow_activity_service import (
        WorkflowActivityService,
    )
    from substitute.application.workflows.workflow_asset_service import (
        WorkflowAssetService,
    )
    from substitute.application.workflows.workflow_canvas_projection_coordinator import (
        WorkflowCanvasProjectionCoordinator,
    )
    from substitute.application.workflows.workflow_duplicate_service import (
        WorkflowDuplicateService,
    )
    from substitute.application.workflows.workflow_input_canvas_service import (
        InputCanvasMaterializationResult,
        LoadedInputCanvasImageIdentityResolution,
        MaskMaterializationResult,
        UserSelectedInputMaskResult,
        WorkflowInputCanvasService,
    )
    from substitute.application.workflows.workflow_link_reconciliation_service import (
        WorkflowLinkReconciliationService,
    )
    from substitute.application.workflows.workflow_session_service import (
        WorkflowActivationTransition,
        WorkflowCloseTransition,
        WorkflowCreationTransition,
        WorkflowRenameTransition,
        WorkflowSessionService,
        WorkflowSessionState,
    )
    from substitute.application.workflows.workflow_tab_service import (
        DEFAULT_WORKFLOW_TAB_LABEL,
        WorkflowInlineRenameDecision,
        WorkflowTabCreation,
        WorkflowTabService,
        is_default_workflow_tab_label,
        normalize_default_workflow_tab_label,
    )
    from substitute.domain.links import (
        NodeLinkEndpoint,
        NodeLinkEndpointIndex,
        NodeLinkIdentity,
        NodeLinkReference,
        PromptEndpoint,
        PromptEndpointIndex,
        update_node_link_references_on_rename,
    )
    from substitute.domain.workflow import (
        ComfyInputAssetRef,
        ImageMeta,
        LocalFileAssetRef,
        ProjectAssetRef,
        ProjectMaskAssetRef,
        WorkflowState,
    )

_EXPORT_MODULES = {
    "AssetRevealService": "substitute.application.workflows.asset_reveal_service",
    "CanvasIoService": "substitute.application.workflows.canvas_io_service",
    "CanvasImageRecord": "substitute.application.workflows.canvas_image_registry",
    "CanvasImageRegistry": "substitute.application.workflows.canvas_image_registry",
    "CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES": (
        "substitute.application.workflows.closed_workflow_buffer"
    ),
    "ClosedWorkflowBuffer": ("substitute.application.workflows.closed_workflow_buffer"),
    "ClosedWorkflowPushResult": (
        "substitute.application.workflows.closed_workflow_buffer"
    ),
    "ClosedWorkflowRecord": ("substitute.application.workflows.closed_workflow_buffer"),
    "ClosedWorkflowSnapshotError": (
        "substitute.application.workflows.closed_workflow_snapshot_service"
    ),
    "ClosedWorkflowSnapshotService": (
        "substitute.application.workflows.closed_workflow_snapshot_service"
    ),
    "ClosedWorkflowSummary": (
        "substitute.application.workflows.closed_workflow_buffer"
    ),
    "ComfyInputAssetRef": "substitute.domain.workflow",
    "CubeRuntimeIssue": "substitute.application.workflows.cube_runtime_issues",
    "CubeRuntimeIssueKind": "substitute.application.workflows.cube_runtime_issues",
    "CubeRuntimeIssueSeverity": (
        "substitute.application.workflows.cube_runtime_issues"
    ),
    "CubeRuntimeIssueSource": "substitute.application.workflows.cube_runtime_issues",
    "CubeIssueDiagnosisService": (
        "substitute.application.workflows.cube_issue_diagnosis_service"
    ),
    "CubeDuplicationResult": (
        "substitute.application.workflows.cube_duplication_service"
    ),
    "CubeDuplicationService": (
        "substitute.application.workflows.cube_duplication_service"
    ),
    "CubeLinkReconcilerProtocol": (
        "substitute.application.workflows.cube_duplication_service"
    ),
    "DEFAULT_WORKFLOW_TAB_LABEL": (
        "substitute.application.workflows.workflow_tab_service"
    ),
    "ExternalImageEditorGateway": (
        "substitute.application.workflows.canvas_io_service"
    ),
    "ImageMeta": "substitute.domain.workflow",
    "InputCanvasMaterializationResult": (
        "substitute.application.workflows.workflow_input_canvas_service"
    ),
    "InputCanvasCapabilityService": (
        "substitute.application.workflows.input_canvas_capability_service"
    ),
    "InputCanvasStateService": (
        "substitute.application.workflows.input_canvas_state_service"
    ),
    "LoadedInputCanvasImageIdentityResolution": (
        "substitute.application.workflows.workflow_input_canvas_service"
    ),
    "LiveFinalOutputEvent": "substitute.application.workflows.output_visual_events",
    "LivePreviewEvent": "substitute.application.workflows.output_visual_events",
    "MaskMaterializationResult": (
        "substitute.application.workflows.workflow_input_canvas_service"
    ),
    "NodeLinkEndpoint": "substitute.domain.links",
    "NodeLinkEndpointIndex": "substitute.domain.links",
    "NodeLinkEndpointProvider": (
        "substitute.application.workflows.node_link_group_service"
    ),
    "NodeLinkEndpointService": (
        "substitute.application.workflows.node_link_endpoint_service"
    ),
    "NodeLinkGroupService": (
        "substitute.application.workflows.node_link_group_service"
    ),
    "NodeLinkIdentity": "substitute.domain.links",
    "NodeLinkReference": "substitute.domain.links",
    "LegacyPromptLinkMigrationService": (
        "substitute.application.workflows.prompt_link_group_service"
    ),
    "LocalFileAssetRef": "substitute.domain.workflow",
    "update_node_link_references_on_rename": "substitute.domain.links",
    "OutputCanvasImageItem": (
        "substitute.application.workflows.output_canvas_projection"
    ),
    "OutputCanvasProjection": (
        "substitute.application.workflows.output_canvas_projection"
    ),
    "OutputCanvasProjectionCoordinator": (
        "substitute.application.workflows.output_canvas_projection_coordinator"
    ),
    "OutputCanvasSceneGroup": (
        "substitute.application.workflows.output_canvas_projection"
    ),
    "OutputCanvasSession": "substitute.application.workflows.output_canvas_session",
    "OutputCanvasSessionBoundary": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "OutputCanvasSourceGroup": (
        "substitute.application.workflows.output_canvas_projection"
    ),
    "OutputCanvasStateService": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "allowed_output_composition_ids": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "allowed_output_image_ids": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "allowed_output_scene_keys": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "allowed_output_source_keys": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "OutputCompareSelection": ("substitute.application.workflows.output_compare_state"),
    "OutputCompareState": "substitute.application.workflows.output_compare_state",
    "OutputFocusMutationResult": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputFocusSnapshot": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputImageRegistrationResult": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputPreviewCloseIdentity": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputPreviewAcceptance": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputPreviewCloseResult": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputPreviewLane": "substitute.application.workflows.output_preview_registry",
    "OutputPreviewLaneKey": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputPreviewLanePlacement": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputPreviewRegistry": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputPreviewRejectionReason": (
        "substitute.application.workflows.output_preview_registry"
    ),
    "OutputProjectionSchedulingIntent": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputProjectionCatalogWarmer": (
        "substitute.application.workflows.output_canvas_projection_coordinator"
    ),
    "OutputProjectionPayloadHydrator": (
        "substitute.application.workflows.output_canvas_projection_coordinator"
    ),
    "OutputPruneResult": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputSceneIdentity": "substitute.application.workflows.output_visual_events",
    "OutputSceneRunService": (
        "substitute.application.workflows.output_scene_run_service"
    ),
    "OutputTimingUpdateResult": (
        "substitute.application.workflows.output_canvas_state_service"
    ),
    "OutputVisualIdentity": "substitute.application.workflows.output_visual_events",
    "PreviewNodeIdentity": "substitute.application.workflows.output_visual_events",
    "PromptEndpoint": "substitute.domain.links",
    "PromptEndpointIndex": "substitute.domain.links",
    "PromptEndpointProvider": (
        "substitute.application.workflows.prompt_link_group_service"
    ),
    "PromptEndpointService": (
        "substitute.application.workflows.prompt_endpoint_service"
    ),
    "PromptLinkGroupService": (
        "substitute.application.workflows.prompt_link_group_service"
    ),
    "ProjectAssetRef": "substitute.domain.workflow",
    "ProjectMaskAssetRef": "substitute.domain.workflow",
    "SceneRunEntry": "substitute.application.workflows.output_scene_run_service",
    "SceneRunState": "substitute.application.workflows.output_scene_run_service",
    "SceneRunStatus": "substitute.application.workflows.output_scene_run_service",
    "SourceOnlyOutputIdentity": (
        "substitute.application.workflows.output_visual_events"
    ),
    "WorkflowActivationTransition": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowActivityService": (
        "substitute.application.workflows.workflow_activity_service"
    ),
    "WorkflowCanvasProjectionCoordinator": (
        "substitute.application.workflows.workflow_canvas_projection_coordinator"
    ),
    "WorkflowCloseTransition": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowCreationTransition": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowAssetService": ("substitute.application.workflows.workflow_asset_service"),
    "WorkflowDuplicateService": (
        "substitute.application.workflows.workflow_duplicate_service"
    ),
    "WorkflowInlineRenameDecision": (
        "substitute.application.workflows.workflow_tab_service"
    ),
    "WorkflowIssueState": "substitute.application.workflows.cube_runtime_issues",
    "live_node_definition_error_to_cube_issues": (
        "substitute.application.workflows.cube_runtime_issues"
    ),
    "WorkflowRenameTransition": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowSessionService": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowSessionState": (
        "substitute.application.workflows.workflow_session_service"
    ),
    "WorkflowState": "substitute.domain.workflow",
    "UserSelectedInputMaskResult": (
        "substitute.application.workflows.workflow_input_canvas_service"
    ),
    "WorkflowInputCanvasService": (
        "substitute.application.workflows.workflow_input_canvas_service"
    ),
    "WorkflowLinkReconciliationService": (
        "substitute.application.workflows.workflow_link_reconciliation_service"
    ),
    "WorkflowTabCreation": "substitute.application.workflows.workflow_tab_service",
    "WorkflowTabService": "substitute.application.workflows.workflow_tab_service",
    "build_output_canvas_projection": (
        "substitute.application.workflows.output_canvas_projection"
    ),
    "bind_output_canvas_session": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "default_output_compare_state": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "default_output_compare_state_for_context": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "deterministic_host_composition_id": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "is_default_workflow_tab_label": (
        "substitute.application.workflows.workflow_tab_service"
    ),
    "normalize_default_workflow_tab_label": (
        "substitute.application.workflows.workflow_tab_service"
    ),
    "output_compare_candidates": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "output_compare_available": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "output_compare_image_ids": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "output_route_identity_for_projection": (
        "substitute.application.workflows.output_canvas_session"
    ),
    "reconcile_output_compare_state": (
        "substitute.application.workflows.output_compare_resolution"
    ),
    "resolve_output_compare_selection": (
        "substitute.application.workflows.output_compare_resolution"
    ),
}

__all__ = [
    "AssetRevealService",
    "CanvasIoService",
    "CanvasImageRecord",
    "CanvasImageRegistry",
    "CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES",
    "ClosedWorkflowBuffer",
    "ClosedWorkflowPushResult",
    "ClosedWorkflowRecord",
    "ClosedWorkflowSnapshotError",
    "ClosedWorkflowSnapshotService",
    "ClosedWorkflowSummary",
    "ComfyInputAssetRef",
    "CubeDuplicationResult",
    "CubeDuplicationService",
    "CubeLinkReconcilerProtocol",
    "CubeRuntimeIssue",
    "CubeRuntimeIssueKind",
    "CubeRuntimeIssueSeverity",
    "CubeRuntimeIssueSource",
    "CubeIssueDiagnosisService",
    "DEFAULT_WORKFLOW_TAB_LABEL",
    "ExternalImageEditorGateway",
    "ImageMeta",
    "InputCanvasMaterializationResult",
    "InputCanvasCapabilityService",
    "InputCanvasStateService",
    "LoadedInputCanvasImageIdentityResolution",
    "LiveFinalOutputEvent",
    "LivePreviewEvent",
    "MaskMaterializationResult",
    "NodeLinkEndpoint",
    "NodeLinkEndpointIndex",
    "NodeLinkEndpointProvider",
    "NodeLinkEndpointService",
    "NodeLinkGroupService",
    "NodeLinkIdentity",
    "NodeLinkReference",
    "LegacyPromptLinkMigrationService",
    "LocalFileAssetRef",
    "update_node_link_references_on_rename",
    "OutputCanvasImageItem",
    "OutputCanvasProjection",
    "OutputCanvasProjectionCoordinator",
    "OutputCanvasSceneGroup",
    "OutputCanvasSession",
    "OutputCanvasSessionBoundary",
    "OutputCanvasSourceGroup",
    "OutputCanvasStateService",
    "allowed_output_composition_ids",
    "allowed_output_image_ids",
    "allowed_output_scene_keys",
    "allowed_output_source_keys",
    "OutputCompareSelection",
    "OutputCompareState",
    "OutputFocusMutationResult",
    "OutputFocusSnapshot",
    "OutputImageRegistrationResult",
    "OutputPreviewCloseIdentity",
    "OutputPreviewAcceptance",
    "OutputPreviewCloseResult",
    "OutputPreviewLane",
    "OutputPreviewLaneKey",
    "OutputPreviewLanePlacement",
    "OutputPreviewRegistry",
    "OutputPreviewRejectionReason",
    "OutputProjectionSchedulingIntent",
    "OutputProjectionCatalogWarmer",
    "OutputProjectionPayloadHydrator",
    "OutputPruneResult",
    "OutputSceneIdentity",
    "OutputSceneRunService",
    "OutputTimingUpdateResult",
    "OutputVisualIdentity",
    "PreviewNodeIdentity",
    "PromptEndpoint",
    "PromptEndpointIndex",
    "PromptEndpointProvider",
    "PromptEndpointService",
    "PromptLinkGroupService",
    "ProjectAssetRef",
    "ProjectMaskAssetRef",
    "SceneRunEntry",
    "SceneRunState",
    "SceneRunStatus",
    "SourceOnlyOutputIdentity",
    "WorkflowActivationTransition",
    "WorkflowActivityService",
    "WorkflowCanvasProjectionCoordinator",
    "WorkflowCloseTransition",
    "WorkflowCreationTransition",
    "WorkflowAssetService",
    "WorkflowDuplicateService",
    "WorkflowInlineRenameDecision",
    "WorkflowIssueState",
    "live_node_definition_error_to_cube_issues",
    "WorkflowRenameTransition",
    "WorkflowSessionService",
    "WorkflowSessionState",
    "WorkflowState",
    "UserSelectedInputMaskResult",
    "WorkflowInputCanvasService",
    "WorkflowLinkReconciliationService",
    "WorkflowTabCreation",
    "WorkflowTabService",
    "build_output_canvas_projection",
    "bind_output_canvas_session",
    "default_output_compare_state",
    "default_output_compare_state_for_context",
    "deterministic_host_composition_id",
    "is_default_workflow_tab_label",
    "normalize_default_workflow_tab_label",
    "output_compare_available",
    "output_compare_candidates",
    "output_compare_image_ids",
    "output_route_identity_for_projection",
    "reconcile_output_compare_state",
    "resolve_output_compare_selection",
]


def __getattr__(name: str) -> object:
    """Load public workflow exports only when callers request them."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return stable lazy-export names for interactive inspection."""

    return sorted({*globals(), *__all__})
