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
from tests.presentation.shell.file_actions.support import (
    _EditorBusyRecorder,
    _QueuedRuntimeSubmitter,
)


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
    )
    service.required = required

    controller.resolve(
        workflow={"nodes": [], "links": []},
        target_workflow_id="wf-1",
        completed=completed.append,
        cancelled=lambda: None,
        failed=lambda error: (_ for _ in ()).throw(error),
    )
    try:
        resolution_submitter.requests[0].work(resolution_submitter.cancellations[0])
    except PortableWorkflowModelResolutionRequired as error:
        resolution_submitter.handles[0].complete_failed(error)

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
    assert busy_calls[-1] == ("end", "busy-token")
    assert submitter.closed


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

    with pytest.raises(PortableWorkflowModelResolutionRequired) as raised:
        submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_failed(raised.value)


def _unused_download_route() -> ModelDownloadRoute:
    """Fail if a success-only test unexpectedly requests download execution."""

    raise AssertionError("download route must not be requested")
