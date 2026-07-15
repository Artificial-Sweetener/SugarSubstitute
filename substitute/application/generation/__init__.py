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

"""Expose generation application services without eager facade imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.application.generation.asset_staging_service import (
        ComfyAssetStagingResult,
        ComfyAssetStagingService,
    )
    from substitute.application.generation.duration_formatting import (
        format_generation_duration,
    )
    from substitute.application.generation.failure_summary import (
        format_generation_failure_line,
        summarize_generation_failure,
    )
    from substitute.application.generation.generation_models import (
        GenerationCallbacks,
        GenerationFailure,
        GenerationRunStarted,
        GenerationStartResult,
        PreparedGenerationRequest,
    )
    from substitute.application.generation.generation_preparation_input import (
        CapturedGenerationRequest,
    )
    from substitute.application.generation.generation_preparation_service import (
        GenerationPreparationResult,
        GenerationPreparationService,
    )
    from substitute.application.generation.generation_result_snapshot_service import (
        GenerationResultSnapshotBuildResult,
        GenerationResultSnapshotService,
        LiveGenerationResultLookup,
    )
    from substitute.application.generation.generation_service import (
        GenerationRequest,
        GenerationService,
        find_unresolved_uuid_class_types,
    )
    from substitute.application.generation.job_queue_service import (
        GenerationJobLifecycleAction,
        GenerationJobLifecycleEvent,
        GenerationJobLifecycleObserver,
        GenerationJobQueueService,
        GenerationQueueBatchEntry,
        GenerationQueueChangeKind,
        GenerationQueueStateChange,
        OutputRunProjectionCacheKeyProvider,
        QueueBatchContext,
        QueueProjectionCacheKey,
    )
    from substitute.application.generation.live_event_projection import (
        LiveEventSceneFields,
        live_event_scene_fields,
    )
    from substitute.application.generation.output_organization_service import (
        OutputOrganizationPreferenceService,
        OutputOrganizationSaveResult,
    )
    from substitute.application.generation.output_path_template_renderer import (
        OutputPathTemplateError,
        OutputPathTemplateRenderer,
    )
    from substitute.application.generation.positive_prompt_preview import (
        positive_prompt_preview_from_prompt_overrides,
        positive_prompt_preview_from_workflow,
        prompt_preview_text,
    )
    from substitute.application.generation.preview_preference_service import (
        GenerationPreviewMethodResolver,
        GenerationPreviewPreferenceService,
        GenerationPreviewSaveResult,
        PreviewAssetBackend,
    )
    from substitute.application.generation.progress_service import (
        ModelLoadProgressViewState,
        ProgressService,
        ProgressViewState,
    )
    from substitute.application.generation.prompt_scene_materialization_service import (
        PromptSceneMaterializationCube,
        PromptSceneMaterializationService,
        PromptSceneMaterializationWorkflow,
    )
    from substitute.application.generation.prompt_scene_preparation_plan import (
        PromptFieldIdentity,
        PromptSceneFieldPlan,
        PromptScenePreparationCube,
        PromptScenePreparationPlan,
        PromptScenePreparationPlanBuilder,
        PromptScenePreparationWorkflow,
    )
    from substitute.application.generation.recipe_output_sibling_discovery_service import (
        RecipeOutputSibling,
        RecipeOutputSiblingDiscoveryResult,
        RecipeOutputSiblingDiscoveryService,
    )
    from substitute.application.generation.seed_randomization_service import (
        SeedRandomizationResult,
        SeedRandomizationService,
        SeedValueChange,
    )
    from substitute.application.generation.visual_authorization import (
        AcceptedVisualRun,
        VisualAuthorizationService,
        VisualRunState,
    )
    from substitute.application.generation.workflow_issue_pruning_service import (
        WorkflowIssuePruningService,
    )
    from substitute.application.generation.workflow_progress_service import (
        GenerationProgressRetirementReason,
        WorkflowProgressIdentity,
        WorkflowProgressService,
        WorkflowProgressState,
    )
    from substitute.domain.generation import (
        TERMINAL_GENERATION_JOB_STATUSES,
        GenerationCubeExecutionDuration,
        GenerationJobSnapshot,
        GenerationJobStatus,
        GenerationPreviewMethod,
        GenerationPreviewPreferences,
        GenerationQueueJob,
        OutputOrganizationPreferences,
        OutputPathRenderContext,
        OutputPathRenderResult,
        TaesdPreviewAssetStatus,
    )

_LAZY_EXPORTS = {
    "AcceptedVisualRun": "substitute.application.generation.visual_authorization",
    "ComfyAssetStagingResult": (
        "substitute.application.generation.asset_staging_service"
    ),
    "ComfyAssetStagingService": (
        "substitute.application.generation.asset_staging_service"
    ),
    "format_generation_duration": (
        "substitute.application.generation.duration_formatting"
    ),
    "format_generation_failure_line": (
        "substitute.application.generation.failure_summary"
    ),
    "GenerationCallbacks": "substitute.application.generation.generation_models",
    "GenerationCubeExecutionDuration": "substitute.domain.generation",
    "GenerationFailure": "substitute.application.generation.generation_models",
    "GenerationJobLifecycleAction": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationJobLifecycleEvent": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationJobLifecycleObserver": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationJobQueueService": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationJobSnapshot": "substitute.domain.generation",
    "GenerationJobStatus": "substitute.domain.generation",
    "GenerationPreparationResult": (
        "substitute.application.generation.generation_preparation_service"
    ),
    "GenerationPreparationService": (
        "substitute.application.generation.generation_preparation_service"
    ),
    "GenerationPreviewMethod": "substitute.domain.generation",
    "GenerationPreviewMethodResolver": (
        "substitute.application.generation.preview_preference_service"
    ),
    "GenerationPreviewPreferenceService": (
        "substitute.application.generation.preview_preference_service"
    ),
    "GenerationPreviewPreferences": "substitute.domain.generation",
    "GenerationPreviewSaveResult": (
        "substitute.application.generation.preview_preference_service"
    ),
    "GenerationProgressRetirementReason": (
        "substitute.application.generation.workflow_progress_service"
    ),
    "GenerationQueueBatchEntry": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationQueueChangeKind": "substitute.application.generation.job_queue_service",
    "GenerationQueueJob": "substitute.domain.generation",
    "GenerationQueueStateChange": (
        "substitute.application.generation.job_queue_service"
    ),
    "GenerationRequest": "substitute.application.generation.generation_service",
    "GenerationResultSnapshotBuildResult": (
        "substitute.application.generation.generation_result_snapshot_service"
    ),
    "GenerationResultSnapshotService": (
        "substitute.application.generation.generation_result_snapshot_service"
    ),
    "GenerationRunStarted": "substitute.application.generation.generation_models",
    "GenerationService": "substitute.application.generation.generation_service",
    "GenerationStartResult": "substitute.application.generation.generation_models",
    "LiveEventSceneFields": ("substitute.application.generation.live_event_projection"),
    "LiveGenerationResultLookup": (
        "substitute.application.generation.generation_result_snapshot_service"
    ),
    "live_event_scene_fields": (
        "substitute.application.generation.live_event_projection"
    ),
    "ModelLoadProgressViewState": (
        "substitute.application.generation.progress_service"
    ),
    "OutputOrganizationPreferenceService": (
        "substitute.application.generation.output_organization_service"
    ),
    "OutputOrganizationPreferences": "substitute.domain.generation",
    "OutputOrganizationSaveResult": (
        "substitute.application.generation.output_organization_service"
    ),
    "OutputRunProjectionCacheKeyProvider": (
        "substitute.application.generation.job_queue_service"
    ),
    "OutputPathRenderContext": "substitute.domain.generation",
    "OutputPathRenderResult": "substitute.domain.generation",
    "OutputPathTemplateError": (
        "substitute.application.generation.output_path_template_renderer"
    ),
    "OutputPathTemplateRenderer": (
        "substitute.application.generation.output_path_template_renderer"
    ),
    "PreparedGenerationRequest": (
        "substitute.application.generation.generation_models"
    ),
    "PreviewAssetBackend": (
        "substitute.application.generation.preview_preference_service"
    ),
    "ProgressService": "substitute.application.generation.progress_service",
    "ProgressViewState": "substitute.application.generation.progress_service",
    "PromptSceneMaterializationCube": (
        "substitute.application.generation.prompt_scene_materialization_service"
    ),
    "PromptSceneMaterializationService": (
        "substitute.application.generation.prompt_scene_materialization_service"
    ),
    "PromptSceneMaterializationWorkflow": (
        "substitute.application.generation.prompt_scene_materialization_service"
    ),
    "PromptFieldIdentity": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "PromptSceneFieldPlan": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "PromptScenePreparationCube": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "PromptScenePreparationPlan": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "PromptScenePreparationPlanBuilder": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "PromptScenePreparationWorkflow": (
        "substitute.application.generation.prompt_scene_preparation_plan"
    ),
    "QueueBatchContext": "substitute.application.generation.job_queue_service",
    "QueueProjectionCacheKey": "substitute.application.generation.job_queue_service",
    "RecipeOutputSibling": (
        "substitute.application.generation.recipe_output_sibling_discovery_service"
    ),
    "RecipeOutputSiblingDiscoveryResult": (
        "substitute.application.generation.recipe_output_sibling_discovery_service"
    ),
    "RecipeOutputSiblingDiscoveryService": (
        "substitute.application.generation.recipe_output_sibling_discovery_service"
    ),
    "SeedRandomizationService": (
        "substitute.application.generation.seed_randomization_service"
    ),
    "SeedRandomizationResult": (
        "substitute.application.generation.seed_randomization_service"
    ),
    "SeedValueChange": ("substitute.application.generation.seed_randomization_service"),
    "TERMINAL_GENERATION_JOB_STATUSES": "substitute.domain.generation",
    "TaesdPreviewAssetStatus": "substitute.domain.generation",
    "VisualAuthorizationService": (
        "substitute.application.generation.visual_authorization"
    ),
    "VisualRunState": "substitute.application.generation.visual_authorization",
    "WorkflowIssuePruningService": (
        "substitute.application.generation.workflow_issue_pruning_service"
    ),
    "WorkflowProgressIdentity": (
        "substitute.application.generation.workflow_progress_service"
    ),
    "WorkflowProgressService": (
        "substitute.application.generation.workflow_progress_service"
    ),
    "WorkflowProgressState": (
        "substitute.application.generation.workflow_progress_service"
    ),
    "CapturedGenerationRequest": (
        "substitute.application.generation.generation_preparation_input"
    ),
    "find_unresolved_uuid_class_types": (
        "substitute.application.generation.generation_service"
    ),
    "positive_prompt_preview_from_workflow": (
        "substitute.application.generation.positive_prompt_preview"
    ),
    "positive_prompt_preview_from_prompt_overrides": (
        "substitute.application.generation.positive_prompt_preview"
    ),
    "prompt_preview_text": (
        "substitute.application.generation.positive_prompt_preview"
    ),
    "summarize_generation_failure": (
        "substitute.application.generation.failure_summary"
    ),
}


def __getattr__(name: str) -> object:
    """Load one exported generation application symbol on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "GenerationCallbacks",
    "ComfyAssetStagingResult",
    "ComfyAssetStagingService",
    "AcceptedVisualRun",
    "format_generation_duration",
    "format_generation_failure_line",
    "live_event_scene_fields",
    "GenerationFailure",
    "GenerationCubeExecutionDuration",
    "GenerationQueueChangeKind",
    "GenerationJobLifecycleAction",
    "GenerationJobLifecycleEvent",
    "GenerationJobLifecycleObserver",
    "GenerationJobQueueService",
    "GenerationQueueBatchEntry",
    "GenerationQueueStateChange",
    "GenerationResultSnapshotBuildResult",
    "GenerationResultSnapshotService",
    "LiveGenerationResultLookup",
    "LiveEventSceneFields",
    "GenerationJobSnapshot",
    "GenerationJobStatus",
    "GenerationPreviewMethod",
    "GenerationPreviewMethodResolver",
    "GenerationPreviewPreferenceService",
    "GenerationPreviewPreferences",
    "GenerationPreviewSaveResult",
    "CapturedGenerationRequest",
    "GenerationPreparationResult",
    "GenerationPreparationService",
    "GenerationQueueJob",
    "GenerationRequest",
    "GenerationRunStarted",
    "GenerationService",
    "GenerationStartResult",
    "PreparedGenerationRequest",
    "PromptSceneMaterializationCube",
    "PromptSceneMaterializationService",
    "PromptSceneMaterializationWorkflow",
    "PromptFieldIdentity",
    "PromptSceneFieldPlan",
    "PromptScenePreparationCube",
    "PromptScenePreparationPlan",
    "PromptScenePreparationPlanBuilder",
    "PromptScenePreparationWorkflow",
    "WorkflowIssuePruningService",
    "GenerationProgressRetirementReason",
    "WorkflowProgressIdentity",
    "WorkflowProgressService",
    "WorkflowProgressState",
    "ModelLoadProgressViewState",
    "OutputOrganizationPreferenceService",
    "OutputOrganizationPreferences",
    "OutputOrganizationSaveResult",
    "OutputRunProjectionCacheKeyProvider",
    "OutputPathRenderContext",
    "OutputPathRenderResult",
    "OutputPathTemplateError",
    "OutputPathTemplateRenderer",
    "RecipeOutputSibling",
    "RecipeOutputSiblingDiscoveryResult",
    "RecipeOutputSiblingDiscoveryService",
    "SeedRandomizationService",
    "SeedRandomizationResult",
    "SeedValueChange",
    "ProgressService",
    "ProgressViewState",
    "PreviewAssetBackend",
    "QueueBatchContext",
    "QueueProjectionCacheKey",
    "VisualAuthorizationService",
    "VisualRunState",
    "TERMINAL_GENERATION_JOB_STATUSES",
    "TaesdPreviewAssetStatus",
    "find_unresolved_uuid_class_types",
    "positive_prompt_preview_from_workflow",
    "positive_prompt_preview_from_prompt_overrides",
    "prompt_preview_text",
    "summarize_generation_failure",
]
