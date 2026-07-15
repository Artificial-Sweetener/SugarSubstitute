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

"""Tests for off-thread canonical model catalog snapshot refresh coordination."""

from __future__ import annotations

from typing import TypeVar, cast

from PySide6.QtWidgets import QApplication

from substitute.application.execution import CancellationToken, TaskHandle, TaskRequest
from tests.execution_testing import ManualTaskHandle
from substitute.application.model_metadata import ModelCatalogSnapshot
from substitute.presentation.shell.model_catalog_snapshot_refresh_coordinator import (
    ModelCatalogSnapshotRefreshCoordinator,
)

TResult = TypeVar("TResult")


class _Catalog:
    """Return deterministic canonical snapshots for requested kinds."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.calls: list[str] = []

    def refresh_snapshot(self, kind: str) -> ModelCatalogSnapshot:
        """Return a snapshot whose generation matches the call count."""

        self.calls.append(kind)
        return ModelCatalogSnapshot(kind=kind, items=(), generation=len(self.calls))


class _Executor:
    """Store submitted work without running it automatically."""

    def __init__(self) -> None:
        """Initialize executor state."""

        self.submitted: list[TaskRequest[ModelCatalogSnapshot]] = []
        self.cancellations: list[CancellationToken] = []

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Record one submitted worker request."""

        self.cancellations.append(cancellation)
        self.submitted.append(cast(TaskRequest[ModelCatalogSnapshot], request))
        return ManualTaskHandle(request)


def test_model_catalog_snapshot_refresh_coordinator_coalesces_latest_request() -> None:
    """Queued metadata events should share one worker and keep the newest follow-up."""

    _ensure_qapp()
    catalog = _Catalog()
    executor = _Executor()
    completed: list[tuple[int, object | None]] = []
    coordinator = ModelCatalogSnapshotRefreshCoordinator(
        model_catalog=catalog,
        completed=lambda snapshot, context: completed.append(
            (snapshot.generation, context)
        ),
        submitter=executor,
    )
    first_context = object()
    second_context = object()

    coordinator.request_refresh("loras", first_context)
    coordinator.request_refresh("loras", second_context)
    first_snapshot = executor.submitted[0].work(_NeverCancelled())
    coordinator._deliver_completed_refresh(1, first_snapshot, None, first_context)
    second_snapshot = executor.submitted[1].work(_NeverCancelled())
    coordinator._deliver_completed_refresh(2, second_snapshot, None, second_context)

    assert catalog.calls == ["loras", "loras"]
    assert completed == [(1, first_context), (2, second_context)]
    assert len(executor.submitted) == 2


def test_model_catalog_snapshot_refresh_coordinator_ignores_stale_completion() -> None:
    """Out-of-date worker completions should not fan out snapshots."""

    _ensure_qapp()
    completed: list[int] = []
    coordinator = ModelCatalogSnapshotRefreshCoordinator(
        model_catalog=_Catalog(),
        completed=lambda snapshot, _context: completed.append(snapshot.generation),
        submitter=_Executor(),
    )
    coordinator.request_refresh("loras")
    coordinator.request_refresh("loras")

    coordinator._deliver_completed_refresh(
        0,
        ModelCatalogSnapshot(kind="loras", items=(), generation=99),
        None,
        None,
    )

    assert completed == []


def test_model_catalog_snapshot_refresh_coordinator_shutdown_cancels_active_work() -> (
    None
):
    """Shutdown should cancel active snapshot refresh work through TaskScope."""

    _ensure_qapp()
    executor = _Executor()
    coordinator = ModelCatalogSnapshotRefreshCoordinator(
        model_catalog=_Catalog(),
        completed=lambda _snapshot, _context: None,
        submitter=executor,
    )

    coordinator.request_refresh("loras")
    coordinator.shutdown()

    assert executor.cancellations[0].is_cancelled is True
    assert executor.cancellations[0].reason == "model_catalog_snapshot_refresh_shutdown"


def _ensure_qapp() -> QApplication:
    """Return a Qt application for QObject tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


class _NeverCancelled:
    """Provide a neutral cancellation token for worker request execution."""

    generation = 0
    is_cancelled = False
    reason: str | None = None
