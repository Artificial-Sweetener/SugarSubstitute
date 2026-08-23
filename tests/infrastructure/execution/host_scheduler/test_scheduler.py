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

"""Abuse the authoritative host physical execution scheduler."""

from __future__ import annotations

import threading
from concurrent.futures import Future
from functools import partial
from random import Random
from threading import Event, Lock
from uuid import UUID

from substitute.infrastructure.execution import (
    HostExecutionLeaseRelease,
    HostExecutionPolicy,
    HostExecutionRequirements,
    HostExecutionResource,
    HostExecutionScheduler,
    HostExecutionSnapshot,
)
from tests.infrastructure.execution.host_scheduler.support import (
    ManualLifecycleJob,
    block_until_released,
    build_scheduler,
    capture_affinity,
    native_requirements,
    record_storm_job,
    wait_for_release,
    wait_for_snapshot,
)


def test_affinity_reuse_stays_on_bounded_stable_host_threads() -> None:
    """Keep every key stable without creating one worker per hostile key."""

    scheduler = build_scheduler(affinity_shards=2)
    futures: list[tuple[str, Future[tuple[str, str]]]] = []
    try:
        for index in range(256):
            affinity_key = f"native-session-{index % 17}"
            future = scheduler.submit_detached(
                partial(capture_affinity, affinity_key),
                operation=f"affinity_reuse_{index}",
                requirements=HostExecutionRequirements(
                    resource=HostExecutionResource.THREAD_AFFINE_NATIVE,
                    urgency_rank=index % 50,
                    affinity_key=affinity_key,
                    resource_id=affinity_key,
                    maximum_concurrency=1,
                ),
            )
            futures.append((affinity_key, future))

        observed: dict[str, set[str]] = {}
        for affinity_key, future in futures:
            key, thread_name = future.result(timeout=2.0)
            assert key == affinity_key
            observed.setdefault(key, set()).add(thread_name)

        assert all(len(thread_names) == 1 for thread_names in observed.values())
        physical_threads = set().union(*observed.values())
        assert 1 <= len(physical_threads) <= 2
        assert all(
            thread_name.startswith("test-host-affinity-")
            for thread_name in physical_threads
        )
        assert scheduler.snapshot().worker_threads == len(physical_threads)
    finally:
        scheduler.shutdown(wait=True)


def test_detached_future_callbacks_observe_fully_settled_scheduler_state() -> None:
    """Publish detached completion only after releasing physical accounting."""

    scheduler = build_scheduler(native_workers=1)
    observed_snapshots: list[HostExecutionSnapshot] = []
    callback_finished = Event()
    try:
        future = scheduler.submit_detached(
            lambda: 42,
            operation="settlement_snapshot",
            requirements=native_requirements(),
        )

        def capture_snapshot(_future: Future[int]) -> None:
            """Record scheduler state visible at lifecycle completion."""

            observed_snapshots.append(scheduler.snapshot())
            callback_finished.set()

        future.add_done_callback(capture_snapshot)

        assert future.result(timeout=1.0) == 42
        assert callback_finished.wait(timeout=1.0)
        assert observed_snapshots == [
            HostExecutionSnapshot(
                accepted=0,
                pending=0,
                running=0,
                retained_bytes=0,
                rejected=0,
                completed=1,
                cancelled_before_start=0,
                worker_threads=1,
            )
        ]
    finally:
        scheduler.shutdown(wait=True)


def test_settlement_held_exclusive_waits_for_owner_adoption() -> None:
    """Block conflicting work until the lifecycle owner reports settlement."""

    scheduler = build_scheduler(affinity_shards=1)
    first_started = Event()
    second_started = Event()
    first = ManualLifecycleJob(
        requirements=native_requirements(
            exclusive_key="native-session",
            lease_release=HostExecutionLeaseRelease.SETTLEMENT_FINISHED,
        ),
        started=first_started,
    )
    second = ManualLifecycleJob(
        requirements=native_requirements(exclusive_key="native-session"),
        started=second_started,
    )
    try:
        scheduler.submit(first.job)
        scheduler.submit(second.job)

        assert first_started.wait(timeout=1.0)
        assert second_started.is_set() is False
        assert scheduler.snapshot().pending == 1

        first.settle()

        assert second_started.wait(timeout=1.0)
        second.settle()
        assert wait_for_snapshot(scheduler, lambda accepted, running: accepted == 0)
    finally:
        first.settle()
        second.settle()
        scheduler.shutdown(wait=True)


def test_shutdown_cancels_each_pending_job_once_and_leaks_no_workers() -> None:
    """Settle a hostile pending burst exactly once during shutdown."""

    scheduler = build_scheduler(native_workers=1)
    blocker_started = Event()
    blocker_release = Event()
    cancelled: list[UUID] = []
    cancellation_lock = Lock()
    blocker = scheduler.submit_detached(
        lambda: block_until_released(blocker_started, blocker_release),
        operation="shutdown_blocker",
        requirements=native_requirements(),
    )
    jobs = [
        ManualLifecycleJob(
            requirements=native_requirements(),
            cancelled=cancelled,
            cancellation_lock=cancellation_lock,
        )
        for _index in range(64)
    ]
    assert blocker_started.wait(timeout=1.0)
    for job in jobs:
        scheduler.submit(job.job)

    scheduler.shutdown(wait=False)

    for job in jobs:
        job.settle()
    blocker_release.set()
    blocker.result(timeout=1.0)
    scheduler.shutdown(wait=True)

    with cancellation_lock:
        assert sorted(cancelled) == sorted(job.job.task_id for job in jobs)
    assert all(job.cancel_count == 1 for job in jobs)
    snapshot = scheduler.snapshot()
    assert snapshot.pending == 0
    assert snapshot.running == 0
    assert snapshot.accepted == 0
    assert not any(
        thread.name.startswith("test-host-") and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_diagnostics_converge_on_observable_physical_state() -> None:
    """Publish coalesced host state without inventing a second owner."""

    scheduler = build_scheduler(native_workers=1)
    observed = Event()
    snapshots = []

    def observe_snapshot(snapshot: HostExecutionSnapshot) -> None:
        """Record diagnostics and signal the expected terminal state."""

        snapshots.append(snapshot)
        if snapshot.completed == 1 and snapshot.accepted == 0:
            observed.set()

    subscription = scheduler.subscribe_diagnostics(observe_snapshot)
    try:
        future = scheduler.submit_detached(
            lambda: "done",
            operation="diagnostics",
            requirements=native_requirements(),
        )
        assert future.result(timeout=1.0) == "done"
        assert observed.wait(timeout=1.0)
        assert snapshots[-1].completed == 1
        assert snapshots[-1].accepted == 0
        assert snapshots[-1].pending == 0
        assert snapshots[-1].running == 0
    finally:
        subscription.close()
        scheduler.shutdown(wait=True)


def test_urgency_aging_prevents_background_starvation() -> None:
    """Let sufficiently old background work overtake newer interaction work."""

    now = [0.0]
    scheduler = HostExecutionScheduler(
        HostExecutionPolicy(
            resource_workers={
                HostExecutionResource.BLOCKING_IO: 1,
                HostExecutionResource.PYTHON_CPU: 1,
                HostExecutionResource.NATIVE_CPU: 1,
                HostExecutionResource.DEVICE: 1,
            },
            affinity_shards=1,
            aging_interval_seconds=0.25,
            thread_name_prefix="test-host",
        ),
        clock=lambda: now[0],
    )
    blocker_started = Event()
    blocker_release = Event()
    order: list[str] = []
    try:
        blocker = scheduler.submit_detached(
            lambda: block_until_released(blocker_started, blocker_release),
            operation="aging_blocker",
            requirements=native_requirements(),
        )
        assert blocker_started.wait(timeout=1.0)
        background = scheduler.submit_detached(
            lambda: order.append("background"),
            operation="aged_background",
            requirements=HostExecutionRequirements(
                resource=HostExecutionResource.NATIVE_CPU,
                urgency_rank=20,
            ),
        )
        now[0] = 10.0
        interactive = scheduler.submit_detached(
            lambda: order.append("interactive"),
            operation="new_interactive",
            requirements=HostExecutionRequirements(
                resource=HostExecutionResource.NATIVE_CPU,
                urgency_rank=0,
            ),
        )

        blocker_release.set()

        blocker.result(timeout=1.0)
        background.result(timeout=1.0)
        interactive.result(timeout=1.0)
        assert order == ["background", "interactive"]
    finally:
        blocker_release.set()
        scheduler.shutdown(wait=True)


def test_ordinary_workers_scale_lazily_with_accepted_demand() -> None:
    """Avoid paying full resource-thread startup cost for the first job."""

    scheduler = build_scheduler(native_workers=4)
    first_started = Event()
    release = Event()
    futures: list[Future[None]] = []
    try:
        futures.append(
            scheduler.submit_detached(
                lambda: block_until_released(first_started, release),
                operation="lazy_worker_first",
                requirements=native_requirements(),
            )
        )
        assert first_started.wait(timeout=1.0)
        assert scheduler.snapshot().worker_threads == 1
        for index in range(3):
            futures.append(
                scheduler.submit_detached(
                    partial(wait_for_release, release),
                    operation=f"lazy_worker_burst_{index}",
                    requirements=native_requirements(),
                )
            )
        assert scheduler.snapshot().worker_threads == 4
    finally:
        release.set()
        for future in futures:
            future.result(timeout=1.0)
        scheduler.shutdown(wait=True)


def test_seeded_mixed_resource_storm_settles_exactly_on_bounded_workers() -> None:
    """Settle thousands of erratic jobs without loss, duplication, or leaks."""

    scheduler = build_scheduler(native_workers=4, affinity_shards=2)
    randomizer = Random(0xC07ECA)
    observed: dict[int, str] = {}
    observed_lock = Lock()
    resources = tuple(HostExecutionResource)
    try:
        for batch_start in range(0, 2048, 128):
            futures: list[Future[int]] = []
            expected = set(range(batch_start, batch_start + 128))
            for sequence in expected:
                resource = randomizer.choice(resources)
                affinity_key = (
                    f"storm-affinity-{randomizer.randrange(31)}"
                    if resource is HostExecutionResource.THREAD_AFFINE_NATIVE
                    else None
                )
                resource_id = f"storm-resource-{randomizer.randrange(7)}"
                requirements = HostExecutionRequirements(
                    resource=resource,
                    urgency_rank=randomizer.randrange(50),
                    resource_id=resource_id,
                    exclusive_key=(
                        f"storm-exclusive-{randomizer.randrange(11)}"
                        if randomizer.randrange(4) == 0
                        else None
                    ),
                    affinity_key=affinity_key,
                    maximum_concurrency=randomizer.choice((None, 1, 2, 3)),
                    estimated_retained_bytes=randomizer.randrange(0, 8193),
                )
                futures.append(
                    scheduler.submit_detached(
                        partial(
                            record_storm_job,
                            sequence,
                            observed,
                            observed_lock,
                        ),
                        operation=f"mixed_storm_{sequence}",
                        requirements=requirements,
                    )
                )

            assert {future.result(timeout=5.0) for future in futures} == expected

        assert set(observed) == set(range(2048))
        snapshot = scheduler.snapshot()
        assert snapshot.accepted == 0
        assert snapshot.pending == 0
        assert snapshot.running == 0
        assert snapshot.completed == 2048
        assert snapshot.worker_threads <= 10
    finally:
        scheduler.shutdown(wait=True)
    assert not any(
        thread.name.startswith("test-host-") and thread.is_alive()
        for thread in threading.enumerate()
    )
