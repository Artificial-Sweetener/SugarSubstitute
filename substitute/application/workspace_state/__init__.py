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

"""Expose workspace state restoration application services."""

from __future__ import annotations

from substitute.application.workspace_state.snapshot_normalization_service import (
    SnapshotNormalizationResult,
    SnapshotNormalizationService,
)
from substitute.application.workspace_state.initial_restore_plan import (
    InitialShellPlacement,
    InitialWorkspaceRestorePlan,
    InitialWorkspaceRestorePlanService,
)
from substitute.application.workspace_state.session_autosave_service import (
    SessionCaptureServiceProtocol,
    SessionAutosaveService,
)
from substitute.application.workspace_state.snapshot_capture_service import (
    SnapshotCapturePort,
    SnapshotCaptureService,
)
from substitute.application.workspace_state.workspace_materialization_service import (
    SnapshotRestoreResult,
    WorkspaceMaterializationPort,
    WorkspaceMaterializationService,
)
from substitute.application.workspace_state.workspace_append_service import (
    WorkspaceAppendService,
)
from substitute.application.workspace_state.workspace_runtime_hydration_service import (
    CubeRuntimeLoadServiceProtocol,
    NodeBehaviorRuntimeServiceProtocol,
    WorkspaceRuntimeHydrationResult,
    WorkspaceRuntimeHydrationService,
    restore_cube_buffer_patch,
)
from substitute.application.workspace_state.restored_cube_definition_warmup_service import (
    RestoredCubeDefinitionLoadServiceProtocol,
    RestoredCubeDefinitionWarmupFailure,
    RestoredCubeDefinitionWarmupResult,
    RestoredCubeDefinitionWarmupService,
)
from substitute.application.workspace_state.restore_projection_identity import (
    cube_definition_fingerprint,
    fingerprint_json,
    node_definition_fingerprint,
    prompt_feature_profile_fingerprint,
    workspace_projection_fingerprint,
)
from substitute.application.workspace_state.restore_projection_backend_identity import (
    RestoreProjectionBackendIdentity,
    RestoreProjectionBackendIdentityService,
    RestoreProjectionCubeLoader,
    RestoreProjectionNodeDefinitionGateway,
)
from substitute.application.workspace_state.restore_projection_codec import (
    restore_projection_artifact_from_json,
    restore_projection_artifact_to_json,
)
from substitute.application.workspace_state.restore_projection_models import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedCubeStackProjection,
    CachedDirectWorkflowProjection,
    CachedEditorSectionProjection,
    CachedNodeProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
    RestoreProjectionCacheKey,
    RestoreProjectionCacheRepository,
)
from substitute.application.workspace_state.restore_projection_validation import (
    RestoreProjectionCacheState,
    RestoreProjectionInvalidation,
    RestoreProjectionValidationResult,
    RestoreProjectionValidationService,
)
from substitute.application.workspace_state.restored_editor_projection import (
    RestoredEditorProjectionCacheExtractor,
)
from substitute.application.workspace_state.workspace_prehydration_service import (
    WorkspacePrehydrationPort,
    WorkspacePrehydrationResult,
    WorkspacePrehydrationService,
)
from substitute.domain.workspace_snapshot import (
    CanvasLayoutSnapshot,
    EditorViewportSnapshot,
    FloatingCanvasWindowSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)

__all__ = [
    "CanvasLayoutSnapshot",
    "EditorViewportSnapshot",
    "FloatingCanvasWindowSnapshot",
    "ImageMetaSnapshot",
    "InitialShellPlacement",
    "InitialWorkspaceRestorePlan",
    "InitialWorkspaceRestorePlanService",
    "InputImageReference",
    "InputMaskReference",
    "OutputImageReference",
    "ShellLayoutSnapshot",
    "SnapshotNormalizationResult",
    "SnapshotRestoreResult",
    "SessionCaptureServiceProtocol",
    "SessionAutosaveService",
    "SnapshotCapturePort",
    "SnapshotCaptureService",
    "SnapshotNormalizationService",
    "WindowGeometrySnapshot",
    "WorkflowSnapshot",
    "WorkspaceSnapshot",
    "WorkspaceMaterializationPort",
    "WorkspaceMaterializationService",
    "WorkspaceAppendService",
    "CubeRuntimeLoadServiceProtocol",
    "NodeBehaviorRuntimeServiceProtocol",
    "WorkspaceRuntimeHydrationResult",
    "WorkspaceRuntimeHydrationService",
    "restore_cube_buffer_patch",
    "RestoredCubeDefinitionLoadServiceProtocol",
    "RestoredCubeDefinitionWarmupFailure",
    "RestoredCubeDefinitionWarmupResult",
    "RestoredCubeDefinitionWarmupService",
    "WorkspacePrehydrationPort",
    "WorkspacePrehydrationResult",
    "WorkspacePrehydrationService",
    "APP_PROJECTION_VERSION",
    "RESTORE_PROJECTION_CACHE_SCHEMA_VERSION",
    "CachedCubeProjection",
    "CachedCubeStackProjection",
    "CachedDirectWorkflowProjection",
    "CachedEditorSectionProjection",
    "CachedNodeProjection",
    "CachedWorkflowProjection",
    "RestoreProjectionArtifact",
    "RestoreProjectionBackendIdentity",
    "RestoreProjectionBackendIdentityService",
    "RestoreProjectionCubeLoader",
    "RestoreProjectionNodeDefinitionGateway",
    "RestoreProjectionCacheKey",
    "RestoreProjectionCacheRepository",
    "RestoreProjectionCacheState",
    "RestoreProjectionInvalidation",
    "RestoreProjectionValidationResult",
    "RestoreProjectionValidationService",
    "restore_projection_artifact_from_json",
    "restore_projection_artifact_to_json",
    "RestoredEditorProjectionCacheExtractor",
    "cube_definition_fingerprint",
    "fingerprint_json",
    "node_definition_fingerprint",
    "prompt_feature_profile_fingerprint",
    "workspace_projection_fingerprint",
]
