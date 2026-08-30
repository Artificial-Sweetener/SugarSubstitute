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

"""Cover generation-queue output-run projection and commitment."""

from __future__ import annotations


from datetime import datetime, timezone


from substitute.application.generation import (
    PreparedGenerationRequest,
)
from substitute.application.generation.job_queue_service import (
    GenerationQueueStateChange,
)
from substitute.domain.generation import (
    GenerationQueueJob,
)

from ..queue_service_test_support import (
    _AllocatorRecorder,
    _BucketResolver,
    _CallbackRecorder,
    _FakeDispatcher,
    _ProjectionKeyProvider,
    _bucket,
    _callbacks,
    _progress_update,
    _service,
    _service_with_allocator,
    _service_with_allocator_ids,
    _snapshot,
)


def test_dispatch_commits_output_run_number_before_start() -> None:
    """Dispatch should commit the output number before calling the dispatcher."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7])
    service = _service_with_allocator(dispatcher, allocator)

    job = service.enqueue_snapshot(_snapshot(), _callbacks())

    assert job.output_run_number == 7
    assert service.jobs()[0].output_run_number == 7
    assert service.jobs()[0].projected_output_run_number is None
    assert dispatcher.requests[0].output_run_number == 7
    assert dispatcher.requests[0].output_job_started_at == datetime(
        2026, 4, 22, tzinfo=timezone.utc
    )
    assert allocator.calls == [{"bucket": _bucket("2026-04-22")}]


def test_pending_jobs_project_distinct_output_numbers_before_outputs_save() -> None:
    """Pending jobs should project distinct future output numbers."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([7, 8, 9])
    service = _service_with_allocator(dispatcher, allocator)

    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())
    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())
    service.enqueue_snapshot(_snapshot("Workflow"), _callbacks())

    assert [job.output_run_number for job in service.jobs()] == [7, None, None]
    assert [job.projected_output_run_number for job in service.jobs()] == [
        None,
        8,
        9,
    ]
    assert [request.output_run_number for request in dispatcher.requests] == [7]


def test_batch_enqueue_matches_one_at_a_time_output_projection() -> None:
    """Batch enqueue should preserve current projected output-number semantics."""

    snapshots = (
        _snapshot("Workflow"),
        _snapshot("Workflow"),
        _snapshot("Workflow"),
    )
    one_at_a_time_dispatcher = _FakeDispatcher()
    one_at_a_time_service = _service_with_allocator_ids(
        one_at_a_time_dispatcher,
        _AllocatorRecorder([7]),
        ["job-1", "job-2", "job-3"],
    )
    batch_dispatcher = _FakeDispatcher()
    batch_service = _service_with_allocator_ids(
        batch_dispatcher,
        _AllocatorRecorder([7]),
        ["job-1", "job-2", "job-3"],
    )

    for snapshot in snapshots:
        one_at_a_time_service.enqueue_snapshot(snapshot, _callbacks())
    batch_service.enqueue_snapshots(snapshots, _callbacks())

    def output_projection_signature(
        jobs: tuple[GenerationQueueJob, ...],
    ) -> list[tuple[str, str, int | None, int | None, str | None]]:
        """Return fields that define visible output numbering semantics."""

        return [
            (
                job.job_id,
                job.status,
                job.output_run_number,
                job.projected_output_run_number,
                job.projected_output_bucket_label,
            )
            for job in jobs
        ]

    assert output_projection_signature(batch_service.jobs()) == (
        output_projection_signature(one_at_a_time_service.jobs())
    )
    assert [request.output_run_number for request in batch_dispatcher.requests] == [
        request.output_run_number for request in one_at_a_time_dispatcher.requests
    ]


def test_pending_jobs_in_different_buckets_can_project_same_output_number() -> None:
    """Run numbers should be scoped to the resolved output bucket."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=_BucketResolver(
            {
                "Today": _bucket("2026-05-12"),
                "Yesterday": _bucket("2026-05-11"),
            }
        ),
    )

    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())

    jobs = service.jobs()
    assert jobs[0].output_run_number == 1
    assert jobs[0].output_bucket_label == "2026-05-12"
    assert jobs[1].projected_output_run_number == 1
    assert jobs[1].projected_output_bucket_label == "2026-05-11"


def test_jobs_projection_is_cached_until_queue_or_output_dependency_changes() -> None:
    """Repeated queue reads should reuse pending projection until inputs change."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    allocator.calls.clear()
    bucket_resolver.calls.clear()

    first_projection = service.jobs()
    second_projection = service.jobs()

    assert first_projection == second_projection
    assert [job.projected_output_bucket_label for job in first_projection] == [
        None,
        "2026-05-11",
    ]
    assert len(allocator.calls) == 1
    assert [call["workflow_name"] for call in bucket_resolver.calls] == ["Yesterday"]

    projection_key_provider.key = "day-2"
    service.jobs()

    assert len(allocator.calls) == 2
    assert [call["workflow_name"] for call in bucket_resolver.calls] == [
        "Yesterday",
        "Yesterday",
    ]


def test_move_pending_job_invalidates_cached_projection_order() -> None:
    """Moving a pending job should make the next cached queue view reflect order."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(dispatcher, allocator)
    service.enqueue_snapshot(_snapshot("Running"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "Running",
        "Second",
        "Third",
    ]

    service.move_pending_job("job-3", 0)

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "Running",
        "Third",
        "Second",
    ]


def test_progress_update_publishes_progress_event_without_projection_rebuild() -> None:
    """Progress should patch queue state without recomputing pending projection."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.jobs()
    allocator.calls.clear()
    bucket_resolver.calls.clear()
    events: list[GenerationQueueStateChange] = []
    service.add_observer(events.append)
    events.clear()

    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="Today",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )

    assert len(events) == 1
    assert events[0].change_kind == "progress"
    assert events[0].changed_job_id == "job-1"
    assert [job.progress_percent for job in events[0].jobs] == [42.0, None]
    assert allocator.calls == []
    assert bucket_resolver.calls == []


def test_rejected_progress_does_not_recompute_projection() -> None:
    """Rejected stale progress should not invalidate cached queue projection."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    bucket_resolver = _BucketResolver(
        {
            "Today": _bucket("2026-05-12"),
            "Yesterday": _bucket("2026-05-11"),
        }
    )
    projection_key_provider = _ProjectionKeyProvider("day-1")
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=bucket_resolver,
        projection_key_provider=projection_key_provider,
    )
    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.jobs()
    allocator.calls.clear()
    bucket_resolver.calls.clear()
    service.cancel_all_jobs()

    dispatcher.callbacks[0].on_progress(
        _progress_update(
            workflow_name="Today",
            workflow_percent=42.0,
            sampler_percent=None,
        )
    )
    service.jobs()

    assert allocator.calls == []
    assert bucket_resolver.calls == []


def test_duplicate_visible_output_numbers_still_cancel_by_job_id() -> None:
    """Queue actions should use hidden job ids when visible run labels match."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder([1])
    service = _service_with_allocator(
        dispatcher,
        allocator,
        bucket_resolver=_BucketResolver(
            {
                "Today": _bucket("2026-05-12"),
                "Yesterday": _bucket("2026-05-11"),
            }
        ),
    )

    service.enqueue_snapshot(_snapshot("Today"), _callbacks())
    pending = service.enqueue_snapshot(_snapshot("Yesterday"), _callbacks())
    service.cancel_job(pending.job_id)

    jobs = service.jobs()
    assert [(job.job_id, job.status) for job in jobs] == [
        ("job-1", "running"),
        ("job-2", "cancelled"),
    ]
    assert jobs[0].output_run_number == 1
    assert jobs[1].output_run_number is None
    assert dispatcher.requests == [
        PreparedGenerationRequest(
            workflow_id="wf-today",
            workflow_name="Today",
            sugar_script_text='use "cube" as Today',
            output_run_number=1,
            output_job_started_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )
    ]


def test_new_pending_jobs_append_to_dispatch_order() -> None:
    """New queued work should enter the back of pending dispatch order."""

    dispatcher = _FakeDispatcher()
    service = _service(dispatcher)

    service.enqueue_snapshot(_snapshot("First"), _callbacks())
    service.enqueue_snapshot(_snapshot("Second"), _callbacks())
    service.enqueue_snapshot(_snapshot("Third"), _callbacks())

    assert [job.snapshot.workflow_name for job in service.jobs()] == [
        "First",
        "Second",
        "Third",
    ]
    assert [job.status for job in service.jobs()] == ["running", "pending", "pending"]


def test_dispatch_fails_closed_when_output_run_number_allocation_fails() -> None:
    """Allocation failure should report failure and avoid dispatching the job."""

    dispatcher = _FakeDispatcher()
    allocator = _AllocatorRecorder(fail=True)
    service = _service_with_allocator(dispatcher, allocator)
    recorder = _CallbackRecorder()

    job = service.enqueue_snapshot(_snapshot(), _callbacks(recorder))

    assert job.status == "failed"
    assert "Failed to allocate output run number" in (job.failure_message or "")
    assert [queued_job.status for queued_job in service.jobs()] == ["failed"]
    assert dispatcher.requests == []
    assert len(recorder.failures) == 1
    assert recorder.failures[0].stage == "queue"
