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

"""Warm Cube Library picker icons during startup without blocking shell reveal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from PySide6.QtCore import QObject

from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot
from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.app.bootstrap.startup_policy import CUBE_ICON_GUI_WARMUP_BUDGET_SECONDS
from substitute.app.bootstrap.startup_trace import (
    trace_mark,
    trace_span,
)
from substitute.presentation.qt.execution import QtUiScheduler
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.cube_icon_startup_warmup")
Scheduler = Callable[[int, Callable[[], None]], None]
Clock = Callable[[], float]


class _QtUiSchedulerAdapter:
    """Adapt the shared Qt UI scheduler to the warmup's simple schedule port."""

    def __init__(self, receiver: QObject) -> None:
        """Create an owner-thread scheduler tied to the receiver lifetime."""

        self._scheduler = QtUiScheduler(receiver)

    def __call__(self, delay_ms: int, callback: Callable[[], None]) -> None:
        """Schedule one warmup callback on the receiver's owner thread."""

        clamped_delay = max(0, delay_ms)
        trace_mark(
            "cube_icon_warmup.gui_scheduler",
            delay_ms=clamped_delay,
        )
        self._scheduler.schedule(
            clamped_delay,
            callback,
            reason="cube_icon_warmup.gui_chunk",
        )


@dataclass
class StartupCubeIconWarmupHandle:
    """Warm Cube Library picker catalog and icon caches during startup."""

    cube_load_service: Any
    cube_icon_factory: Any
    submitter: TaskSubmitter
    close_submitter: object | None = None
    scheduler: Scheduler | None = None
    ui_receiver: QObject | None = None
    batch_size: int = 1
    startup_budget_seconds: float = CUBE_ICON_GUI_WARMUP_BUDGET_SECONDS
    gui_chunk_budget_seconds: float = 0.008
    clock: Clock = perf_counter

    def __post_init__(self) -> None:
        """Initialize scheduler and one-shot warmup state."""

        self._scheduler = self._build_scheduler()
        self._scope = TaskScope(
            submitter=self.submitter,
            scope_id=f"cube_icon_startup_warmup_{id(self):x}",
        )
        self._handle: TaskHandle[None] | None = None
        self._shutdown_requested = False
        self._entries: list[CubeCatalogRecord] = []
        self._next_index = 0
        self._warmed_count = 0
        self._skipped_count = 0
        self._gui_started_at = 0.0

    def start(self) -> None:
        """Start catalog refresh and icon warmup once without blocking startup."""

        trace_mark(
            "cube_icon_warmup.start_requested",
            already_started=self._handle is not None,
            shutdown_requested=self._shutdown_requested,
        )
        if self._handle is not None or self._shutdown_requested:
            return
        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=1,
                domain="cube_icon_startup_warmup",
            ),
            context=ExecutionContext(
                operation="cube_icon_startup_warmup",
                reason="startup_warmup",
                lane="startup",
            ),
            work=self._refresh_catalog_task,
        )
        self._handle = self._scope.submit(request)

    def shutdown(self) -> None:
        """Release executor resources without blocking application shutdown."""

        trace_mark("cube_icon_warmup.shutdown_requested")
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._scope.close(reason="cube_icon_warmup_shutdown")
        close = getattr(self.close_submitter, "__call__", None)
        if callable(close):
            close()

    def _build_scheduler(self) -> Scheduler:
        """Return the configured scheduler or create the shared Qt scheduler adapter."""

        if self.scheduler is not None:
            return self.scheduler
        if self.ui_receiver is None:
            raise ValueError("ui_receiver is required when scheduler is not supplied.")
        return _QtUiSchedulerAdapter(self.ui_receiver)

    def _refresh_catalog_task(self, cancellation: CancellationToken) -> None:
        """Refresh picker catalog data before scheduling GUI icon chunks."""

        started_at = perf_counter()
        try:
            if cancellation.is_cancelled:
                return
            trace_mark("cube_icon_warmup.catalog_refresh.start")
            with trace_span("cube_icon_warmup.catalog_refresh"):
                snapshot = self._startup_catalog_snapshot()
            if not isinstance(snapshot, CubeCatalogSnapshot):
                raise TypeError(
                    "startup catalog warmup must return CubeCatalogSnapshot"
                )
        except Exception:
            trace_mark("cube_icon_warmup.catalog_refresh.error")
            log_exception(_LOGGER, "Cube icon startup catalog refresh failed")
            return
        log_timing(
            _LOGGER,
            "Refreshed cube picker catalog for startup icon warmup",
            started_at=started_at,
            catalog_state=snapshot.state,
            cube_count=len(snapshot.entries),
            has_error=snapshot.error is not None,
        )
        if self._shutdown_requested or cancellation.is_cancelled:
            return
        self._scheduler(0, lambda: self._begin_icon_warmup(snapshot))

    def _startup_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return cached picker data when fresh, otherwise refresh once."""

        snapshot = self._cached_catalog_snapshot()
        if snapshot is not None and snapshot.state == "fresh":
            trace_mark(
                "cube_icon_warmup.catalog_snapshot.cached",
                catalog_state=snapshot.state,
                cube_count=len(snapshot.entries),
            )
            return snapshot
        refresh = getattr(self.cube_load_service, "refresh_picker_catalog")
        refreshed = refresh()
        if not isinstance(refreshed, CubeCatalogSnapshot):
            raise TypeError("refresh_picker_catalog must return CubeCatalogSnapshot")
        return refreshed

    def _cached_catalog_snapshot(self) -> CubeCatalogSnapshot | None:
        """Return the immediate picker catalog snapshot when available."""

        snapshot = getattr(self.cube_load_service, "picker_catalog_snapshot", None)
        if not callable(snapshot):
            return None
        cached = snapshot()
        if not isinstance(cached, CubeCatalogSnapshot):
            raise TypeError("picker_catalog_snapshot must return CubeCatalogSnapshot")
        return cached

    def _begin_icon_warmup(self, snapshot: CubeCatalogSnapshot) -> None:
        """Initialize GUI-thread icon warmup state from one catalog snapshot."""

        if self._shutdown_requested:
            return
        trace_mark(
            "cube_icon_warmup.gui.begin",
            cube_count=len(snapshot.entries),
            catalog_state=snapshot.state,
        )
        self._entries = list(snapshot.entries)
        self._next_index = 0
        self._warmed_count = 0
        self._skipped_count = 0
        self._gui_started_at = self.clock()
        if not self._entries:
            self._log_completion(budget_exhausted=False)
            return
        self._schedule_next_chunk()

    def _schedule_next_chunk(self) -> None:
        """Schedule the next GUI-thread icon warmup chunk."""

        if self._shutdown_requested:
            return
        trace_mark(
            "cube_icon_warmup.gui.chunk_scheduled",
            next_index=self._next_index,
            total_count=len(self._entries),
        )
        self._scheduler(0, self._warm_next_chunk)

    def _warm_next_chunk(self) -> None:
        """Warm one bounded GUI chunk of icon records."""

        if self._shutdown_requested:
            return
        chunk_started_at = self.clock()
        trace_mark(
            "cube_icon_warmup.gui.chunk.start",
            next_index=self._next_index,
            total_count=len(self._entries),
            remaining_count=max(0, len(self._entries) - self._next_index),
            chunk_budget_ms=f"{self.gui_chunk_budget_seconds * 1000.0:.3f}",
        )
        batch_limit = max(1, self.batch_size)
        warmed_in_batch = 0
        while self._next_index < len(self._entries) and warmed_in_batch < batch_limit:
            entry = self._entries[self._next_index]
            self._next_index += 1
            warmed_in_batch += 1
            self._warm_entry(entry)
            if self._chunk_budget_exhausted(chunk_started_at):
                break
            if self._budget_exhausted():
                self._trace_chunk_end(
                    chunk_started_at=chunk_started_at,
                    processed_count=warmed_in_batch,
                    budget_exhausted=True,
                )
                self._log_completion(budget_exhausted=True)
                return
        if self._next_index >= len(self._entries):
            self._trace_chunk_end(
                chunk_started_at=chunk_started_at,
                processed_count=warmed_in_batch,
                budget_exhausted=False,
            )
            self._log_completion(budget_exhausted=False)
            return
        if self._budget_exhausted():
            self._trace_chunk_end(
                chunk_started_at=chunk_started_at,
                processed_count=warmed_in_batch,
                budget_exhausted=True,
            )
            self._log_completion(budget_exhausted=True)
            return
        self._trace_chunk_end(
            chunk_started_at=chunk_started_at,
            processed_count=warmed_in_batch,
            budget_exhausted=False,
        )
        self._schedule_next_chunk()

    def _trace_chunk_end(
        self,
        *,
        chunk_started_at: float,
        processed_count: int,
        budget_exhausted: bool,
    ) -> None:
        """Trace the completed GUI chunk size and elapsed time."""

        elapsed_ms = max(0.0, (self.clock() - chunk_started_at) * 1000.0)
        trace_mark(
            "cube_icon_warmup.gui.chunk.end",
            next_index=self._next_index,
            processed_count=processed_count,
            remaining_count=max(0, len(self._entries) - self._next_index),
            warmed_count=self._warmed_count,
            skipped_count=self._skipped_count,
            chunk_elapsed_ms=f"{elapsed_ms:.3f}",
            budget_exhausted=budget_exhausted,
        )

    def _warm_entry(self, entry: CubeCatalogRecord) -> None:
        """Warm one icon record while preserving startup after failures."""

        try:
            warm_icon = getattr(self.cube_icon_factory, "warm_icon_for_cube")
            with trace_span(
                "cube_icon_warmup.gui.entry",
                cube_id=entry.cube_id,
                display_name=entry.display_name,
            ):
                warmed = bool(
                    warm_icon(
                        cube_id=entry.cube_id,
                        display_name=entry.display_name,
                        icon=entry.icon,
                        catalog_revision=entry.catalog_revision,
                        cube_content_hash=entry.content_hash,
                    )
                )
        except Exception as error:
            self._skipped_count += 1
            log_warning(
                _LOGGER,
                "Cube icon startup warmup skipped one icon after failure",
                cube_id=entry.cube_id,
                error=repr(error),
            )
            return
        if warmed:
            self._warmed_count += 1
        else:
            self._skipped_count += 1

    def _budget_exhausted(self) -> bool:
        """Return whether the GUI warmup budget has elapsed."""

        if self.startup_budget_seconds < 0:
            return False
        return (self.clock() - self._gui_started_at) >= self.startup_budget_seconds

    def _chunk_budget_exhausted(self, chunk_started_at: float) -> bool:
        """Return whether this GUI callback should yield after current icon."""

        if self.gui_chunk_budget_seconds < 0:
            return False
        return (self.clock() - chunk_started_at) >= self.gui_chunk_budget_seconds

    def _log_completion(self, *, budget_exhausted: bool) -> None:
        """Log the final observed startup warmup state."""

        elapsed_ms = max(0.0, (self.clock() - self._gui_started_at) * 1000.0)
        log_info(
            _LOGGER,
            "Completed cube icon startup warmup",
            warmed_count=self._warmed_count,
            skipped_count=self._skipped_count,
            total_count=len(self._entries),
            next_index=self._next_index,
            budget_exhausted=budget_exhausted,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )
        trace_mark(
            "cube_icon_warmup.gui.completed",
            warmed_count=self._warmed_count,
            skipped_count=self._skipped_count,
            total_count=len(self._entries),
            next_index=self._next_index,
            budget_exhausted=budget_exhausted,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )


__all__ = ["StartupCubeIconWarmupHandle"]
