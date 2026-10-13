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

"""Contract tests for workspace generation presentation controller behavior."""

from __future__ import annotations

import weakref
from threading import Event

import pytest

from substitute.infrastructure.execution import ThreadPoolExecutionLane
from tests.support.execution import RecordingDispatcher


from substitute.application.generation import (
    GenerationPreparationResult,
)
from substitute.presentation.shell.workspace_generation_preparation_executor import (
    GenerationPreparationExecutor,
)
from tests.support.execution import QueuedTaskSubmitter


def test_generation_preparation_executor_close_cancels_and_suppresses_callbacks() -> (
    None
):
    """Closing generation preparation should cancel scoped work and drop callbacks."""

    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    completed: list[GenerationPreparationResult] = []
    failed: list[BaseException] = []
    executor = GenerationPreparationExecutor(
        submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )

    executor.submit(
        prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
        on_completed=completed.append,
        on_failed=failed.append,
    )

    assert len(submitter.handles) == 1
    assert submitter.handles[0].state == "pending"

    executor.close()

    assert close_calls == ["closed"]
    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "generation_preparation_executor_closed"
    assert submitter.handles[0].state == "cancelled"
    assert completed == []
    assert failed == []

    try:
        executor.submit(
            prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
            on_completed=completed.append,
            on_failed=failed.append,
        )
    except RuntimeError as error:
        assert "closed" in str(error)
    else:
        raise AssertionError("closed generation preparation accepted new work")


@pytest.mark.parametrize("failure", [False, True])
def test_cancel_pending_drops_published_outcomes_and_accepts_new_work(
    failure: bool,
) -> None:
    """Cancellation must revoke already-published success and failure callbacks."""

    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="preparation-cancellation",
        max_workers=1,
        queue_capacity=8,
        thread_name_prefix="preparation-cancellation",
        dispatcher=dispatcher,
    )
    executor = GenerationPreparationExecutor(lane)
    completed: list[GenerationPreparationResult] = []
    failed: list[BaseException] = []
    old_result = GenerationPreparationResult(snapshots=(), scene_run_id="cancelled")
    new_result = GenerationPreparationResult(snapshots=(), scene_run_id="new")

    def prepare_old() -> GenerationPreparationResult:
        """Settle in the worker while holding publication at the owner-thread boundary."""

        if failure:
            raise RuntimeError("cancelled preparation failed")
        return old_result

    try:
        executor.submit(
            prepare_snapshots=prepare_old,
            on_completed=completed.append,
            on_failed=failed.append,
        )
        dispatcher.wait_for_callbacks(2, timeout_seconds=5)
        executor.cancel_pending()
        executor.cancel_pending()
        executor.submit(
            prepare_snapshots=lambda: new_result,
            on_completed=completed.append,
            on_failed=failed.append,
        )
        dispatcher.wait_for_callbacks(4, timeout_seconds=5)
        dispatcher.run_all()
        assert completed == [new_result]
        assert failed == []
    finally:
        executor.close()
        lane.shutdown(wait=True)
        dispatcher.run_all()


def test_cancel_pending_releases_callbacks_without_closing_executor() -> None:
    """Pending UI owners should be released immediately when queue admission is revoked."""

    submitter = QueuedTaskSubmitter()
    executor = GenerationPreparationExecutor(submitter)

    class Observer:
        """Provide an independently collectable presentation callback owner."""

        def completed(self, result: GenerationPreparationResult) -> None:
            """Accept a preparation result without retaining it."""

    observer = Observer()
    observer_ref = weakref.ref(observer)
    executor.submit(
        prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
        on_completed=observer.completed,
        on_failed=lambda _error: None,
    )
    del observer
    assert observer_ref() is not None
    executor.cancel_pending()
    assert observer_ref() is None
    assert submitter.cancellations[0].is_cancelled
    executor.close()


def test_cancel_pending_running_worker_finishes_without_delivering_result() -> None:
    """Revoke a running noncooperative preparation without blocking or leaking its lane."""

    started = Event()
    release = Event()
    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="running-preparation",
        max_workers=1,
        queue_capacity=8,
        thread_name_prefix="running-preparation",
        dispatcher=dispatcher,
    )
    executor = GenerationPreparationExecutor(lane)
    completed: list[GenerationPreparationResult] = []
    failed: list[BaseException] = []

    def prepare() -> GenerationPreparationResult:
        """Hold real running work until the owner has revoked its admission."""

        started.set()
        assert release.wait(timeout=5), "Owner never released the preparation barrier"
        return GenerationPreparationResult(snapshots=(), scene_run_id="cancelled")

    try:
        executor.submit(
            prepare_snapshots=prepare,
            on_completed=completed.append,
            on_failed=failed.append,
        )
        assert started.wait(timeout=5), "Preparation worker did not start"
        executor.cancel_pending()
        assert lane.pending_count == 1
        release.set()
        dispatcher.wait_for_callbacks(2, timeout_seconds=5)
        dispatcher.run_all()
        assert completed == []
        assert failed == []
    finally:
        release.set()
        executor.close()
        lane.shutdown(wait=True)
        dispatcher.run_all()
    assert lane.pending_count == 0
