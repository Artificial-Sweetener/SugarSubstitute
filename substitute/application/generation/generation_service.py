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

"""Coordinate generation dispatch, listener lifecycle, and output preparation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from sugarsubstitute_shared.localization import app_text

from substitute.application.cubes import cube_alias_body
from substitute.application.direct_workflows import (
    DirectWorkflowExecutionProjector,
    DirectWorkflowGenerationPlanService,
)
from substitute.application.ports.comfy_gateway import (
    ComfyGateway,
    ComfyQueueMutationResult,
    ComfyQueueSnapshot,
    InterruptResult,
    ListenerHandle,
    ListenerOutputSource,
    OutputSavePlan,
)
from substitute.application.recipes.recipe_io_service import (
    RecipeIoService,
    WorkflowLike as RecipeWorkflowLike,
)
from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.application.workflows.input_asset_diagnostics import (
    log_generation_payload_assets,
)
from substitute.domain.common import WorkflowId
from substitute.domain.workflow import active_cube_aliases
from substitute.application.generation.asset_staging_service import (
    ComfyAssetStagingResult,
)
from substitute.application.generation.generation_execution_dispatcher import (
    GenerationExecutionDispatcher,
)
from substitute.application.generation.generation_models import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRequest,
    GenerationStartResult,
    PreparedGenerationRequest,
)
from substitute.application.generation.generation_document_routing import (
    direct_generation_document,
    uses_graph_backed_cube_execution,
)
from substitute.application.generation.native_cube_workflow_builder import (
    NativeCubeWorkflowBuilder,
)
from substitute.application.generation.preview_preference_service import (
    GenerationPreviewMethodResolver,
)
from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.application.generation.output_seed_resolver import resolve_output_seed
from substitute.application.generation.visual_run_context_builder import (
    VisualRunContextBuilder,
)
from substitute.application.prompt_wildcards import PromptWildcardPreprocessingService
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_warning,
)

_UUID_CLASS_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_LOGGER = get_logger("application.generation.generation_service")
DEFAULT_PROJECTS_DIR = Path.cwd() / "user" / "projects"


def _call_accepts_keyword(callable_obj: Callable[..., object], keyword: str) -> bool:
    """Return whether a collaborator method advertises a keyword parameter."""

    try:
        return keyword in signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False


class _DefaultGenerationPreviewMethodResolver:
    """Resolve the default preview method when no preferences are wired."""

    def resolved_comfy_preview_method(self) -> str:
        """Return SugarSubstitute's default Comfy preview method."""

        return "latent2rgb"


class AssetStagingService(Protocol):
    """Describe generation-time asset staging behavior."""

    def stage_payload(
        self,
        *,
        workflow_payload: dict[str, object],
        workflow_id: WorkflowId,
        workflow_name: str,
        workflow: RecipeWorkflowLike | None = None,
    ) -> ComfyAssetStagingResult:
        """Return an execution-ready workflow payload."""


class ModelUsageRecorder(Protocol):
    """Record model identities after a generation is accepted by ComfyUI."""

    def record_queued_payload(self, workflow_payload: Mapping[str, object]) -> int:
        """Record exact referenced models and return their count."""


class GenerationService:
    """Own generation orchestration independent from presentation widgets."""

    def __init__(
        self,
        *,
        recipe_io_service: RecipeIoService,
        comfy_gateway: ComfyGateway,
        asset_staging_service: AssetStagingService | None = None,
        prompt_wildcard_preprocessing_service: (
            PromptWildcardPreprocessingService | None
        ) = None,
        preview_method_resolver: GenerationPreviewMethodResolver | None = None,
        output_preference_service: OutputPreferenceService | None = None,
        direct_workflow_graph_service: DirectWorkflowGenerationPlanService
        | None = None,
        direct_workflow_execution_projector: DirectWorkflowExecutionProjector
        | None = None,
        visual_run_context_builder: VisualRunContextBuilder | None = None,
        model_usage_recorder: ModelUsageRecorder | None = None,
        native_cube_workflow_builder: NativeCubeWorkflowBuilder | None = None,
        output_dir: Path = DEFAULT_PROJECTS_DIR,
        client_id: str = "substitute",
    ) -> None:
        """Initialize generation service dependencies and listener tracking state."""
        self._recipe_io_service = recipe_io_service
        self._comfy_gateway: ComfyGateway = comfy_gateway
        self._asset_staging_service = asset_staging_service
        self._prompt_wildcard_preprocessing_service = (
            prompt_wildcard_preprocessing_service
        )
        resolved_preview_method = (
            preview_method_resolver or _DefaultGenerationPreviewMethodResolver()
        )
        self._output_preference_service = output_preference_service
        self._direct_workflow_graph_service = (
            direct_workflow_graph_service or DirectWorkflowGenerationPlanService()
        )
        self._direct_workflow_execution_projector = (
            direct_workflow_execution_projector or DirectWorkflowExecutionProjector()
        )
        resolved_visual_context_builder = (
            visual_run_context_builder or VisualRunContextBuilder()
        )
        self._native_cube_workflow_builder = (
            native_cube_workflow_builder or NativeCubeWorkflowBuilder()
        )
        self._output_dir = output_dir
        self._execution_dispatcher = GenerationExecutionDispatcher(
            comfy_gateway=comfy_gateway,
            preview_method_resolver=resolved_preview_method,
            visual_run_context_builder=resolved_visual_context_builder,
            output_dir=output_dir,
            client_id=client_id,
            model_usage_recorder=model_usage_recorder,
        )

    @property
    def active_listener_handles(self) -> tuple[ListenerHandle, ...]:
        """Return a snapshot of listener handles currently tracked by the service."""
        return self._execution_dispatcher.active_listener_handles

    def run_single_generation(
        self,
        *,
        request: GenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Run one generation dispatch using provided workflow and callbacks."""
        return self._start_generation(
            request=request,
            callbacks=callbacks,
        )

    def run_prepared_generation(
        self,
        *,
        request: PreparedGenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Run one dispatch from a previously captured Sugar script snapshot."""
        return self._start_prepared_generation(
            request=request,
            callbacks=callbacks,
        )

    def interrupt_generation(self) -> InterruptResult:
        """Interrupt active generation through transport gateway."""
        return self._comfy_gateway.interrupt()

    def get_comfy_queue_snapshot(self) -> ComfyQueueSnapshot:
        """Return Comfy running and pending queue prompt ids."""

        return self._comfy_gateway.get_queue()

    def delete_pending_comfy_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Delete one pending prompt from Comfy's queue."""

        return self._comfy_gateway.delete_pending_prompt(prompt_id)

    def _start_generation(
        self,
        *,
        request: GenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Start one generation attempt and wire websocket listener callbacks."""
        try:
            if callbacks.randomize_seeds is not None:
                callbacks.randomize_seeds()
            workflow = request.workflow
            direct_document = direct_generation_document(workflow)
            direct_plan = (
                self._direct_workflow_graph_service.build(direct_document)
                if direct_document is not None
                else None
            )
            if direct_plan is not None:
                prepared_request = PreparedGenerationRequest(
                    workflow_id=request.workflow_id,
                    workflow_name=request.workflow_name,
                    direct_workflow_plan=direct_plan,
                    workflow=workflow,
                    output_run_number=None,
                    output_session_id=request.output_session_id,
                )
                return self._start_prepared_generation(
                    request=prepared_request,
                    callbacks=callbacks,
                )
            if self._prompt_wildcard_preprocessing_service is not None:
                workflow = (
                    self._prompt_wildcard_preprocessing_service.preprocess_workflow(
                        workflow=request.workflow,
                        workflow_id=request.workflow_id,
                    )
                )
            if uses_graph_backed_cube_execution(workflow):
                sugar_script = None
            else:
                serialize = self._recipe_io_service.serialize_workflow_to_sugar_script
                if request.global_override_scopes is not None and _call_accepts_keyword(
                    serialize, "global_override_scopes"
                ):
                    sugar_script = serialize(
                        workflow,
                        enabled_node_keys_by_alias=request.enabled_node_keys_by_alias,
                        disabled_node_keys_by_alias=request.disabled_node_keys_by_alias,
                        global_override_scopes=request.global_override_scopes,
                    )
                else:
                    sugar_script = serialize(
                        workflow,
                        enabled_node_keys_by_alias=request.enabled_node_keys_by_alias,
                        disabled_node_keys_by_alias=request.disabled_node_keys_by_alias,
                    )
            native_cube_workflow = self._native_cube_workflow_builder.build(
                cast(Any, workflow),
                global_override_scopes=request.global_override_scopes,
            )
            prepared_request = PreparedGenerationRequest(
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                cube_workflow=native_cube_workflow,
                persistence_sugar_script=sugar_script,
                workflow=workflow,
                output_run_number=None,
                output_session_id=request.output_session_id,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to prepare workflow generation snapshot",
                workflow_id=request.workflow_id,
                error=error,
            )
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="build",
                    workflow_id=request.workflow_id,
                    message=str(error),
                ),
            )
        return self._start_prepared_generation(
            request=prepared_request,
            callbacks=callbacks,
        )

    def _start_prepared_generation(
        self,
        *,
        request: PreparedGenerationRequest,
        callbacks: GenerationCallbacks,
    ) -> GenerationStartResult:
        """Start one prepared generation attempt and wire listener callbacks."""
        try:
            execution_targets: tuple[str, ...] | None = None
            standard_output_sources: tuple[ListenerOutputSource, ...] = ()
            if request.direct_workflow_plan is not None:
                direct_projection = self._direct_workflow_execution_projector.project(
                    request.direct_workflow_plan
                )
                workflow_payload = direct_projection.prompt
                execution_targets = direct_projection.execution_targets
                standard_output_sources = tuple(
                    ListenerOutputSource(
                        node_id=recovery.recovery_node_id,
                        source_key=recovery.source_key,
                        source_label=recovery.source_label,
                    )
                    for recovery in direct_projection.recovery_outputs
                )
            else:
                if request.cube_workflow is None:
                    raise RuntimeError(
                        "Cannot generate because no native Cube workflow was prepared."
                    )
                workflow_payload = request.cube_workflow
            unresolved = find_unresolved_uuid_class_types(workflow_payload)
            log_generation_payload_assets(
                workflow_payload,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                stage="compiled",
            )
            if unresolved:
                unresolved_text = ", ".join(unresolved)
                raise RuntimeError(
                    "Workflow build left unresolved UUID wrapper class_type(s): "
                    f"{unresolved_text}. Re-save cubes with updated SugarCubes."
                )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to prepare workflow generation payload",
                workflow_id=request.workflow_id,
                error=error,
            )
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="build",
                    workflow_id=request.workflow_id,
                    message=str(error),
                ),
            )

        if self._asset_staging_service is not None:
            try:
                staging_result = self._asset_staging_service.stage_payload(
                    workflow_payload=workflow_payload,
                    workflow_id=request.workflow_id,
                    workflow_name=request.workflow_name,
                    workflow=request.workflow,
                )
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Failed to stage workflow generation assets",
                    workflow_id=request.workflow_id,
                    error=error,
                )
                return self._notify_failure(
                    callbacks=callbacks,
                    failure=GenerationFailure(
                        stage="stage",
                        workflow_id=request.workflow_id,
                        message=str(error),
                    ),
                )
            if staging_result.failures:
                failure = staging_result.failures[0]
                log_warning(
                    _LOGGER,
                    "Workflow generation asset staging failed",
                    workflow_id=request.workflow_id,
                    node_id=failure.node_id,
                    node_class=failure.node_class,
                    source_value=failure.source_value,
                    failure_message=failure.message,
                )
                return self._notify_failure(
                    callbacks=callbacks,
                    failure=GenerationFailure(
                        stage="stage",
                        workflow_id=request.workflow_id,
                        message=app_text(
                            "Failed to stage workflow asset %1.%2: %3",
                            failure.node_id,
                            failure.input_name,
                            failure.message,
                        ),
                    ),
                )
            workflow_payload = staging_result.workflow_payload
            log_generation_payload_assets(
                workflow_payload,
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                stage="staged",
            )

        try:
            output_seed = resolve_output_seed(
                workflow=request.workflow,
                workflow_payload=workflow_payload,
            )
            output_save_plan = self._create_output_save_plan(
                request,
                seed=output_seed,
                explicit_output_aliases=tuple(
                    source.source_label for source in standard_output_sources
                ),
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to prepare output save plan",
                workflow_id=request.workflow_id,
                workflow_name=request.workflow_name,
                error=error,
            )
            return self._notify_failure(
                callbacks=callbacks,
                failure=GenerationFailure(
                    stage="build",
                    workflow_id=request.workflow_id,
                    message=str(error),
                ),
            )

        return self._execution_dispatcher.dispatch(
            request=request,
            workflow_payload=workflow_payload,
            output_save_plan=output_save_plan,
            callbacks=callbacks,
            native_cube_execution=request.direct_workflow_plan is None,
            execution_targets=execution_targets,
            standard_output_sources=standard_output_sources,
        )

    def _create_output_save_plan(
        self,
        request: PreparedGenerationRequest,
        *,
        seed: str,
        explicit_output_aliases: tuple[str, ...] = (),
    ) -> OutputSavePlan:
        """Create immutable output organization settings for one queued prompt."""

        job_started_at = request.output_job_started_at or datetime.now().astimezone()
        if self._output_preference_service is not None:
            return self._output_preference_service.create_save_plan(
                workflow_name=request.workflow_name,
                output_run_number=request.output_run_number,
                job_started_at=job_started_at,
                seed=seed,
                cube_numbers_by_alias=_cube_numbers_by_alias(request),
                active_cube_aliases=(
                    explicit_output_aliases or _active_cube_aliases_for_request(request)
                ),
                muted_cube_aliases=_muted_cube_aliases_for_request(request),
            )
        return OutputSavePlan(
            output_root=self._output_dir,
            path_pattern="{date}\\{run}_{cube#}_{workflow}_{source}",
            workflow_name=request.workflow_name,
            output_run_number=request.output_run_number,
            job_started_at=job_started_at,
            seed=seed,
            cube_numbers_by_alias=_cube_numbers_by_alias(request),
        )

    @staticmethod
    def _notify_failure(
        *,
        callbacks: GenerationCallbacks,
        failure: GenerationFailure,
    ) -> GenerationStartResult:
        """Emit failure callback and normalize failed start result payload."""
        callbacks.on_failure(failure)
        return GenerationStartResult(
            started=False,
            prompt_id=failure.prompt_id,
            failure=failure,
            generation_run_id=failure.generation_run_id,
            client_id=failure.client_id,
        )


def find_unresolved_uuid_class_types(workflow_payload: dict[str, object]) -> list[str]:
    """Return UUID class_type values that should be expanded before queueing."""
    unresolved: set[str] = set()
    for node in executable_prompt_nodes(workflow_payload).values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        if _UUID_CLASS_RE.match(class_type):
            unresolved.add(class_type)
    return sorted(unresolved)


def _cube_numbers_by_alias(request: PreparedGenerationRequest) -> dict[str, int]:
    """Return lookup keys for cube order from detached workflow state."""

    aliases = _ordered_cube_aliases_from_workflow(request.workflow)
    if aliases is None:
        aliases = ()
    numbers: dict[str, int] = {}
    for index, alias in enumerate(aliases, start=1):
        _add_cube_number_aliases(numbers, alias, index)
    return numbers


def _active_cube_aliases_for_request(
    request: PreparedGenerationRequest,
) -> tuple[str, ...]:
    """Return topology-ordered active cube aliases for persistence policy."""

    aliases = _ordered_cube_aliases_from_workflow(request.workflow)
    if aliases is not None:
        return aliases
    return ()


def _muted_cube_aliases_for_request(
    request: PreparedGenerationRequest,
) -> frozenset[str]:
    """Return workflow-local cube aliases whose outputs are memory-only."""

    workflow = request.workflow
    cubes = getattr(workflow, "cubes", None)
    if isinstance(cubes, Mapping):
        return frozenset(
            alias
            for alias, cube in cubes.items()
            if isinstance(alias, str)
            and getattr(cube, "output_persistence_enabled", True) is False
        )
    return frozenset()


def _ordered_cube_aliases_from_workflow(
    workflow: object | None,
) -> tuple[str, ...] | None:
    """Return stack-order aliases from a live workflow-like object when available."""

    stack_order = getattr(workflow, "stack_order", None)
    if not isinstance(stack_order, list | tuple):
        return None
    cubes = getattr(workflow, "cubes", None)
    if isinstance(cubes, Mapping):
        aliases = active_cube_aliases(cast(Any, workflow))
    else:
        aliases = tuple(
            alias for alias in stack_order if isinstance(alias, str) and alias
        )
    return aliases if aliases else None


def _add_cube_number_aliases(
    numbers: dict[str, int],
    alias: str,
    cube_number: int,
) -> None:
    """Index raw and display-form aliases for save-time source lookup."""

    for key in {alias, cube_alias_body(alias)}:
        cleaned = key.strip()
        if cleaned and cleaned not in numbers:
            numbers[cleaned] = cube_number


__all__ = [
    "GenerationCallbacks",
    "GenerationFailure",
    "GenerationRequest",
    "GenerationService",
    "GenerationStartResult",
    "PreparedGenerationRequest",
    "find_unresolved_uuid_class_types",
]
