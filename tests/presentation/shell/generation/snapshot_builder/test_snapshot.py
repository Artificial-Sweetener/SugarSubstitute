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

"""Tests for shell generation snapshot-building helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from substitute.application.generation import (
    GenerationRequest,
)
from substitute.application.recipes.recipe_io_service import WorkflowLike
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    generation_snapshot_from_request,
)


from tests.presentation.shell.generation.snapshot_builder.support import (
    _behavior_snapshot,
    _prompt_workflow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def test_generation_snapshot_from_request_preprocesses_and_serializes() -> None:
    """Snapshot construction should use the processed workflow for all outputs."""

    original_workflow = _prompt_workflow("original prompt")
    processed_workflow = _prompt_workflow("  processed\nprompt  ")
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="prompt_template",
            ),
        )
    )
    behavior_snapshot = _behavior_snapshot(prompt_endpoint_index=endpoint_index)
    global_scopes = cast(
        Mapping[str, GlobalOverrideSerializationScope],
        {"scope": object()},
    )
    calls: list[dict[str, object]] = []

    class _PreprocessingService:
        """Return the processed workflow while recording prompt endpoint metadata."""

        def preprocess_workflow(
            self,
            *,
            workflow: object,
            workflow_id: str,
            wildcard_context: object | None,
            prompt_endpoint_index: object | None,
        ) -> object:
            """Record preprocessing arguments and return processed workflow."""

            calls.append(
                {
                    "stage": "preprocess",
                    "workflow": workflow,
                    "workflow_id": workflow_id,
                    "wildcard_context": wildcard_context,
                    "prompt_endpoint_index": prompt_endpoint_index,
                }
            )
            return processed_workflow

    class _RecipeIoService:
        """Record the workflow passed to recipe serialization."""

        def serialize_workflow_to_sugar_script(
            self,
            workflow: object,
            *,
            global_override_scopes: object,
        ) -> str:
            """Record serialization arguments and return Sugar text."""

            calls.append(
                {
                    "stage": "serialize",
                    "workflow": workflow,
                    "global_override_scopes": global_override_scopes,
                }
            )
            return "# sugar"

    snapshot = generation_snapshot_from_request(
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(WorkflowLike, original_workflow),
            global_override_scopes=global_scopes,
        ),
        behavior_snapshot=behavior_snapshot,
        recipe_io_service=_RecipeIoService(),
        prompt_wildcard_preprocessing_service=_PreprocessingService(),
    )

    assert snapshot.workflow_id == "workflow-a"
    assert snapshot.workflow_name == "Recipe A"
    assert snapshot.sugar_script_text == "# sugar"
    assert snapshot.positive_prompt_preview == "processed prompt"
    assert calls == [
        {
            "stage": "preprocess",
            "workflow": original_workflow,
            "workflow_id": "workflow-a",
            "wildcard_context": None,
            "prompt_endpoint_index": endpoint_index,
        },
        {
            "stage": "serialize",
            "workflow": processed_workflow,
            "global_override_scopes": global_scopes,
        },
    ]
