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

"""Verify asynchronous canonical-workflow model resolution coordination."""

from __future__ import annotations

from collections import OrderedDict
from typing import cast

import pytest

from substitute.app.bootstrap.execution_lane_configs import ExecutionLaneConfig
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime

from substitute.application.direct_workflows import (
    PendingPortableWorkflowResolution,
    PortableWorkflowModelResolutionRequired,
    ResolvedPortableWorkflow,
    PortableWorkflowModelResolutionService,
)
from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelDownloadResolutionService,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
    ResolvedRecipeModelScript,
)
from substitute.application.workflows.portable_model_projection import (
    CanonicalModelResolutionProjection,
)
from substitute.domain.common import JsonObject
from substitute.domain.recipes import ParsedSugarScript
from substitute.presentation.shell.direct_workflow_model_resolution import (
    DirectWorkflowModelResolutionController,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
)
from substitute.presentation.shell.model_resolution_execution import (
    ModelDownloadRoute,
    ModelResolutionRoute,
)
from substitute.presentation.shell.recipe_model_resolution_flow import (
    DeferredRecipeModelDownload,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from tests.presentation.shell.file_actions.support import (
    _EditorBusyRecorder,
    _QueuedRuntimeSubmitter,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _ImmediateDispatcher:
    """Run deterministic owner callbacks immediately in tests."""

    def publish(self, callback: object, *, reason: str) -> None:
        """Invoke one callback while retaining the production method shape."""

        _ = reason
        assert callable(callback)
        callback()


def test_controller_resolves_without_blocking_and_completes_on_owner_callback() -> None:
    """Canonical lookup work should run through the configured resolution lane."""

    submitter = _QueuedRuntimeSubmitter()
    completed: list[JsonObject] = []
    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, _ResolvedService()),
        editor_busy=cast(EditorBusyControllerProtocol, _EditorBusyRecorder()),
        prompt_for_download=lambda _required: None,
        resolution_route_factory=lambda **_kwargs: ModelResolutionRoute(
            submitter=submitter,
            close=submitter.close,
        ),
        download_route_factory=lambda **_kwargs: _unused_download_route(),
    )

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=completed.append,
        cancelled=lambda: None,
        failed=lambda error: (_ for _ in ()).throw(error),
    )

    assert completed == []
    outcome = submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_success(outcome)
    assert completed == [{"nodes": [], "links": [], "resolved": True}]
    assert submitter.closed


def test_controller_downloads_all_approved_models_before_completion() -> None:
    """A blocked canonical load should continue only after verified acquisition."""

    resolution_submitter = _QueuedRuntimeSubmitter()
    download_submitter = _QueuedRuntimeSubmitter()
    service = _PendingService()
    required = _required()
    download_service = _DownloadService()
    completed: list[JsonObject] = []
    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, service),
        editor_busy=cast(EditorBusyControllerProtocol, _EditorBusyRecorder()),
        prompt_for_download=lambda requested: DeferredRecipeModelDownload(
            service=cast(RecipeModelDownloadResolutionService, download_service),
            required=requested,
        ),
        resolution_route_factory=lambda **_kwargs: ModelResolutionRoute(
            submitter=resolution_submitter,
            close=resolution_submitter.close,
        ),
        download_route_factory=lambda **_kwargs: ModelDownloadRoute(
            submitter=download_submitter,
            progress_dispatcher=_ImmediateDispatcher(),
            close=download_submitter.close,
        ),
        defer_to_owner=lambda callback: callback(),
    )
    service.required = required

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=completed.append,
        cancelled=lambda: None,
        failed=lambda error: (_ for _ in ()).throw(error),
    )
    _complete_resolution_as_required(resolution_submitter)

    assert len(download_submitter.requests) == 1
    result = download_submitter.requests[0].work(download_submitter.cancellations[0])
    download_submitter.handles[0].complete_success(result)

    assert download_service.calls == 1
    assert completed == [{"nodes": [], "links": [], "downloaded": True}]


def test_controller_cancels_load_when_user_declines_model_acquisition() -> None:
    """Leave the current workflow untouched when model review is declined."""

    submitter = _QueuedRuntimeSubmitter()
    service = _PendingService()
    service.required = _required()
    busy_calls: list[object] = []
    cancelled: list[bool] = []
    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, service),
        editor_busy=cast(
            EditorBusyControllerProtocol,
            _EditorBusyRecorder(busy_calls),
        ),
        prompt_for_download=lambda _required: None,
        resolution_route_factory=lambda **_kwargs: ModelResolutionRoute(
            submitter=submitter,
            close=submitter.close,
        ),
        download_route_factory=lambda **_kwargs: _unused_download_route(),
        defer_to_owner=lambda callback: callback(),
    )

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=lambda _workflow: pytest.fail("declined load must not complete"),
        cancelled=lambda: cancelled.append(True),
        failed=lambda error: pytest.fail(f"declined load failed: {error}"),
    )
    _complete_resolution_as_required(submitter)

    assert cancelled == [True]
    assert cast(tuple[object, object], busy_calls[0])[0] == "begin"
    assert cast(tuple[str, tuple[str, str]], busy_calls[0])[1][1] == (
        "Checking model links"
    )
    assert busy_calls[-1] == ("end", "busy-token")
    assert submitter.closed


def test_controller_delivers_required_model_review_through_real_qt_runtime() -> None:
    """A worker-side resolution request must reach its Qt owner callback."""

    ensure_qt_application()
    runtime = ExecutionRuntime(
        lane_configs=(
            ExecutionLaneConfig(
                name="recipe_model_resolution",
                max_workers=1,
                queue_capacity=4,
                thread_name_prefix="test-model-resolution",
            ),
        )
    )
    service = _PendingService()
    service.required = _required()
    busy_calls: list[object] = []
    prompts: list[RecipeModelResolutionRequired] = []
    cancelled: list[bool] = []

    def resolution_route(**_kwargs: object) -> ModelResolutionRoute:
        """Create one production-shaped route through the real runtime."""

        submitter = runtime.submitter(
            "recipe_model_resolution",
            owner_id="real_qt_model_resolution",
            dispatcher=QtOwnerThreadDispatcher(),
        )
        return ModelResolutionRoute(submitter=submitter, close=submitter.close)

    def decline_prompt(required: RecipeModelResolutionRequired) -> None:
        """Record the review request and simulate explicit cancellation."""

        prompts.append(required)

    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, service),
        editor_busy=cast(EditorBusyControllerProtocol, _EditorBusyRecorder(busy_calls)),
        prompt_for_download=decline_prompt,
        resolution_route_factory=resolution_route,
        download_route_factory=lambda **_kwargs: _unused_download_route(),
    )

    try:
        controller.resolve(
            workflow={"nodes": [], "links": []},
            target_workflow_id="wf-real-qt",
            completed=lambda _workflow: pytest.fail("blocked load must not complete"),
            cancelled=lambda: cancelled.append(True),
            failed=lambda error: pytest.fail(f"blocked load failed: {error}"),
        )

        wait_for_qt_condition(lambda: cancelled == [True])

        assert prompts == [service.required]
        assert busy_calls[-1] == ("end", "busy-token")
    finally:
        runtime.shutdown()


def test_controller_defers_review_until_busy_completion_callback_unwinds() -> None:
    """Remove the busy wash before entering a model-review modal event loop."""

    submitter = _QueuedRuntimeSubmitter()
    service = _PendingService()
    service.required = _required()
    busy_calls: list[object] = []
    prompts: list[RecipeModelResolutionRequired] = []
    deferred_callbacks: list[object] = []
    cancelled: list[bool] = []
    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, service),
        editor_busy=cast(EditorBusyControllerProtocol, _EditorBusyRecorder(busy_calls)),
        prompt_for_download=lambda required: prompts.append(required),
        resolution_route_factory=lambda **_kwargs: ModelResolutionRoute(
            submitter=submitter,
            close=submitter.close,
        ),
        download_route_factory=lambda **_kwargs: _unused_download_route(),
        defer_to_owner=deferred_callbacks.append,
    )

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=lambda _workflow: pytest.fail("blocked load must not complete"),
        cancelled=lambda: cancelled.append(True),
        failed=lambda error: pytest.fail(f"blocked load failed: {error}"),
    )
    _complete_resolution_as_required(submitter)

    assert busy_calls[-1] == ("end", "busy-token")
    assert prompts == []
    assert cancelled == []
    assert len(deferred_callbacks) == 1

    callback = deferred_callbacks.pop()
    assert callable(callback)
    callback()

    assert prompts == [service.required]
    assert cancelled == [True]


def test_controller_surfaces_download_failure_and_releases_busy_state() -> None:
    """Report a failed acquisition while closing every transient UI owner."""

    resolution_submitter = _QueuedRuntimeSubmitter()
    download_submitter = _QueuedRuntimeSubmitter()
    service = _PendingService()
    service.required = _required()
    busy_calls: list[object] = []
    failures: list[BaseException] = []
    controller = DirectWorkflowModelResolutionController(
        service=cast(PortableWorkflowModelResolutionService, service),
        editor_busy=cast(
            EditorBusyControllerProtocol,
            _EditorBusyRecorder(busy_calls),
        ),
        prompt_for_download=lambda requested: DeferredRecipeModelDownload(
            service=cast(RecipeModelDownloadResolutionService, _DownloadService()),
            required=requested,
        ),
        resolution_route_factory=lambda **_kwargs: ModelResolutionRoute(
            submitter=resolution_submitter,
            close=resolution_submitter.close,
        ),
        download_route_factory=lambda **_kwargs: ModelDownloadRoute(
            submitter=download_submitter,
            progress_dispatcher=_ImmediateDispatcher(),
            close=download_submitter.close,
        ),
        defer_to_owner=lambda callback: callback(),
    )

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=lambda _workflow: pytest.fail("failed load must not complete"),
        cancelled=lambda: pytest.fail("failed load must not cancel"),
        failed=failures.append,
    )
    _complete_resolution_as_required(resolution_submitter)
    download_error = RuntimeError("BackEnd rejected the verified model")
    download_submitter.handles[0].complete_failed(download_error)

    assert failures == [download_error]
    assert busy_calls.count(("end", "busy-token")) == 2
    assert resolution_submitter.closed
    assert download_submitter.closed


class _ResolvedService:
    """Resolve a graph immediately when its queued work runs."""

    def resolve(self, workflow: JsonObject) -> ResolvedPortableWorkflow:
        """Return a visibly resolved detached graph."""

        return ResolvedPortableWorkflow(
            workflow={**workflow, "resolved": True},
            summary=RecipeModelResolutionSummary(hash_matches=1),
        )


class _PendingService:
    """Require one download and then complete its canonical graph."""

    required: RecipeModelResolutionRequired

    def resolve(self, workflow: JsonObject) -> ResolvedPortableWorkflow:
        """Raise one user-review request."""

        pending = PendingPortableWorkflowResolution(
            workflow=workflow,
            projection=cast(CanonicalModelResolutionProjection, object()),
            required=self.required,
        )
        raise PortableWorkflowModelResolutionRequired(pending)

    def complete(
        self,
        pending: PendingPortableWorkflowResolution,
        parsed_script: ParsedSugarScript,
    ) -> ResolvedPortableWorkflow:
        """Return a graph marked with completed acquisition."""

        _ = parsed_script
        return ResolvedPortableWorkflow(
            workflow={**pending.workflow, "downloaded": True},
            summary=RecipeModelResolutionSummary(hash_matches=1),
        )


class _DownloadService:
    """Return a resolved script after one approved acquisition call."""

    def __init__(self) -> None:
        self.calls = 0

    def download_and_resolve(self, required: object, **_kwargs: object) -> object:
        """Return the request's partial script as a completed result."""

        self.calls += 1
        typed = cast(RecipeModelResolutionRequired, required)
        return ResolvedRecipeModelScript(
            parsed_script=typed.partial_script,
            summary=RecipeModelResolutionSummary(hash_matches=1),
        )


def _required() -> RecipeModelResolutionRequired:
    """Build one minimal blocked model request."""

    parsed = ParsedSugarScript(
        buffers=OrderedDict(),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    reference = RecipeModelUnresolvedReference(
        alias="Cube",
        node_name="model",
        input_key="ckpt_name",
        kind="checkpoints",
        value="missing.safetensors",
        sha256="A" * 64,
        civitai_state=RecipeModelCivitaiState.DISABLED,
    )
    return RecipeModelResolutionRequired(
        references=(reference,),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=1),
    )


def _complete_resolution_as_required(submitter: _QueuedRuntimeSubmitter) -> None:
    """Drive one queued canonical resolution into its review callback."""

    review = submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_success(review)


def _unused_download_route() -> ModelDownloadRoute:
    """Fail if a success-only test unexpectedly requests download execution."""

    raise AssertionError("download route must not be requested")
