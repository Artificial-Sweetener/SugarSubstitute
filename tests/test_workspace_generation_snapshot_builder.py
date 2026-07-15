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

import ast
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.recipes.recipe_io_service import WorkflowLike
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import NodeDisplayDecision, PromptRole
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    build_recipe_serialization_plan,
    capture_queued_snapshot_preparation,
    create_recipe_serialization_context,
    generation_snapshot_from_request,
    preprocess_generation_workflow,
    serialize_generation_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _behavior_snapshot(
    prompt_endpoint_index: PromptEndpointIndex | None = None,
) -> EditorBehaviorSnapshot:
    """Return a behavior snapshot with one activation delta."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "enabled_from_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "disabled_from_default": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=prompt_endpoint_index or PromptEndpointIndex(),
    )


def _workflow() -> SimpleNamespace:
    """Return a workflow-like object with activation defaults."""

    return SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "enabled_from_bypass": {"mode": 4},
                        "disabled_from_default": {},
                    }
                }
            )
        },
    )


def _prompt_workflow(prompt_text: str) -> SimpleNamespace:
    """Return a workflow-like object with one positive prompt endpoint."""

    return SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {"inputs": {"prompt_template": prompt_text}},
                    }
                }
            )
        },
    )


def test_serialize_generation_workflow_passes_supported_kwargs() -> None:
    """Serialization should pass only kwargs supported by the recipe service."""

    calls: list[dict[str, object]] = []

    class _RecipeIoService:
        """Record supported serialization keyword arguments."""

        def serialize_workflow_to_sugar_script(
            self,
            workflow: object,
            *,
            enabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            disabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            global_override_scopes: object,
            serialization_context: object,
            serialization_plan: object,
            prompt_field_overrides: object,
        ) -> str:
            """Record serialization arguments and return Sugar text."""

            calls.append(
                {
                    "workflow": workflow,
                    "enabled": enabled_node_keys_by_alias,
                    "disabled": disabled_node_keys_by_alias,
                    "global": global_override_scopes,
                    "context": serialization_context,
                    "plan": serialization_plan,
                    "prompt_overrides": prompt_field_overrides,
                }
            )
            return "# sugar"

    workflow = _workflow()
    global_scopes = cast(
        Mapping[str, GlobalOverrideSerializationScope],
        {"scope": object()},
    )
    context = object()
    plan = object()
    prompt_overrides = {("A", "node", "field"): object()}

    assert (
        serialize_generation_workflow(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            global_override_scopes=global_scopes,
            serialization_context=context,
            serialization_plan=plan,
            prompt_field_overrides=prompt_overrides,
        )
        == "# sugar"
    )

    assert calls == [
        {
            "workflow": workflow,
            "enabled": {"A": ("enabled_from_bypass",)},
            "disabled": {"A": ("disabled_from_default",)},
            "global": global_scopes,
            "context": context,
            "plan": plan,
            "prompt_overrides": prompt_overrides,
        }
    ]


def test_serialize_generation_workflow_preserves_legacy_serializer_call() -> None:
    """Legacy serializers without optional kwargs should receive only workflow."""

    calls: list[object] = []

    class _RecipeIoService:
        """Record legacy serialization arguments."""

        def serialize_workflow_to_sugar_script(self, workflow: object) -> str:
            """Record the workflow and return Sugar text."""

            calls.append(workflow)
            return "# legacy"

    workflow = _workflow()

    assert (
        serialize_generation_workflow(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            global_override_scopes={"scope": object()},
        )
        == "# legacy"
    )
    assert calls == [workflow]


def test_create_recipe_serialization_context_uses_optional_factory() -> None:
    """Serialization context creation should be optional."""

    context = object()

    assert (
        create_recipe_serialization_context(
            SimpleNamespace(create_serialization_context=lambda: context)
        )
        is context
    )
    assert create_recipe_serialization_context(SimpleNamespace()) is None


def test_build_recipe_serialization_plan_passes_supported_kwargs() -> None:
    """Serialization plan construction should include activation deltas."""

    calls: list[dict[str, object]] = []
    context = object()
    plan = object()

    class _RecipeIoService:
        """Record supported plan keyword arguments."""

        def build_serialization_plan(
            self,
            workflow: object,
            *,
            enabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            disabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            serialization_context: object,
        ) -> object:
            """Record plan arguments and return a plan object."""

            calls.append(
                {
                    "workflow": workflow,
                    "enabled": enabled_node_keys_by_alias,
                    "disabled": disabled_node_keys_by_alias,
                    "context": serialization_context,
                }
            )
            return plan

    workflow = _workflow()

    assert (
        build_recipe_serialization_plan(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            serialization_context=context,
        )
        is plan
    )
    assert calls == [
        {
            "workflow": workflow,
            "enabled": {"A": ("enabled_from_bypass",)},
            "disabled": {"A": ("disabled_from_default",)},
            "context": context,
        }
    ]


def test_build_recipe_serialization_plan_is_optional() -> None:
    """Missing plan construction support should return None."""

    assert (
        build_recipe_serialization_plan(
            recipe_io_service=SimpleNamespace(),
            workflow=_workflow(),
            behavior_snapshot=_behavior_snapshot(),
            serialization_context=None,
        )
        is None
    )


def test_preprocess_generation_workflow_uses_optional_service() -> None:
    """Prompt wildcard preprocessing should be delegated when supported."""

    original_workflow = object()
    processed_workflow = object()
    wildcard_context = object()
    endpoint_index = PromptEndpointIndex()
    calls: list[dict[str, object]] = []

    class _PreprocessingService:
        """Record preprocessing arguments and return a processed workflow."""

        def preprocess_workflow(
            self,
            *,
            workflow: object,
            workflow_id: str,
            wildcard_context: object | None,
            prompt_endpoint_index: object | None,
        ) -> object:
            """Record the preprocessing call."""

            calls.append(
                {
                    "workflow": workflow,
                    "workflow_id": workflow_id,
                    "wildcard_context": wildcard_context,
                    "prompt_endpoint_index": prompt_endpoint_index,
                }
            )
            return processed_workflow

    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=_PreprocessingService(),
            workflow=original_workflow,
            workflow_id="workflow-a",
            wildcard_context=wildcard_context,
            prompt_endpoint_index=endpoint_index,
        )
        is processed_workflow
    )
    assert calls == [
        {
            "workflow": original_workflow,
            "workflow_id": "workflow-a",
            "wildcard_context": wildcard_context,
            "prompt_endpoint_index": endpoint_index,
        }
    ]


def test_preprocess_generation_workflow_returns_original_without_service() -> None:
    """Missing prompt wildcard preprocessing support should preserve workflow."""

    workflow = object()

    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=None,
            workflow=workflow,
            workflow_id="workflow-a",
        )
        is workflow
    )
    assert (
        preprocess_generation_workflow(
            prompt_wildcard_preprocessing_service=SimpleNamespace(),
            workflow=workflow,
            workflow_id="workflow-a",
        )
        is workflow
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


def test_capture_queued_snapshot_preparation_uses_detached_request() -> None:
    """Queued preparation should capture workflow state before task execution."""

    workflow = SimpleNamespace(seed="before")
    captured_workflows: list[object] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        sugar_script_text="# sugar",
    )

    class _PreparationService:
        """Record the detached request used by queued preparation."""

        def prepare_queued_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
        ) -> GenerationPreparationResult:
            """Record captured workflow state and return a snapshot result."""

            captured_workflows.append(request.workflow)
            return GenerationPreparationResult(snapshots=(snapshot,))

    def _ignore_scene_run(
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Ignore scene-run callbacks for the no-scene case."""

        _ = workflow_id, workflow_name, scene_run_id, scene_count, snapshots

    preparation = capture_queued_snapshot_preparation(
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(WorkflowLike, workflow),
        ),
        behavior_snapshot=None,
        preparation_service=_PreparationService(),
        on_scene_run_prepared=_ignore_scene_run,
    )

    workflow.seed = "after"
    result = preparation.prepare_snapshots()

    assert result.snapshots == (snapshot,)
    assert len(captured_workflows) == 1
    assert captured_workflows[0] is not workflow
    assert getattr(captured_workflows[0], "seed") == "before"
    assert preparation.on_prepared(result) == (snapshot,)


def test_capture_queued_snapshot_preparation_applies_scene_run_bookkeeping() -> None:
    """Prepared scene metadata should flow through the injected scene callback."""

    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A - Scene",
        sugar_script_text="# scene",
        scene_run_id="scene-run-a",
        scene_key="scene-a",
        scene_count=2,
    )
    scene_calls: list[tuple[str, str, str, int, tuple[GenerationJobSnapshot, ...]]] = []
    result = GenerationPreparationResult(
        snapshots=(snapshot,),
        scene_run_id="scene-run-a",
        scene_count=2,
    )

    class _PreparationService:
        """Return a prebuilt scene preparation result."""

        def prepare_queued_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
        ) -> GenerationPreparationResult:
            """Return the scene preparation result."""

            _ = request
            return result

    def _record_scene_run(
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Record scene-run bookkeeping callback arguments."""

        scene_calls.append(
            (
                workflow_id,
                workflow_name,
                scene_run_id,
                scene_count,
                snapshots,
            )
        )

    preparation = capture_queued_snapshot_preparation(
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(WorkflowLike, _workflow()),
        ),
        behavior_snapshot=_behavior_snapshot(),
        preparation_service=_PreparationService(),
        on_scene_run_prepared=_record_scene_run,
    )

    assert preparation.prepare_snapshots() is result
    assert preparation.on_prepared(result) == (snapshot,)
    assert scene_calls == [
        (
            "workflow-a",
            "Recipe A",
            "scene-run-a",
            2,
            (snapshot,),
        )
    ]


def test_workspace_generation_snapshot_builder_imports_no_concrete_boundaries() -> None:
    """Snapshot builder helpers should not import Qt or concrete controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_workspace_controller_no_longer_owns_serialization_helpers() -> None:
    """Workspace controller should delegate moved serialization helper policy."""

    source = WORKSPACE_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert "def _serialize_generation_workflow(" not in source
    assert "def _create_recipe_serialization_context(" not in source
    assert "def _build_recipe_serialization_plan(" not in source
    assert "def _preprocess_generation_workflow(" not in source
