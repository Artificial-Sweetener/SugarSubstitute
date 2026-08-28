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

"""Provide typed final Output pipeline test doubles."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
)


class SignalSpy:
    """Capture signal connections behind a minimal Qt-like boundary."""

    def __init__(self) -> None:
        """Initialize an empty callback collection."""

        self.callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Capture one callback connection."""

        self.callbacks.append(callback)


class PreparationDispatcherSpy:
    """Capture output preparation and capacity coordination."""

    def __init__(self) -> None:
        """Initialize signals, submissions, and capacity state."""

        self.prepared = SignalSpy()
        self.failed = SignalSpy()
        self.submitted: list[OutputImageCommitRequest] = []
        self.prepared_capacity: Callable[[], int] | None = None
        self.resume_count = 0

    def submit(self, request: OutputImageCommitRequest) -> None:
        """Capture one output preparation request."""

        self.submitted.append(request)

    def set_prepared_capacity(self, capacity: Callable[[], int]) -> None:
        """Capture the decoded-output admission boundary."""

        self.prepared_capacity = capacity

    def resume(self) -> None:
        """Record that prepared capacity became available."""

        self.resume_count += 1


class CommitQueueSpy:
    """Expose the bounded commit-queue collaboration contract."""

    def __init__(self) -> None:
        """Initialize the capacity signal used to resume decoding."""

        self.capacity_available = SignalSpy()

    def enqueue_prepared(self, output: object) -> None:
        """Accept one prepared output."""

        _ = output

    def enqueue_failed(self, failure: object) -> None:
        """Accept one failed output preparation."""

        _ = failure

    def available_prepared_slots(self) -> int:
        """Return deterministic decoded-output capacity."""

        return 2


class ProjectionSchedulerSpy:
    """Capture projection scheduler requests without timers."""

    def __init__(self) -> None:
        """Initialize captured scheduler calls."""

        self.requests: list[tuple[str, object, object]] = []
        self.discarded: list[str] = []
        self.renamed: list[tuple[str, str]] = []

    def request_projection(
        self,
        workflow_id: str,
        *,
        reason: object,
        registered_image_id: object = None,
    ) -> None:
        """Capture one projection request."""

        self.requests.append((workflow_id, reason, registered_image_id))

    def flush_pending_for_workflow(self, _workflow_id: str) -> None:
        """Accept flush requests for protocol compatibility."""

    def discard_workflow(self, workflow_id: str) -> None:
        """Capture workflow cleanup requests."""

        self.discarded.append(workflow_id)

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Capture workflow rename requests."""

        self.renamed.append((old_workflow_id, new_workflow_id))


class ProjectionCoordinatorSpy:
    """Capture direct Output projection coordinator calls."""

    def __init__(self) -> None:
        """Initialize captured projection calls."""

        self.projected: list[tuple[object, str, object]] = []

    def project_workflow(
        self,
        workflows: object,
        active_workflow_id: str,
        *,
        registered_image_id: object = None,
    ) -> None:
        """Record one active Output projection request."""

        self.projected.append((workflows, active_workflow_id, registered_image_id))


class TimingLookupStub:
    """Return deterministic cube timing for output pipeline tests."""

    def __init__(self) -> None:
        """Initialize lookup call capture."""

        self.calls: list[dict[str, str]] = []

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Record the lookup request and return a fixed duration."""

        self.calls.append(
            {
                "workflow_id": workflow_id,
                "source_key": source_key,
                "cube_alias": cube_alias,
            }
        )
        return 850.0


def noop_project_workflow(
    _workflow_id: str,
    _registered_image_id: object = None,
) -> None:
    """Accept projection callbacks for tests that do not inspect projection."""


def build_pipeline_shell_dependencies() -> dict[str, Any]:
    """Return shell collaborators irrelevant to route/visibility tests."""

    return {
        "workflow_session_service": SimpleNamespace(
            active_workflow_id="wf",
            workflows={"wf": object()},
            get_workflow=lambda _workflow_id: SimpleNamespace(metadata={}),
        ),
        "canvas_io_service": SimpleNamespace(
            resolve_node_meta_title=lambda _node_data: "Cube.Output",
            resolve_workflow_label=lambda _metadata: "Workflow",
        ),
        "output_commit_handler": SimpleNamespace(
            commit_prepared_output_image=lambda _prepared: None,
            handle_output_image_preparation_failed=lambda _failure: None,
        ),
        "output_canvas_projection_coordinator": ProjectionCoordinatorSpy(),
        "preparation_dispatcher": PreparationDispatcherSpy(),
        "commit_queue": CommitQueueSpy(),
    }
