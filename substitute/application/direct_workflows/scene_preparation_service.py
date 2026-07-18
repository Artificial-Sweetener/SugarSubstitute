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

"""Prepare scene-specific direct Comfy plans without Sugar serialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from substitute.application.generation.prompt_scene_preparation_plan import (
    PromptScenePreparationPlan,
    PromptScenePreparationPlanBuilder,
)
from substitute.application.prompt_editor import (
    PromptSceneAnalysisService,
    WorkflowScene,
    WorkflowSceneAnalysis,
)
from substitute.application.prompt_wildcards import (
    PromptWildcardPreprocessingContext,
)
from substitute.domain.comfy_workflow import (
    DirectWorkflowGenerationPlan,
    DirectWorkflowState,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.domain.links import PromptEndpointIndex

from .prompt_scene_projection import (
    DirectWorkflowPromptProjector,
    DirectWorkflowPromptView,
)


class DirectPromptWildcardPreprocessor(Protocol):
    """Describe wildcard overlay resolution used by direct scene preparation."""

    def resolve_workflow_prompt_field_overrides(
        self,
        *,
        workflow: object,
        workflow_id: str,
        prompt_field_overrides: Mapping[tuple[str, str, str], str] | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return wildcard-resolved direct prompt-field overlays."""


@dataclass(frozen=True, slots=True)
class DirectScenePreparationResult:
    """Carry direct scene snapshots and their shared run identity."""

    snapshots: tuple[GenerationJobSnapshot, ...]
    scene_run_id: str
    scene_count: int


class DirectWorkflowScenePreparationService:
    """Own scene analysis and immutable prompt projection for direct workflows."""

    def __init__(
        self,
        *,
        wildcard_preprocessor: DirectPromptWildcardPreprocessor | None = None,
    ) -> None:
        """Initialize shared prompt analysis and projection collaborators."""

        self._wildcard_preprocessor = wildcard_preprocessor
        self._analysis_service = PromptSceneAnalysisService()
        self._plan_builder = PromptScenePreparationPlanBuilder()
        self._prompt_projector = DirectWorkflowPromptProjector()

    def analyze(
        self,
        *,
        document: DirectWorkflowState,
        endpoint_index: PromptEndpointIndex,
    ) -> WorkflowSceneAnalysis:
        """Return prompt-scene analysis through the shared prompt model."""

        return self._analysis_service.analyze(
            workflow=DirectWorkflowPromptView(document),
            endpoint_index=endpoint_index,
        )

    def prepare_all(
        self,
        *,
        document: DirectWorkflowState,
        plan: DirectWorkflowGenerationPlan,
        workflow_id: str,
        workflow_name: str,
        endpoint_index: PromptEndpointIndex,
        scene_analysis: WorkflowSceneAnalysis,
        scene_run_id: str | None = None,
    ) -> DirectScenePreparationResult:
        """Return one detached direct plan for every runnable prompt scene."""

        if not scene_analysis.can_generate_scenes:
            raise ValueError("Scene generation requires at least one runnable scene.")
        resolved_run_id = scene_run_id or uuid4().hex
        view = DirectWorkflowPromptView(document)
        scene_plan = self._plan_builder.build(
            workflow=view,
            workflow_id=workflow_id,
            endpoint_index=endpoint_index,
            scene_analysis=scene_analysis,
        )
        preprocessing_context = PromptWildcardPreprocessingContext()
        snapshots = tuple(
            self._snapshot_for_scene(
                view=view,
                plan=plan,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                endpoint_index=endpoint_index,
                scene_analysis=scene_analysis,
                scene=scene,
                scene_plan=scene_plan,
                scene_run_id=resolved_run_id,
                preprocessing_context=preprocessing_context,
            )
            for scene in scene_analysis.scenes
        )
        return DirectScenePreparationResult(
            snapshots=snapshots,
            scene_run_id=resolved_run_id,
            scene_count=len(scene_analysis.scenes),
        )

    def prepare_one(
        self,
        *,
        document: DirectWorkflowState,
        plan: DirectWorkflowGenerationPlan,
        workflow_id: str,
        workflow_name: str,
        endpoint_index: PromptEndpointIndex,
        scene_analysis: WorkflowSceneAnalysis,
        scene_key: str,
        scene_run_id: str | None = None,
    ) -> GenerationJobSnapshot:
        """Return one detached direct plan for a selected prompt scene."""

        scene = next(
            (
                candidate
                for candidate in scene_analysis.scenes
                if candidate.key == scene_key
            ),
            None,
        )
        if scene is None:
            raise ValueError(f"Unknown workflow scene key: {scene_key}")
        view = DirectWorkflowPromptView(document)
        scene_plan = self._plan_builder.build(
            workflow=view,
            workflow_id=workflow_id,
            endpoint_index=endpoint_index,
            scene_analysis=scene_analysis,
        )
        return self._snapshot_for_scene(
            view=view,
            plan=plan,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            endpoint_index=endpoint_index,
            scene_analysis=scene_analysis,
            scene=scene,
            scene_plan=scene_plan,
            scene_run_id=scene_run_id or uuid4().hex,
            preprocessing_context=PromptWildcardPreprocessingContext(),
        )

    def _snapshot_for_scene(
        self,
        *,
        view: DirectWorkflowPromptView,
        plan: DirectWorkflowGenerationPlan,
        workflow_id: str,
        workflow_name: str,
        endpoint_index: PromptEndpointIndex,
        scene_analysis: WorkflowSceneAnalysis,
        scene: WorkflowScene,
        scene_plan: PromptScenePreparationPlan,
        scene_run_id: str,
        preprocessing_context: PromptWildcardPreprocessingContext,
    ) -> GenerationJobSnapshot:
        """Build one scene snapshot from cached analysis and immutable overlays."""

        overrides = scene_plan.prompt_field_overrides_for_scene(scene.key)
        preprocessor = self._wildcard_preprocessor
        if preprocessor is not None:
            overrides = preprocessor.resolve_workflow_prompt_field_overrides(
                workflow=view,
                workflow_id=workflow_id,
                prompt_field_overrides=overrides,
                preprocessing_context=preprocessing_context,
                prompt_endpoint_index=endpoint_index,
            )
        projected_plan = self._prompt_projector.project(
            view.document,
            plan,
            prompt_field_overrides=overrides,
        )
        return GenerationJobSnapshot(
            workflow_id=workflow_id,
            workflow_name=f"{workflow_name} - {scene.title}",
            sugar_script_text="",
            direct_workflow_plan=projected_plan,
            scene_run_id=scene_run_id,
            scene_key=scene.key,
            scene_title=scene.title,
            scene_order=scene.order,
            scene_count=len(scene_analysis.scenes),
        )


__all__ = [
    "DirectPromptWildcardPreprocessor",
    "DirectScenePreparationResult",
    "DirectWorkflowScenePreparationService",
]
