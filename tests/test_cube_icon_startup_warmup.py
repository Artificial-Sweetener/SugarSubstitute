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

"""Tests for startup cube icon cache warmup coordination."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from substitute.app.bootstrap.cube_icon_startup_warmup import (
    StartupCubeIconWarmupHandle,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot


@dataclass
class _ManualScheduler:
    """Collect scheduled callbacks and run them deterministically."""

    callbacks: list[Callable[[], None]] = field(default_factory=list)
    scheduled_count: int = 0

    def __call__(self, _delay_ms: int, callback: Callable[[], None]) -> None:
        """Record one scheduled callback."""

        self.scheduled_count += 1
        self.callbacks.append(callback)

    def drain_one(self) -> None:
        """Run one scheduled callback."""

        callback = self.callbacks.pop(0)
        callback()

    def drain_all(self) -> None:
        """Run scheduled callbacks until the queue is empty."""

        while self.callbacks:
            self.drain_one()


class _CloseRecorder:
    """Record execution submitter close requests."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_called = False

    def close(self) -> None:
        """Record one close request."""

        self.close_called = True


@dataclass
class _FakeCubeLoadService:
    """Provide deterministic catalog refresh behavior."""

    snapshot: CubeCatalogSnapshot | None = None
    cached_snapshot: CubeCatalogSnapshot | None = None
    error: Exception | None = None
    snapshot_calls: int = 0
    refresh_calls: int = 0

    def picker_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return cached catalog state without forcing a refresh."""

        self.snapshot_calls += 1
        if self.cached_snapshot is None:
            return CubeCatalogSnapshot(entries=[], state="missing")
        return self.cached_snapshot

    def refresh_picker_catalog(self) -> CubeCatalogSnapshot:
        """Return the configured snapshot or raise the configured failure."""

        self.refresh_calls += 1
        if self.error is not None:
            raise self.error
        if self.snapshot is None:
            return CubeCatalogSnapshot(entries=[], state="missing")
        return self.snapshot


@dataclass
class _FakeIconFactory:
    """Record startup icon warmup requests."""

    failing_cube_ids: set[str] = field(default_factory=set)
    calls: list[tuple[str, str, object | None, str, str]] = field(default_factory=list)

    def warm_icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
    ) -> bool:
        """Record one warmup request and optionally raise."""

        self.calls.append(
            (cube_id, display_name, icon, catalog_revision, cube_content_hash)
        )
        if cube_id in self.failing_cube_ids:
            raise RuntimeError(f"failed {cube_id}")
        return True


@dataclass
class _SequenceClock:
    """Return a deterministic sequence of perf-counter values."""

    values: list[float]

    def __post_init__(self) -> None:
        """Store the last value for exhausted reads."""

        self._last_value = self.values[-1] if self.values else 0.0

    def __call__(self) -> float:
        """Return the next configured clock value."""

        if not self.values:
            return self._last_value
        self._last_value = self.values.pop(0)
        return self._last_value


def _records(count: int) -> list[CubeCatalogRecord]:
    """Return deterministic catalog records for warmup tests."""

    return [
        CubeCatalogRecord(
            cube_id=f"cube-{index}",
            version="1.0.0",
            display_name=f"Cube {index}",
        )
        for index in range(count)
    ]


def test_start_refreshes_catalog_and_warms_icon_records() -> None:
    """Startup warmup should refresh catalog then warm icons on scheduled turns."""

    scheduler = _ManualScheduler()
    records = _records(3)
    service = _FakeCubeLoadService(CubeCatalogSnapshot(entries=records, state="fresh"))
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert service.refresh_calls == 1
    assert factory.calls == [
        ("cube-0", "Cube 0", None, "", ""),
        ("cube-1", "Cube 1", None, "", ""),
        ("cube-2", "Cube 2", None, "", ""),
    ]


def test_start_uses_fresh_cached_catalog_without_refreshing() -> None:
    """Startup warmup should avoid backend refresh when picker cache is fresh."""

    scheduler = _ManualScheduler()
    records = _records(2)
    service = _FakeCubeLoadService(
        cached_snapshot=CubeCatalogSnapshot(entries=records, state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert service.snapshot_calls == 1
    assert service.refresh_calls == 0
    assert [call[0] for call in factory.calls] == ["cube-0", "cube-1"]


def test_start_refreshes_when_cached_catalog_is_stale() -> None:
    """Startup warmup should refresh when TTL policy marks cache stale."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        cached_snapshot=CubeCatalogSnapshot(entries=_records(1), state="stale"),
        snapshot=CubeCatalogSnapshot(entries=_records(2), state="fresh"),
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert service.snapshot_calls == 1
    assert service.refresh_calls == 1
    assert [call[0] for call in factory.calls] == ["cube-0", "cube-1"]


def test_warmup_batches_icon_work_across_scheduled_callbacks() -> None:
    """Warmup should split icon work across scheduler turns."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(5), state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        batch_size=2,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    assert len(scheduler.callbacks) == 1
    scheduler.drain_all()

    assert len(factory.calls) == 5
    assert service.refresh_calls == 1


def test_default_warmup_processes_one_icon_per_gui_chunk() -> None:
    """Default icon warmup should yield after each GUI icon entry."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(3), state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    assert scheduler.scheduled_count == 1

    scheduler.drain_one()
    assert factory.calls == []
    assert scheduler.scheduled_count == 2

    scheduler.drain_one()
    assert [call[0] for call in factory.calls] == ["cube-0"]
    assert scheduler.scheduled_count == 3

    scheduler.drain_one()
    assert [call[0] for call in factory.calls] == ["cube-0", "cube-1"]
    assert scheduler.scheduled_count == 4

    scheduler.drain_one()
    assert [call[0] for call in factory.calls] == ["cube-0", "cube-1", "cube-2"]
    assert scheduler.callbacks == []


def test_warmup_chunk_budget_yields_before_batch_limit() -> None:
    """Chunk budget should split oversized batches across GUI turns."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(3), state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        batch_size=3,
        gui_chunk_budget_seconds=0.008,
        submitter=ImmediateTaskSubmitter(),
        clock=_SequenceClock([0.0, 0.0, 0.009, 0.009]),
    )

    handle.start()
    scheduler.drain_one()
    scheduler.drain_one()

    assert [call[0] for call in factory.calls] == ["cube-0"]
    assert scheduler.callbacks


def test_warmup_budget_stops_before_all_records() -> None:
    """Startup budget should leave remaining records for normal on-demand use."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(3), state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        batch_size=3,
        startup_budget_seconds=0.5,
        submitter=ImmediateTaskSubmitter(),
        clock=_SequenceClock([0.0, 0.6, 0.6]),
    )

    handle.start()
    scheduler.drain_all()

    assert factory.calls == [("cube-0", "Cube 0", None, "", "")]


def test_refresh_failure_schedules_no_icon_work() -> None:
    """Catalog refresh failures should stop warmup without scheduling icons."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(error=RuntimeError("catalog unavailable"))
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert service.refresh_calls == 1
    assert scheduler.callbacks == []
    assert factory.calls == []


def test_icon_failure_logs_and_continues_with_remaining_records() -> None:
    """One icon failure should not stop the rest of startup warmup."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(3), state="fresh")
    )
    factory = _FakeIconFactory(failing_cube_ids={"cube-1"})
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert [call[0] for call in factory.calls] == ["cube-0", "cube-1", "cube-2"]


def test_shutdown_prevents_scheduled_icon_work() -> None:
    """Shutdown should prevent already-scheduled callbacks from warming icons."""

    scheduler = _ManualScheduler()
    close_recorder = _CloseRecorder()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(entries=_records(2), state="fresh")
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
        close_submitter=close_recorder.close,
    )

    handle.start()
    handle.shutdown()
    scheduler.drain_all()

    assert close_recorder.close_called is True
    assert factory.calls == []


def test_warmup_passes_catalog_identity_to_icon_factory() -> None:
    """Startup warmup should hydrate the same durable key used by the cart."""

    scheduler = _ManualScheduler()
    service = _FakeCubeLoadService(
        CubeCatalogSnapshot(
            entries=[
                CubeCatalogRecord(
                    cube_id="cube-a",
                    version="1.0.0",
                    display_name="Cube A",
                    content_hash="hash-a",
                    catalog_revision="revision-a",
                )
            ],
            state="fresh",
            catalog_revision="revision-a",
        )
    )
    factory = _FakeIconFactory()
    handle = StartupCubeIconWarmupHandle(
        cube_load_service=service,
        cube_icon_factory=factory,
        scheduler=scheduler,
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()
    scheduler.drain_all()

    assert factory.calls == [
        ("cube-a", "Cube A", None, "revision-a", "hash-a"),
    ]
