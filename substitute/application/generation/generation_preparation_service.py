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

"""Prepare immutable generation queue snapshots from captured workflow state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from inspect import signature
from time import perf_counter
from typing import Any, Protocol, cast
from uuid import uuid4

from substitute.application.generation.generation_preparation_input import (
    CapturedGenerationRequest,
)
from substitute.application.direct_workflows import (
    DirectWorkflowGenerationPlanService,
    DirectWorkflowScenePreparationService,
)
from substitute.application.generation.positive_prompt_preview import (
    positive_prompt_preview_from_prompt_overrides,
)
from substitute.application.generation.prompt_scene_preparation_plan import (
    PromptScenePreparationPlan,
    PromptScenePreparationPlanBuilder,
)
from substitute.application.prompt_editor import (
    PromptSceneAnalysisService,
    WorkflowScene,
    WorkflowSceneAnalysis,
)
from substitute.application.prompt_wildcards import PromptWildcardPreprocessingContext
from substitute.application.recipes.recipe_serialization_context import (
    RecipeSerializationContext,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.domain.comfy_workflow import (
    DirectWorkflowGenerationPlan,
    DirectWorkflowState,
)
from substitute.domain.links import PromptEndpointIndex
from substitute.shared.logging.logger import get_logger, log_debug, log_timing

_LOGGER = get_logger("application.generation.generation_preparation_service")


class GenerationPromptWildcardPreprocessor(Protocol):
    """Resolve prompt wildcard overlays for captured generation workflows."""

    def resolve_workflow_prompt_field_overrides(
        self,
        *,
        workflow: object,
        workflow_id: str,
        prompt_field_overrides: Mapping[tuple[str, str, str], str] | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return prompt-field values with wildcard preprocessing applied."""


@dataclass(frozen=True, slots=True)
class GenerationPreparationResult:
    """Carry prepared queue snapshots and multi-scene run metadata."""

    snapshots: tuple[GenerationJobSnapshot, ...]
    scene_run_id: str | None = None
    scene_count: int | None = None


class GenerationPreparationService:
    """Prepare immutable queue snapshots from captured workflow state."""

    def __init__(
        self,
        *,
        recipe_io_service: object,
        prompt_wildcard_preprocessing_service: (
            GenerationPromptWildcardPreprocessor | None
        ) = None,
        direct_workflow_graph_service: DirectWorkflowGenerationPlanService
        | None = None,
    ) -> None:
        """Store application services used by generation preparation."""

        self._recipe_io_service = recipe_io_service
        self._prompt_wildcard_preprocessing_service = (
            prompt_wildcard_preprocessing_service
        )
        self._scene_analysis_service = PromptSceneAnalysisService()
        self._scene_plan_builder = PromptScenePreparationPlanBuilder()
        self._direct_workflow_graph_service = (
            direct_workflow_graph_service or DirectWorkflowGenerationPlanService()
        )
        self._direct_scene_preparation_service = DirectWorkflowScenePreparationService(
            wildcard_preprocessor=prompt_wildcard_preprocessing_service
        )

    def prepare_queued_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_run_id: str | None = None,
    ) -> GenerationPreparationResult:
        """Return prepared snapshots for one queued generation request."""

        started_at = perf_counter()
        log_debug(
            _LOGGER,
            "Generation preparation started.",
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
        )
        result = self._prepare_queued_snapshots(
            request=request,
            scene_run_id=scene_run_id,
        )
        log_timing(
            _LOGGER,
            "Generation preparation completed.",
            started_at=started_at,
            level="debug",
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
            scene_count=result.scene_count or 0,
            snapshot_count=len(result.snapshots),
        )
        return result

    def _prepare_queued_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_run_id: str | None,
    ) -> GenerationPreparationResult:
        """Prepare queued snapshots without presentation-thread logging concerns."""

        behavior_snapshot = request.behavior_snapshot
        direct_document = getattr(request.workflow, "direct_workflow", None)
        direct_plan = (
            self._direct_workflow_graph_service.build(direct_document)
            if isinstance(direct_document, DirectWorkflowState)
            else None
        )
        if isinstance(direct_document, DirectWorkflowState) and direct_plan is not None:
            if behavior_snapshot is None:
                return self._single_direct_result(request, direct_plan)
            scene_analysis = self._direct_scene_preparation_service.analyze(
                document=direct_document,
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
            )
            if len(scene_analysis.scenes) <= 1:
                return self._single_direct_result(request, direct_plan)
            direct_result = self._direct_scene_preparation_service.prepare_all(
                document=direct_document,
                plan=direct_plan,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
                scene_analysis=scene_analysis,
                scene_run_id=scene_run_id,
            )
            return GenerationPreparationResult(
                snapshots=direct_result.snapshots,
                scene_run_id=direct_result.scene_run_id,
                scene_count=direct_result.scene_count,
            )
        if behavior_snapshot is None:
            return GenerationPreparationResult(
                snapshots=(self._prepare_single_snapshot(request=request),)
            )

        scene_analysis = self._scene_analysis_service.analyze(
            workflow=cast(Any, request.workflow),
            endpoint_index=behavior_snapshot.prompt_endpoint_index,
        )
        if len(scene_analysis.scenes) <= 1:
            return GenerationPreparationResult(
                snapshots=(self._prepare_single_snapshot(request=request),)
            )
        return self.prepare_scene_snapshots(
            request=request,
            scene_analysis=scene_analysis,
            scene_run_id=scene_run_id,
        )

    def prepare_scene_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_analysis: WorkflowSceneAnalysis | None = None,
        scene_run_id: str | None = None,
    ) -> GenerationPreparationResult:
        """Return one prepared snapshot for each runnable scene."""

        behavior_snapshot = request.behavior_snapshot
        if behavior_snapshot is None:
            raise ValueError("Scene generation requires a prompt endpoint index.")
        direct_document = getattr(request.workflow, "direct_workflow", None)
        if isinstance(direct_document, DirectWorkflowState):
            direct_plan = self._direct_workflow_graph_service.build(direct_document)
            resolved_analysis = scene_analysis or (
                self._direct_scene_preparation_service.analyze(
                    document=direct_document,
                    endpoint_index=behavior_snapshot.prompt_endpoint_index,
                )
            )
            direct_result = self._direct_scene_preparation_service.prepare_all(
                document=direct_document,
                plan=direct_plan,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
                scene_analysis=resolved_analysis,
                scene_run_id=scene_run_id,
            )
            return GenerationPreparationResult(
                snapshots=direct_result.snapshots,
                scene_run_id=direct_result.scene_run_id,
                scene_count=direct_result.scene_count,
            )
        resolved_scene_analysis = (
            scene_analysis
            or self._scene_analysis_service.analyze(
                workflow=cast(Any, request.workflow),
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
            )
        )
        if not resolved_scene_analysis.can_generate_scenes:
            raise ValueError("Scene generation requires at least one runnable scene.")
        resolved_scene_run_id = scene_run_id or uuid4().hex
        preparation_state = self._preparation_state(request)
        scene_plan = self._scene_plan(
            request=request,
            scene_analysis=resolved_scene_analysis,
        )
        snapshots = tuple(
            self._prepare_scene_snapshot(
                request=request,
                scene_analysis=resolved_scene_analysis,
                scene_plan=scene_plan,
                scene=scene,
                scene_run_id=resolved_scene_run_id,
                preparation_state=preparation_state,
            )
            for scene in resolved_scene_analysis.scenes
        )
        self._log_preparation_cache_stats(
            request=request,
            preparation_state=preparation_state,
            scene_count=len(resolved_scene_analysis.scenes),
            prompt_scene_field_count=len(scene_plan.fields),
        )
        return GenerationPreparationResult(
            snapshots=snapshots,
            scene_run_id=resolved_scene_run_id,
            scene_count=len(resolved_scene_analysis.scenes),
        )

    def prepare_scene_snapshot(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_key: str,
        scene_run_id: str | None = None,
    ) -> GenerationJobSnapshot:
        """Return one prepared snapshot for a selected runnable scene."""

        behavior_snapshot = request.behavior_snapshot
        if behavior_snapshot is None:
            raise ValueError("Scene generation requires a prompt endpoint index.")
        direct_document = getattr(request.workflow, "direct_workflow", None)
        if isinstance(direct_document, DirectWorkflowState):
            direct_plan = self._direct_workflow_graph_service.build(direct_document)
            direct_analysis = self._direct_scene_preparation_service.analyze(
                document=direct_document,
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
            )
            return self._direct_scene_preparation_service.prepare_one(
                document=direct_document,
                plan=direct_plan,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                endpoint_index=behavior_snapshot.prompt_endpoint_index,
                scene_analysis=direct_analysis,
                scene_key=scene_key,
                scene_run_id=scene_run_id,
            )
        scene_analysis = self._scene_analysis_service.analyze(
            workflow=cast(Any, request.workflow),
            endpoint_index=behavior_snapshot.prompt_endpoint_index,
        )
        scene = _scene_for_key(scene_analysis=scene_analysis, scene_key=scene_key)
        preparation_state = self._preparation_state(request)
        scene_plan = self._scene_plan(request=request, scene_analysis=scene_analysis)
        snapshot = self._prepare_scene_snapshot(
            request=request,
            scene_analysis=scene_analysis,
            scene_plan=scene_plan,
            scene=scene,
            scene_run_id=scene_run_id or uuid4().hex,
            preparation_state=preparation_state,
        )
        self._log_preparation_cache_stats(
            request=request,
            preparation_state=preparation_state,
            scene_count=1,
            prompt_scene_field_count=len(scene_plan.fields),
        )
        return snapshot

    def _prepare_single_snapshot(
        self,
        *,
        request: CapturedGenerationRequest,
    ) -> GenerationJobSnapshot:
        """Prepare one non-scene queue snapshot from captured workflow state."""

        preparation_state = self._preparation_state(request)
        prompt_overrides = self._resolve_prompt_overrides(
            request=request,
            prompt_field_overrides=None,
            preprocessing_context=preparation_state.preprocessing_context,
        )
        positive_prompt_preview = positive_prompt_preview_from_prompt_overrides(
            workflow=request.workflow,
            behavior_snapshot=request.behavior_snapshot,
            prompt_field_overrides=prompt_overrides,
        )
        sugar_script_text = self._serialize(
            request=request,
            preparation_state=preparation_state,
            prompt_field_overrides=prompt_overrides,
        )
        snapshot = GenerationJobSnapshot(
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
            sugar_script_text=sugar_script_text,
            positive_prompt_preview=positive_prompt_preview,
        )
        self._log_preparation_cache_stats(
            request=request,
            preparation_state=preparation_state,
            scene_count=0,
            prompt_scene_field_count=0,
        )
        return snapshot

    @staticmethod
    def _single_direct_result(
        request: CapturedGenerationRequest,
        direct_plan: DirectWorkflowGenerationPlan,
    ) -> GenerationPreparationResult:
        """Return one non-scene direct workflow snapshot."""

        return GenerationPreparationResult(
            snapshots=(
                GenerationJobSnapshot(
                    workflow_id=request.workflow_id,
                    workflow_name=request.workflow_name,
                    sugar_script_text="",
                    direct_workflow_plan=direct_plan,
                ),
            )
        )

    def _prepare_scene_snapshot(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_analysis: WorkflowSceneAnalysis,
        scene_plan: PromptScenePreparationPlan,
        scene: WorkflowScene,
        scene_run_id: str,
        preparation_state: "_PreparationState",
    ) -> GenerationJobSnapshot:
        """Prepare one scene queue snapshot from prompt-field overlays."""

        scene_prompt_overrides = scene_plan.prompt_field_overrides_for_scene(scene.key)
        resolved_prompt_overrides = self._resolve_prompt_overrides(
            request=request,
            prompt_field_overrides=scene_prompt_overrides,
            preprocessing_context=preparation_state.preprocessing_context,
        )
        positive_prompt_preview = positive_prompt_preview_from_prompt_overrides(
            workflow=request.workflow,
            behavior_snapshot=request.behavior_snapshot,
            prompt_field_overrides=resolved_prompt_overrides,
        )
        sugar_script_text = self._serialize(
            request=request,
            preparation_state=preparation_state,
            prompt_field_overrides=resolved_prompt_overrides,
        )
        return GenerationJobSnapshot(
            workflow_id=request.workflow_id,
            workflow_name=f"{request.workflow_name} - {scene.title}",
            sugar_script_text=sugar_script_text,
            positive_prompt_preview=positive_prompt_preview,
            scene_run_id=scene_run_id,
            scene_key=scene.key,
            scene_title=scene.title,
            scene_order=scene.order,
            scene_count=len(scene_analysis.scenes),
        )

    def _preparation_state(
        self,
        request: CapturedGenerationRequest,
    ) -> "_PreparationState":
        """Build request-scoped wildcard and serialization state."""

        serialization_context = self._create_serialization_context()
        serialization_plan = self._build_serialization_plan(
            request=request,
            serialization_context=serialization_context,
        )
        return _PreparationState(
            preprocessing_context=PromptWildcardPreprocessingContext(),
            serialization_context=serialization_context,
            serialization_plan=serialization_plan,
        )

    def _scene_plan(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_analysis: WorkflowSceneAnalysis,
    ) -> PromptScenePreparationPlan:
        """Build a prompt scene plan for the captured workflow."""

        behavior_snapshot = request.behavior_snapshot
        if behavior_snapshot is None:
            raise ValueError("Scene preparation requires a prompt endpoint index.")
        return self._scene_plan_builder.build(
            workflow=cast(Any, request.workflow),
            workflow_id=request.workflow_id,
            endpoint_index=behavior_snapshot.prompt_endpoint_index,
            scene_analysis=scene_analysis,
        )

    def _resolve_prompt_overrides(
        self,
        *,
        request: CapturedGenerationRequest,
        prompt_field_overrides: Mapping[tuple[str, str, str], str] | None,
        preprocessing_context: PromptWildcardPreprocessingContext,
    ) -> dict[tuple[str, str, str], str]:
        """Resolve wildcard prompt overlays for the captured workflow."""

        preprocessor = self._prompt_wildcard_preprocessing_service
        if preprocessor is None:
            return dict(prompt_field_overrides or {})
        return preprocessor.resolve_workflow_prompt_field_overrides(
            workflow=request.workflow,
            workflow_id=request.workflow_id,
            prompt_field_overrides=prompt_field_overrides,
            preprocessing_context=preprocessing_context,
            prompt_endpoint_index=None
            if request.behavior_snapshot is None
            else request.behavior_snapshot.prompt_endpoint_index,
        )

    def _serialize(
        self,
        *,
        request: CapturedGenerationRequest,
        preparation_state: "_PreparationState",
        prompt_field_overrides: Mapping[tuple[str, str, str], object],
    ) -> str:
        """Serialize one prepared snapshot using request-scoped recipe state."""

        serialize = getattr(
            self._recipe_io_service,
            "serialize_workflow_to_sugar_script",
        )
        try:
            serialize_parameters = signature(serialize).parameters
        except (TypeError, ValueError):
            return cast(str, serialize(request.workflow))
        kwargs: dict[str, object] = {}
        if "enabled_node_keys_by_alias" in serialize_parameters:
            kwargs["enabled_node_keys_by_alias"] = request.enabled_node_keys_by_alias
        if "disabled_node_keys_by_alias" in serialize_parameters:
            kwargs["disabled_node_keys_by_alias"] = request.disabled_node_keys_by_alias
        if (
            "global_override_scopes" in serialize_parameters
            and request.global_override_scopes is not None
        ):
            kwargs["global_override_scopes"] = request.global_override_scopes
        if (
            "serialization_context" in serialize_parameters
            and preparation_state.serialization_context is not None
        ):
            kwargs["serialization_context"] = preparation_state.serialization_context
        if (
            "serialization_plan" in serialize_parameters
            and preparation_state.serialization_plan is not None
        ):
            kwargs["serialization_plan"] = preparation_state.serialization_plan
        if "prompt_field_overrides" in serialize_parameters:
            kwargs["prompt_field_overrides"] = prompt_field_overrides
        return cast(str, serialize(request.workflow, **kwargs))

    def _create_serialization_context(self) -> object | None:
        """Return a request-scoped recipe context when the serializer supports one."""

        create_context = getattr(
            self._recipe_io_service,
            "create_serialization_context",
            None,
        )
        if not callable(create_context):
            return None
        return cast(object, create_context())

    def _build_serialization_plan(
        self,
        *,
        request: CapturedGenerationRequest,
        serialization_context: object | None,
    ) -> object | None:
        """Return a reusable serialization plan when the serializer supports one."""

        build_plan = getattr(self._recipe_io_service, "build_serialization_plan", None)
        if not callable(build_plan):
            return None
        try:
            plan_parameters = signature(build_plan).parameters
        except (TypeError, ValueError):
            return cast(object, build_plan(request.workflow))
        kwargs: dict[str, object] = {}
        if "enabled_node_keys_by_alias" in plan_parameters:
            kwargs["enabled_node_keys_by_alias"] = request.enabled_node_keys_by_alias
        if "disabled_node_keys_by_alias" in plan_parameters:
            kwargs["disabled_node_keys_by_alias"] = request.disabled_node_keys_by_alias
        if (
            "serialization_context" in plan_parameters
            and serialization_context is not None
        ):
            kwargs["serialization_context"] = serialization_context
        return cast(object, build_plan(request.workflow, **kwargs))

    def _log_preparation_cache_stats(
        self,
        *,
        request: CapturedGenerationRequest,
        preparation_state: "_PreparationState",
        scene_count: int,
        prompt_scene_field_count: int,
    ) -> None:
        """Log request-scoped preparation cache size and hit/miss counters."""

        wildcard_context = preparation_state.preprocessing_context
        unique_inline_lora_count = 0
        model_hash_lookup_kind_count = 0
        serialization_context = preparation_state.serialization_context
        if isinstance(serialization_context, RecipeSerializationContext):
            unique_inline_lora_count = len(
                serialization_context.prompt_lora_sha_by_normalized_name
            )
            model_hash_lookup_kind_count = _model_hash_lookup_kind_count(
                serialization_context.model_hash_lookup
            )
        log_debug(
            _LOGGER,
            "Generation preparation cache stats.",
            workflow_id=request.workflow_id,
            scene_count=scene_count,
            prompt_endpoint_count=_prompt_endpoint_count(request),
            prompt_scene_field_count=prompt_scene_field_count,
            unique_inline_lora_count=unique_inline_lora_count,
            model_hash_lookup_kind_count=model_hash_lookup_kind_count,
            wildcard_exact_cache_hits=wildcard_context.exact_resolution_cache_hits,
            wildcard_exact_cache_misses=wildcard_context.exact_resolution_cache_misses,
        )


@dataclass(frozen=True, slots=True)
class _PreparationState:
    """Carry request-scoped state shared by snapshots in one preparation pass."""

    preprocessing_context: PromptWildcardPreprocessingContext
    serialization_context: object | None
    serialization_plan: object | None


def _scene_for_key(
    *,
    scene_analysis: WorkflowSceneAnalysis,
    scene_key: str,
) -> WorkflowScene:
    """Return one runnable scene by key or raise a value error."""

    for scene in scene_analysis.scenes:
        if scene.key == scene_key:
            return scene
    raise ValueError(f"Generate scene could not find runnable scene: {scene_key}")


def _prompt_endpoint_count(request: CapturedGenerationRequest) -> int:
    """Return the number of semantic prompt endpoints captured for the request."""

    if request.behavior_snapshot is None:
        return 0
    return len(request.behavior_snapshot.prompt_endpoint_index.endpoints)


def _model_hash_lookup_kind_count(model_hash_lookup: object | None) -> int:
    """Return the indexed model kind count when a lookup session exposes it."""

    indexed_kind_count = getattr(model_hash_lookup, "indexed_kind_count", 0)
    return indexed_kind_count if isinstance(indexed_kind_count, int) else 0


__all__ = [
    "CapturedGenerationRequest",
    "GenerationPreparationResult",
    "GenerationPreparationService",
]
