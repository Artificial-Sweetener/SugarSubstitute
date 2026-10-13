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

"""Prove queue cancellation revokes detached preparation before UI admission."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

import pytest

from substitute.application.generation import (
    GenerationPreparationResult,
    GenerationService,
)
from substitute.application.generation.job_queue_service import (
    GenerationJobQueueService,
)
from substitute.domain.generation import GenerationJobSnapshot
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
    QueuedGenerationPreparationJob,
    WorkspaceGenerationController,
)
from tests.application.generation.job_queue.queue_service_test_support import (
    _FakeDispatcher,
)
from tests.presentation.shell.generation.controller.support import (
    _BindingRecorder,
    _FakeGenerationService,
    _build_bindings,
)
from substitute.presentation.shell.workspace_generation_preparation_executor import (
    GenerationPreparationExecutor,
)
from tests.support.execution import QueuedTaskSubmitter


@dataclass
class _CancellationHarness:
    """Own real queue/controller lifetimes around a manually settled worker boundary."""

    controller: WorkspaceGenerationController
    queue: GenerationJobQueueService
    dispatcher: _FakeDispatcher
    submitter: QueuedTaskSubmitter
    recorder: _BindingRecorder
    prepared: list[str]

    def bindings(
        self, workflow_id: str, *, batch_count: int = 1
    ) -> GenerationUiBindings:
        """Capture independent document identity and scene bookkeeping callbacks."""

        snapshot = GenerationJobSnapshot(
            workflow_id=workflow_id, workflow_name=workflow_id
        )

        def on_prepared(
            result: GenerationPreparationResult,
        ) -> tuple[GenerationJobSnapshot, ...]:
            """Record scene bookkeeping only for admitted preparation results."""

            self.prepared.append(workflow_id)
            return result.snapshots

        base_bindings = _build_bindings(self.recorder)
        return GenerationUiBindings(
            build_generation_request=base_bindings.build_generation_request,
            randomize_seeds=base_bindings.randomize_seeds,
            on_progress=base_bindings.on_progress,
            on_model_load_progress=base_bindings.on_model_load_progress,
            on_preview=base_bindings.on_preview,
            on_output_image=base_bindings.on_output_image,
            on_output_video=base_bindings.on_output_video,
            on_failure=base_bindings.on_failure,
            on_timing=base_bindings.on_timing,
            on_completed=base_bindings.on_completed,
            refresh_generation_actions=base_bindings.refresh_generation_actions,
            effective_batch_count=lambda: batch_count,
            capture_queued_generation_preparation=lambda: (
                QueuedGenerationPreparationJob(
                    prepare_snapshots=lambda: GenerationPreparationResult(
                        snapshots=(snapshot,)
                    ),
                    on_prepared=on_prepared,
                )
            ),
        )

    def complete(self, index: int, workflow_id: str) -> None:
        """Settle one captured worker without sleeps or native backend work."""

        self.submitter.handles[index].complete_success(
            GenerationPreparationResult(
                snapshots=(
                    GenerationJobSnapshot(
                        workflow_id=workflow_id,
                        workflow_name=workflow_id,
                    ),
                )
            )
        )


@pytest.fixture
def cancellation_harness() -> Iterator[_CancellationHarness]:
    """Dispose controller and queue resources even when a race assertion fails."""

    submitter = QueuedTaskSubmitter()
    dispatcher = _FakeDispatcher()
    queue = GenerationJobQueueService(dispatcher)
    controller = WorkspaceGenerationController(
        cast(GenerationService, _FakeGenerationService()),
        queue,
        preparation_executor=GenerationPreparationExecutor(submitter),
    )
    harness = _CancellationHarness(
        controller,
        queue,
        dispatcher,
        submitter,
        _BindingRecorder([], [], [], [], [], []),
        [],
    )
    try:
        yield harness
    finally:
        controller.close()
        queue.shutdown()


@pytest.mark.parametrize("active", [False, True])
def test_cancel_queue_cancels_pending_preparation_before_admission(
    cancellation_harness: _CancellationHarness,
    active: bool,
) -> None:
    """Cancel affects pending captures even with no job yet admitted to the queue."""

    h = cancellation_harness
    if active:
        h.controller.handle_generate_clicked(
            current_mode="generate", bindings=h.bindings("active")
        )
        h.complete(0, "active")
        assert h.queue.has_cancellable_jobs()
    h.controller.handle_generate_clicked(
        current_mode="generate", bindings=h.bindings("pending")
    )
    h.controller.cancel_generation_queue()

    assert h.submitter.handles[-1].state == "cancelled"
    assert h.submitter.cancellations[-1].is_cancelled
    assert not h.queue.has_cancellable_jobs()
    assert h.prepared == (["active"] if active else [])
    assert h.recorder.failures == []
    assert [request.workflow_id for request in h.dispatcher.requests] == (
        ["active"] if active else []
    )


def test_cancel_all_documents_and_batches_preserves_new_out_of_order_submissions(
    cancellation_harness: _CancellationHarness,
) -> None:
    """All pre-cancel captures are revoked; later document captures retain their identity."""

    h = cancellation_harness
    for workflow_id in ("old-a", "old-b"):
        h.controller.handle_generate_clicked(
            current_mode="generate", bindings=h.bindings(workflow_id, batch_count=2)
        )
    h.controller.cancel_generation_queue()
    assert [handle.state for handle in h.submitter.handles] == ["cancelled"] * 4
    for workflow_id in ("new-a", "new-b"):
        h.controller.handle_generate_clicked(
            current_mode="generate", bindings=h.bindings(workflow_id)
        )
    h.complete(5, "new-b")
    h.complete(4, "new-a")

    assert h.prepared == ["new-b", "new-a"]
    assert [job.snapshot.workflow_id for job in h.queue.jobs()] == ["new-b", "new-a"]
    assert h.dispatcher.requests[0].workflow_id == "new-b"
    assert h.recorder.failures == []


def test_failure_after_cancel_then_retry_remains_reportable(
    cancellation_harness: _CancellationHarness,
) -> None:
    """Cancelling old captures must not suppress a new failure or its subsequent retry."""

    h = cancellation_harness
    h.controller.handle_generate_clicked(
        current_mode="generate", bindings=h.bindings("old")
    )
    h.controller.cancel_generation_queue()
    h.controller.handle_generate_clicked(
        current_mode="generate", bindings=h.bindings("new")
    )
    h.submitter.handles[1].complete_failed(RuntimeError("new preparation failed"))
    assert [failure.message for failure in h.recorder.failures] == [
        "new preparation failed"
    ]
    h.controller.handle_generate_clicked(
        current_mode="generate", bindings=h.bindings("retry")
    )
    h.complete(2, "retry")
    assert [request.workflow_id for request in h.dispatcher.requests] == ["retry"]


def test_cancel_pending_continuous_cycle_allows_clean_restart(
    cancellation_harness: _CancellationHarness,
) -> None:
    """A cancelled continuous capture must not join the next continuous lifecycle."""

    h = cancellation_harness
    h.controller.handle_generate_clicked(
        current_mode="continuous", bindings=h.bindings("old")
    )
    h.controller.cancel_generation_queue()
    assert not h.controller.is_continuous_active
    assert h.submitter.handles[0].state == "cancelled"
    h.controller.handle_generate_clicked(
        current_mode="continuous", bindings=h.bindings("new")
    )
    h.complete(1, "new")
    assert h.controller.is_continuous_active
    assert h.prepared == ["new"]
    assert [request.workflow_id for request in h.dispatcher.requests] == ["new"]
