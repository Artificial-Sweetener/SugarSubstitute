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

"""Build shell-side generation snapshots from prepared request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from inspect import signature
from typing import TYPE_CHECKING, Protocol, cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
    positive_prompt_preview_from_workflow,
)
from substitute.presentation.shell.workspace_generation_request_builder import (
    activation_node_keys_by_alias,
)

if TYPE_CHECKING:
    from substitute.application.node_behavior import EditorBehaviorSnapshot


class QueuedSnapshotPreparationService(Protocol):
    """Prepare detached queued generation snapshots."""

    def prepare_queued_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
    ) -> GenerationPreparationResult:
        """Return immutable queued snapshots from a captured request."""


class SceneRunPreparedCallback(Protocol):
    """Apply presentation scene-run bookkeeping for prepared snapshots."""

    def __call__(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Record that a prepared scene run is beginning."""


@dataclass(frozen=True, slots=True)
class QueuedSnapshotPreparation:
    """Carry detached queued snapshot preparation callbacks."""

    prepare_snapshots: Callable[[], GenerationPreparationResult]
    on_prepared: Callable[
        [GenerationPreparationResult], tuple[GenerationJobSnapshot, ...]
    ]


def serialize_generation_workflow(
    *,
    recipe_io_service: object,
    workflow: object,
    behavior_snapshot: object | None,
    global_override_scopes: Mapping[str, object] | None = None,
    serialization_context: object | None = None,
    serialization_plan: object | None = None,
    prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
) -> str:
    """Serialize a generation workflow while applying activation overrides."""

    serialize = getattr(recipe_io_service, "serialize_workflow_to_sugar_script")
    enabled_node_keys_by_alias, disabled_node_keys_by_alias = (
        activation_node_keys_by_alias(behavior_snapshot, workflow)
    )
    try:
        serialize_parameters = signature(serialize).parameters
    except (TypeError, ValueError):
        accepts_enabled_nodes = False
        accepts_disabled_nodes = False
        accepts_global_override_scopes = False
        accepts_serialization_context = False
        accepts_serialization_plan = False
        accepts_prompt_field_overrides = False
    else:
        accepts_enabled_nodes = "enabled_node_keys_by_alias" in serialize_parameters
        accepts_disabled_nodes = "disabled_node_keys_by_alias" in serialize_parameters
        accepts_global_override_scopes = (
            "global_override_scopes" in serialize_parameters
        )
        accepts_serialization_context = "serialization_context" in serialize_parameters
        accepts_serialization_plan = "serialization_plan" in serialize_parameters
        accepts_prompt_field_overrides = (
            "prompt_field_overrides" in serialize_parameters
        )
    kwargs: dict[str, object] = {}
    if accepts_disabled_nodes:
        kwargs["disabled_node_keys_by_alias"] = disabled_node_keys_by_alias
        if accepts_enabled_nodes:
            kwargs["enabled_node_keys_by_alias"] = enabled_node_keys_by_alias
    if accepts_global_override_scopes and global_override_scopes is not None:
        kwargs["global_override_scopes"] = global_override_scopes
    if accepts_serialization_context and serialization_context is not None:
        kwargs["serialization_context"] = serialization_context
    if accepts_serialization_plan and serialization_plan is not None:
        kwargs["serialization_plan"] = serialization_plan
    if accepts_prompt_field_overrides and prompt_field_overrides is not None:
        kwargs["prompt_field_overrides"] = prompt_field_overrides
    if kwargs:
        return cast(str, serialize(workflow, **kwargs))
    return cast(str, serialize(workflow))


def create_recipe_serialization_context(recipe_io_service: object) -> object | None:
    """Return a request-scoped recipe serialization context when supported."""

    create_context = getattr(recipe_io_service, "create_serialization_context", None)
    if not callable(create_context):
        return None
    return cast("object | None", create_context())


def build_recipe_serialization_plan(
    *,
    recipe_io_service: object,
    workflow: object,
    behavior_snapshot: object | None,
    serialization_context: object | None,
) -> object | None:
    """Return a reusable recipe serialization plan when supported."""

    build_plan = getattr(recipe_io_service, "build_serialization_plan", None)
    if not callable(build_plan):
        return None
    enabled_node_keys_by_alias, disabled_node_keys_by_alias = (
        activation_node_keys_by_alias(behavior_snapshot, workflow)
    )
    try:
        plan_parameters = signature(build_plan).parameters
    except (TypeError, ValueError):
        return cast("object | None", build_plan(workflow))
    kwargs: dict[str, object] = {}
    if "enabled_node_keys_by_alias" in plan_parameters:
        kwargs["enabled_node_keys_by_alias"] = enabled_node_keys_by_alias
    if "disabled_node_keys_by_alias" in plan_parameters:
        kwargs["disabled_node_keys_by_alias"] = disabled_node_keys_by_alias
    if "serialization_context" in plan_parameters and serialization_context is not None:
        kwargs["serialization_context"] = serialization_context
    return cast("object | None", build_plan(workflow, **kwargs))


def preprocess_generation_workflow(
    *,
    prompt_wildcard_preprocessing_service: object | None,
    workflow: object,
    workflow_id: str,
    wildcard_context: object | None = None,
    prompt_endpoint_index: object | None = None,
) -> object:
    """Resolve generation-only prompt preprocessors for a workflow snapshot."""

    preprocess_workflow = getattr(
        prompt_wildcard_preprocessing_service, "preprocess_workflow", None
    )
    if callable(preprocess_workflow):
        return cast(
            object,
            preprocess_workflow(
                workflow=workflow,
                workflow_id=workflow_id,
                wildcard_context=wildcard_context,
                prompt_endpoint_index=prompt_endpoint_index,
            ),
        )
    return workflow


def generation_snapshot_from_request(
    *,
    request: GenerationRequest,
    behavior_snapshot: "EditorBehaviorSnapshot | None",
    recipe_io_service: object,
    prompt_wildcard_preprocessing_service: object | None,
) -> GenerationJobSnapshot:
    """Capture one queued Sugar script snapshot from a generation request."""

    workflow = preprocess_generation_workflow(
        prompt_wildcard_preprocessing_service=prompt_wildcard_preprocessing_service,
        workflow=request.workflow,
        workflow_id=request.workflow_id,
        prompt_endpoint_index=None
        if behavior_snapshot is None
        else behavior_snapshot.prompt_endpoint_index,
    )
    positive_prompt_preview = positive_prompt_preview_from_workflow(
        workflow=workflow,
        behavior_snapshot=behavior_snapshot,
    )
    sugar_script_text = serialize_generation_workflow(
        recipe_io_service=recipe_io_service,
        workflow=workflow,
        behavior_snapshot=behavior_snapshot,
        global_override_scopes=request.global_override_scopes,
    )
    return GenerationJobSnapshot(
        workflow_id=request.workflow_id,
        workflow_name=request.workflow_name,
        sugar_script_text=sugar_script_text,
        positive_prompt_preview=positive_prompt_preview,
    )


def capture_queued_snapshot_preparation(
    *,
    request: GenerationRequest,
    behavior_snapshot: "EditorBehaviorSnapshot | None",
    preparation_service: QueuedSnapshotPreparationService,
    on_scene_run_prepared: SceneRunPreparedCallback,
) -> QueuedSnapshotPreparation:
    """Capture detached queued snapshot preparation callbacks."""

    captured_request = CapturedGenerationRequest.capture(
        request=request,
        behavior_snapshot=behavior_snapshot,
    )

    def prepare_snapshots() -> GenerationPreparationResult:
        """Prepare queued snapshots from detached state."""

        return preparation_service.prepare_queued_snapshots(request=captured_request)

    def on_prepared(
        result: GenerationPreparationResult,
    ) -> tuple[GenerationJobSnapshot, ...]:
        """Apply scene-run bookkeeping for a prepared queued snapshot result."""

        if result.scene_run_id is not None and result.scene_count is not None:
            on_scene_run_prepared(
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                scene_run_id=result.scene_run_id,
                scene_count=result.scene_count,
                snapshots=result.snapshots,
            )
        return result.snapshots

    return QueuedSnapshotPreparation(
        prepare_snapshots=prepare_snapshots,
        on_prepared=on_prepared,
    )


__all__ = [
    "build_recipe_serialization_plan",
    "capture_queued_snapshot_preparation",
    "create_recipe_serialization_context",
    "generation_snapshot_from_request",
    "preprocess_generation_workflow",
    "QueuedSnapshotPreparation",
    "QueuedSnapshotPreparationService",
    "SceneRunPreparedCallback",
    "serialize_generation_workflow",
]
