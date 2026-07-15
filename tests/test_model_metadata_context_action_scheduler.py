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

"""Tests for model metadata context action execution scheduling."""

from __future__ import annotations

from typing import TypeVar, cast
from uuid import uuid4

from substitute.application.execution import CancellationToken, TaskRequest
from tests.execution_testing import ManualTaskHandle
from substitute.application.model_metadata import (
    ManualModelMetadataRefreshRequest,
    ManualModelMetadataRefreshResult,
    ManualModelMetadataRefreshStatus,
    RefreshCancellationToken,
    SetModelThumbnailFromOutputRequest,
    SetModelThumbnailFromOutputResult,
    SetModelThumbnailFromOutputStatus,
)
from substitute.presentation.shell.model_metadata_context_action_handler import (
    ModelMetadataContextActionScheduler,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
)

TResult = TypeVar("TResult")


class _RecordingSubmitter:
    """Record execution requests and let tests run them manually."""

    def __init__(self) -> None:
        """Initialize an empty submission log."""

        self.requests: list[TaskRequest[object]] = []
        self.cancellations: list[CancellationToken] = []
        self.handles: list[ManualTaskHandle[object]] = []

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Record one request without executing it."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[object], request))
        self.cancellations.append(cancellation)
        self.handles.append(cast(ManualTaskHandle[object], handle))
        return handle

    def run_next(self) -> None:
        """Execute the oldest recorded request and complete its handle."""

        request = self.requests.pop(0)
        cancellation = self.cancellations.pop(0)
        handle = self.handles.pop(0)
        result = request.work(cancellation)
        handle.complete_success(result)


class _RefreshService:
    """Record manual refresh requests."""

    def __init__(self) -> None:
        """Initialize refresh observations."""

        self.requests: list[ManualModelMetadataRefreshRequest] = []
        self.cancellations: list[RefreshCancellationToken] = []

    def refresh_model(
        self,
        request: ManualModelMetadataRefreshRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ManualModelMetadataRefreshResult:
        """Record and complete one manual refresh."""

        self.requests.append(request)
        self.cancellations.append(cancellation_token)
        return ManualModelMetadataRefreshResult(
            status=ManualModelMetadataRefreshStatus.UPDATED,
            kind=request.kind,
            value=request.value,
        )


class _ThumbnailService:
    """Record output thumbnail assignment requests."""

    def __init__(self) -> None:
        """Initialize thumbnail observations."""

        self.requests: list[SetModelThumbnailFromOutputRequest] = []
        self.cancellations: list[RefreshCancellationToken] = []

    def set_thumbnail(
        self,
        request: SetModelThumbnailFromOutputRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> SetModelThumbnailFromOutputResult:
        """Record and complete one thumbnail assignment."""

        self.requests.append(request)
        self.cancellations.append(cancellation_token)
        return SetModelThumbnailFromOutputResult(
            status=SetModelThumbnailFromOutputStatus.UPDATED,
            kind=request.kind,
            value=request.value,
            image_id=request.image_id,
        )


def test_manual_refresh_submits_model_metadata_execution_request() -> None:
    """Manual refresh should run through the app execution submitter."""

    submitter = _RecordingSubmitter()
    refresh_service = _RefreshService()
    scheduler = ModelMetadataContextActionScheduler(
        refresh_service=refresh_service,
        submitter=submitter,
    )

    scheduler.refresh_civitai_metadata(_target())

    assert len(submitter.requests) == 1
    request = submitter.requests[0]
    assert request.identity.domain == "model_metadata"
    assert request.identity.field_value("operation_key") == "manual_refresh"
    assert request.context.operation == "manual_model_metadata_refresh"
    assert request.context.lane == "model_metadata"
    assert request.context.field_value("kind") == "loras"
    submitter.run_next()
    assert refresh_service.requests == [
        ManualModelMetadataRefreshRequest(kind="loras", value="models/a.safetensors")
    ]


def test_manual_refresh_coalesces_duplicate_target_while_in_flight() -> None:
    """A duplicate context-menu refresh should not queue while its key is running."""

    submitter = _RecordingSubmitter()
    refresh_service = _RefreshService()
    scheduler = ModelMetadataContextActionScheduler(
        refresh_service=refresh_service,
        submitter=submitter,
    )
    target = _target()

    scheduler.refresh_civitai_metadata(target)
    scheduler.refresh_civitai_metadata(target)

    assert len(submitter.requests) == 1
    submitter.run_next()
    scheduler.refresh_civitai_metadata(target)
    assert len(submitter.requests) == 1


def test_output_thumbnail_assignment_uses_model_metadata_submitter() -> None:
    """Output thumbnail assignment should share the model metadata execution lane."""

    submitter = _RecordingSubmitter()
    refresh_service = _RefreshService()
    thumbnail_service = _ThumbnailService()
    scheduler = ModelMetadataContextActionScheduler(
        refresh_service=refresh_service,
        output_thumbnail_service=thumbnail_service,
        submitter=submitter,
    )
    image_id = uuid4()

    scheduler.set_thumbnail_from_output_image(_target(), image_id)

    assert len(submitter.requests) == 1
    request = submitter.requests[0]
    assert request.identity.domain == "model_metadata"
    assert request.identity.field_value("operation_key") == (
        "output_thumbnail_assignment"
    )
    assert request.context.operation == "output_thumbnail_assignment"
    submitter.run_next()
    assert thumbnail_service.requests == [
        SetModelThumbnailFromOutputRequest(
            kind="loras",
            value="models/a.safetensors",
            image_id=image_id,
        )
    ]


def test_shutdown_closes_injected_runtime_submitter_route() -> None:
    """Scheduler shutdown should release the injected runtime submitter route."""

    closed: list[bool] = []
    submitter = _RecordingSubmitter()
    scheduler = ModelMetadataContextActionScheduler(
        refresh_service=_RefreshService(),
        submitter=submitter,
        close_submitter=lambda: closed.append(True),
    )

    scheduler.refresh_civitai_metadata(_target())
    assert submitter.cancellations[0].is_cancelled is False

    scheduler.shutdown()
    scheduler.refresh_civitai_metadata(_target())

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == (
        "model_metadata_context_actions_shutdown"
    )
    assert submitter.handles[0].cancel_reason == (
        "model_metadata_context_actions_shutdown"
    )
    assert closed == [True]


def test_shutdown_cancels_pending_output_thumbnail_assignment() -> None:
    """Output-thumbnail assignment should share scheduler-scope cancellation."""

    submitter = _RecordingSubmitter()
    scheduler = ModelMetadataContextActionScheduler(
        refresh_service=_RefreshService(),
        output_thumbnail_service=_ThumbnailService(),
        submitter=submitter,
    )

    scheduler.set_thumbnail_from_output_image(_target(), uuid4())
    scheduler.shutdown()

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == (
        "model_metadata_context_actions_shutdown"
    )


def _target() -> ModelMetadataContextMenuTarget:
    """Return a local model metadata target."""

    return ModelMetadataContextMenuTarget(
        title="A",
        backend_value="models/a.safetensors",
        model_kind="loras",
    )
