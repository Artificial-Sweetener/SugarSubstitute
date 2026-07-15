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

"""Tests for pending Cube Library update coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, cast

from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.execution_testing import ManualTaskHandle
from substitute.application.cube_library import (
    CubeLibraryUpdateCoordinator,
    CubeLibraryUpdateReason,
    LoadedCubeUpdateAction,
)
from substitute.application.cube_library.update_detection import (
    CubeLibraryUpdateDetectionService,
    LoadedCubeUpdateCandidate,
)
from substitute.domain.cube_library import CubeCatalog
from substitute.domain.cube_library import CubeUpdatePolicy

TResult = TypeVar("TResult")


@dataclass(frozen=True)
class _Update:
    """Represent a backend change notification for coordinator tests."""

    catalog_revision: str = "rev-2"
    previous_catalog_revision: str = "rev-1"
    reason: str = "catalog-revision-changed"


class _Client:
    """Return a fixed catalog."""

    def __init__(self, catalog: CubeCatalog | None = None) -> None:
        """Store the test catalog."""

        self.catalog = catalog

    def get_catalog(self) -> CubeCatalog | None:
        """Return the configured catalog."""

        return self.catalog


class _Detection(CubeLibraryUpdateDetectionService):
    """Return configured candidates for coordinator tests."""

    def __init__(self, candidates: tuple[LoadedCubeUpdateCandidate, ...]) -> None:
        """Store deterministic candidates."""

        self._candidates = candidates

    def detect_updates(
        self,
        *,
        workflows: object,
        workflow_names: object,
        catalog: CubeCatalog,
    ) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return deterministic candidates."""

        _ = workflows, workflow_names, catalog
        return self._candidates


class _RecordingSubmitter:
    """Capture submitted update refresh requests for deterministic execution."""

    def __init__(self) -> None:
        """Create empty submission records."""

        self.requests: list[TaskRequest[None]] = []
        self.handles: list[ManualTaskHandle[None]] = []
        self.cancellations: list[CancellationToken] = []

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Record one request and return a manual handle."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[None], request))
        self.handles.append(cast(ManualTaskHandle[None], handle))
        self.cancellations.append(cancellation)
        return handle


def test_pending_candidates_are_deduplicated() -> None:
    """Duplicate candidate identities should collapse to one pending update."""

    candidate = _candidate()
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {},
        workflow_name_provider=lambda: {},
        detection_service=_Detection((candidate, candidate)),
    )

    pending = coordinator.refresh_now()

    assert pending == (candidate,)


def test_mark_presented_removes_candidates_for_modal_cycle() -> None:
    """Presented candidates should leave the pending batch."""

    candidate = _candidate()
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {},
        workflow_name_provider=lambda: {},
        detection_service=_Detection((candidate,)),
    )
    coordinator.refresh_now()

    coordinator.mark_presented((candidate,))

    assert coordinator.collect_pending_on_focus() == ()


def test_queue_pending_replaces_pending_candidates() -> None:
    """Startup restore can seed a deferred modal without a catalog refresh."""

    first = _candidate(alias="Demo")
    second = _candidate(alias="Other")
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {},
        workflow_name_provider=lambda: {},
    )
    coordinator.queue_pending((first,))

    coordinator.queue_pending((second,))

    assert coordinator.collect_pending_on_focus() == (second,)


def test_follow_latest_candidates_request_automatic_update_without_pending_modal() -> (
    None
):
    """Follow-latest stale cubes should auto-update instead of prompting."""

    pinned = _candidate(alias="Pinned")
    follow = _candidate(alias="Follow", update_policy=CubeUpdatePolicy.FOLLOW_LATEST)
    requested: list[object] = []
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {},
        workflow_name_provider=lambda: {},
        detection_service=_Detection((pinned, follow)),
        automatic_selections_requested=requested.append,
    )

    pending = coordinator.refresh_now()

    assert pending == (pinned,)
    assert len(requested) == 1
    selections = requested[0]
    assert isinstance(selections, tuple)
    assert selections[0].candidate == follow
    assert selections[0].action == LoadedCubeUpdateAction.FOLLOW_LATEST


def test_follow_latest_candidates_remain_pending_without_automatic_owner() -> None:
    """A coordinator without an automatic owner should keep stale cubes visible."""

    follow = _candidate(alias="Follow", update_policy=CubeUpdatePolicy.FOLLOW_LATEST)
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {},
        workflow_name_provider=lambda: {},
        detection_service=_Detection((follow,)),
    )

    assert coordinator.refresh_now() == (follow,)


def test_refresh_async_uses_submitter_and_collapses_follow_up_refreshes() -> None:
    """Async refresh should use the injected execution boundary without threads."""

    candidate = _candidate()
    submitter = _RecordingSubmitter()
    detections: list[object] = []

    class _CountingDetection(CubeLibraryUpdateDetectionService):
        """Record each refresh pass."""

        def detect_updates(
            self,
            *,
            workflows: object,
            workflow_names: object,
            catalog: CubeCatalog,
        ) -> tuple[LoadedCubeUpdateCandidate, ...]:
            """Return one candidate while recording the pass."""

            detections.append((workflows, workflow_names, catalog))
            return (candidate,)

    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {"wf": object()},
        workflow_name_provider=lambda: {"wf": "Workflow"},
        detection_service=_CountingDetection(),
        refresh_submitter=submitter,
    )

    coordinator.refresh_async()
    coordinator.refresh_async()

    assert len(submitter.requests) == 1
    submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_success(None)

    assert len(detections) == 2
    assert coordinator.collect_pending_on_focus() == (candidate,)


def test_refresh_async_cancels_pending_refresh_on_shutdown() -> None:
    """Coordinator shutdown should cancel owner-scoped refresh work."""

    submitter = _RecordingSubmitter()
    coordinator = CubeLibraryUpdateCoordinator(
        catalog_client=_Client(_empty_catalog()),
        workflow_provider=lambda: {"wf": object()},
        workflow_name_provider=lambda: {"wf": "Workflow"},
        detection_service=_Detection((_candidate(),)),
        refresh_submitter=submitter,
    )

    coordinator.refresh_async()
    assert len(submitter.requests) == 1
    assert submitter.cancellations[0].is_cancelled is False

    coordinator.shutdown()
    coordinator.refresh_async()

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "cube_library_update_shutdown"
    assert submitter.handles[0].cancel_reason == "cube_library_update_shutdown"
    assert len(submitter.requests) == 1


def _candidate(
    alias: str = "Demo",
    *,
    update_policy: CubeUpdatePolicy = CubeUpdatePolicy.PINNED,
) -> LoadedCubeUpdateCandidate:
    """Build a single update candidate."""

    return LoadedCubeUpdateCandidate(
        workflow_id="workflow-1",
        workflow_name="Workflow One",
        cube_alias=alias,
        cube_id="owner/repo/demo.cube",
        current_version="1.0",
        latest_version="2.0",
        catalog_revision="rev",
        display_name="Demo Cube",
        reason=CubeLibraryUpdateReason.VERSION_DRIFT,
        update_policy=update_policy,
    )


def _empty_catalog() -> CubeCatalog:
    """Build an empty catalog snapshot."""

    return CubeCatalog(
        schema_version=1,
        catalog_revision="rev",
        generated_at="",
        cubes=(),
    )
