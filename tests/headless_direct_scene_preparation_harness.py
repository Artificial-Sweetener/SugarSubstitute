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

"""Prepare prompt scenes from real Comfy fixtures without starting Qt or Comfy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationPreparationResult,
    GenerationPreparationService,
    GenerationRequest,
)
from substitute.application.generation.generation_preparation_service import (
    GenerationPromptWildcardPreprocessor,
)
from substitute.application.node_behavior import NodeBehaviorService
from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.comfy_workflow import ComfyWorkflowConverter, DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from substitute.infrastructure.comfy.workflow_json_repository import (
    JsonComfyWorkflowRepository,
)
from tests.prompt_detection_fixture_catalog import PromptDetectionFixture
from tests.recorded_node_definition_gateway import RecordedNodeDefinitionGateway


class HeadlessDirectScenePreparationHarness:
    """Drive real workflow import, prompt detection, and scene graph preparation."""

    def __init__(
        self,
        *,
        wildcard_preprocessor: GenerationPromptWildcardPreprocessor | None = None,
    ) -> None:
        """Store optional deterministic wildcard behavior for scene preparation."""

        self._wildcard_preprocessor = wildcard_preprocessor

    def prepare(
        self,
        fixture: PromptDetectionFixture,
        *,
        prompt_text_by_node: Mapping[str, str],
        scene_run_id: str = "headless-direct-scenes",
    ) -> tuple[GenerationPreparationResult, DirectWorkflowState]:
        """Return production-prepared scenes and the untouched authored document."""

        source_workflow = JsonComfyWorkflowRepository().load(fixture.path)
        buffer = ComfyWorkflowConverter().convert(
            source_workflow,
            node_definitions=fixture.node_definitions,
        )
        nodes = cast(Any, buffer)["nodes"]
        for node_id, prompt_text in prompt_text_by_node.items():
            nodes[node_id]["inputs"]["text"] = prompt_text
        document = DirectWorkflowState(
            source_path=fixture.path,
            source_workflow=source_workflow,
            buffer=buffer,
        )
        behavior_snapshot = NodeBehaviorService(
            node_definition_gateway=RecordedNodeDefinitionGateway(
                fixture.node_definitions
            )
        ).build_snapshot(
            cube_states={DIRECT_WORKFLOW_SECTION_KEY: document},
            stack_order=[DIRECT_WORKFLOW_SECTION_KEY],
        )
        captured = CapturedGenerationRequest.capture(
            request=GenerationRequest(
                workflow_id=f"fixture:{fixture.name}",
                workflow_name=fixture.name,
                workflow=cast(
                    Any,
                    WorkflowState(direct_workflow=document),
                ),
            ),
            behavior_snapshot=behavior_snapshot,
        )
        result = GenerationPreparationService(
            recipe_io_service=object(),
            prompt_wildcard_preprocessing_service=self._wildcard_preprocessor,
        ).prepare_queued_snapshots(
            request=captured,
            scene_run_id=scene_run_id,
        )
        return result, document


__all__ = ["HeadlessDirectScenePreparationHarness"]
