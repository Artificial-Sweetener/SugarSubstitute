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

"""Coordinate portable canonical-workflow model resolution on runtime lanes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from sugarsubstitute_shared.localization import app_text

from substitute.application.direct_workflows import (
    PendingPortableWorkflowResolution,
    PortableWorkflowModelResolutionRequired,
    PortableWorkflowModelResolutionService,
    ResolvedPortableWorkflow,
)
from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
)
from substitute.application.model_metadata import (
    BackendModelDownloadJob,
    ModelDownloadStatus,
)
from substitute.application.recipes import (
    RecipeModelResolutionRequired,
    ResolvedRecipeModelScript,
)
from substitute.domain.common import JsonObject
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
    EditorBusyDownloadState,
)
from substitute.presentation.shell.model_download_progress import (
    model_download_detail,
    model_download_label,
    model_download_message,
    model_download_progress,
)
from substitute.presentation.shell.model_resolution_execution import (
    ModelDownloadRoute,
    ModelDownloadRouteFactory,
    ModelResolutionRoute,
    ModelResolutionRouteFactory,
)
from substitute.presentation.shell.recipe_model_resolution_flow import (
    DeferredRecipeModelDownload,
)


@dataclass(slots=True)
class _ActiveResolution:
    """Retain a resolution route until its owner-thread callback completes."""

    scope: TaskScope
    route: ModelResolutionRoute
    busy_token: object


@dataclass(slots=True)
class _ActiveDownload:
    """Retain a verified-download route and cancellation state."""

    route: ModelDownloadRoute
    cancellation: CancellationSource
    busy_token: object


class DirectWorkflowModelResolutionController:
    """Resolve and acquire canonical workflow models before materialization."""

    def __init__(
        self,
        *,
        service: PortableWorkflowModelResolutionService,
        editor_busy: EditorBusyControllerProtocol,
        prompt_for_download: Callable[
            [RecipeModelResolutionRequired], DeferredRecipeModelDownload | None
        ],
        resolution_route_factory: ModelResolutionRouteFactory,
        download_route_factory: ModelDownloadRouteFactory,
    ) -> None:
        """Store application, user-decision, progress, and execution owners."""

        self._service = service
        self._editor_busy = editor_busy
        self._prompt_for_download = prompt_for_download
        self._resolution_route_factory = resolution_route_factory
        self._download_route_factory = download_route_factory
        self._request_id = 0
        self._resolutions: list[_ActiveResolution] = []
        self._downloads: list[_ActiveDownload] = []

    def resolve(
        self,
        *,
        workflow: JsonObject,
        target_workflow_id: str,
        completed: Callable[[JsonObject], None],
        cancelled: Callable[[], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Resolve one detached graph without blocking the Qt owner thread."""

        request_id = self._next_request_id()
        route = self._resolution_route_factory(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )
        scope = TaskScope(
            submitter=route.submitter,
            scope_id=f"portable_model_resolution_{target_workflow_id}_{request_id}",
        )
        busy_token = self._editor_busy.begin(
            target_workflow_id,
            message=app_text("Checking model links…"),
        )
        active = _ActiveResolution(scope, route, busy_token)
        self._resolutions.append(active)
        request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="portable_model_resolution",
                parts=(("workflow_id", target_workflow_id),),
            ),
            context=ExecutionContext(
                operation="portable_model_resolution",
                reason="canonical_workflow_load",
                lane="recipe_model_resolution",
                safe_fields=(("workflow_id", target_workflow_id),),
            ),
            work=lambda _token: self._service.resolve(workflow),
        )

        def receive(outcome: TaskOutcome[object]) -> None:
            """Continue with materialization, user review, or failure presentation."""

            self._finish_resolution(active)
            if outcome.status == "cancelled":
                cancelled()
                return
            if outcome.status == "failed":
                error = outcome.error
                if isinstance(error, PortableWorkflowModelResolutionRequired):
                    deferred = self._prompt_for_download(error.pending.required)
                    if deferred is None:
                        cancelled()
                        return
                    self._download(
                        pending=error.pending,
                        request=deferred,
                        target_workflow_id=target_workflow_id,
                        completed=completed,
                        cancelled=cancelled,
                        failed=failed,
                    )
                    return
                failed(error or RuntimeError("Workflow model resolution failed."))
                return
            resolved = cast(ResolvedPortableWorkflow, outcome.result)
            completed(resolved.workflow)

        try:
            handle = scope.submit(request)
            handle.add_done_callback(receive, reason="portable_model_resolution_done")
        except Exception:
            self._finish_resolution(active)
            raise

    def _download(
        self,
        *,
        pending: PendingPortableWorkflowResolution,
        request: DeferredRecipeModelDownload,
        target_workflow_id: str,
        completed: Callable[[JsonObject], None],
        cancelled: Callable[[], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Run approved verified downloads and complete stable field projection."""

        request_id = self._next_request_id()
        route = self._download_route_factory(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )
        cancellation = CancellationSource(generation=request_id)
        label = model_download_label(request.required)
        busy_token = self._editor_busy.begin(
            target_workflow_id,
            message=app_text("Downloading %1", label),
        )
        active = _ActiveDownload(route, cancellation, busy_token)
        self._downloads.append(active)
        self._editor_busy.set_cancel_callback(
            busy_token,
            lambda: cancellation.cancel(reason="portable_model_download_cancelled"),
        )
        self._publish_progress(
            active,
            BackendModelDownloadJob(
                job_id="pending",
                status=ModelDownloadStatus.QUEUED,
                kind=request.required.references[0].kind,
                sha256=request.required.references[0].sha256,
                value=None,
                result=None,
                error=None,
            ),
            label=label,
        )
        task: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="portable_model_download",
                parts=(("workflow_id", target_workflow_id),),
                cancellation_generation=cancellation.generation,
            ),
            context=ExecutionContext(
                operation="portable_model_download",
                reason="canonical_workflow_load",
                lane="model_download",
                safe_fields=(("workflow_id", target_workflow_id),),
            ),
            work=lambda token: request.service.download_and_resolve(
                request.required,
                api_key_override=request.api_key_override,
                progress_callback=lambda job: route.progress_dispatcher.publish(
                    lambda: self._publish_progress(active, job, label=label),
                    reason="portable_model_download_progress",
                ),
                should_cancel=lambda: token.is_cancelled,
            ),
        )

        def receive(outcome: TaskOutcome[object]) -> None:
            """Complete projection after every verified transfer settles."""

            self._finish_download(active)
            if outcome.status == "cancelled":
                cancelled()
                return
            if outcome.status == "failed":
                failed(outcome.error or RuntimeError("Model download failed."))
                return
            resolved = cast(ResolvedRecipeModelScript, outcome.result)
            completed(self._service.complete(pending, resolved.parsed_script).workflow)

        try:
            handle = route.submitter.submit(task, cancellation=cancellation)
            handle.add_done_callback(receive, reason="portable_model_download_done")
        except Exception:
            self._finish_download(active)
            raise

    def _publish_progress(
        self,
        active: _ActiveDownload,
        job: BackendModelDownloadJob,
        *,
        label: str,
    ) -> None:
        """Project one BackEnd job update into the workflow busy overlay."""

        self._editor_busy.update_download(
            active.busy_token,
            EditorBusyDownloadState(
                title=app_text("Downloading %1", label),
                message=model_download_message(job),
                detail=model_download_detail(job),
                progress_per_mille=model_download_progress(job),
                cancel_enabled=job.status
                not in {ModelDownloadStatus.COMPLETE, ModelDownloadStatus.FAILED},
            ),
        )

    def _finish_resolution(self, active: _ActiveResolution) -> None:
        """Release one completed resolution operation exactly once."""

        self._editor_busy.end(active.busy_token)
        active.scope.close(reason="portable_model_resolution_finished")
        active.route.close()
        if active in self._resolutions:
            self._resolutions.remove(active)

    def _finish_download(self, active: _ActiveDownload) -> None:
        """Release one completed download operation exactly once."""

        self._editor_busy.set_cancel_callback(active.busy_token, None)
        self._editor_busy.end(active.busy_token)
        active.route.close()
        if active in self._downloads:
            self._downloads.remove(active)

    def _next_request_id(self) -> int:
        """Return a controller-local monotonically increasing request identity."""

        self._request_id += 1
        return self._request_id


__all__ = ["DirectWorkflowModelResolutionController"]
