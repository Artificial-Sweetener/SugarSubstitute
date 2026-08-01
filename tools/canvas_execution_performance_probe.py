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

"""Measure host-backed CuteCanvas dispatch latency without mounting Qt windows."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from _thread import LockType
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event, Lock, enumerate as enumerate_threads
from typing import Protocol

_SOURCE_ROOT = Path(
    os.environ.get(
        "SUGAR_CANVAS_EXECUTION_PROBE_ROOT",
        Path(__file__).resolve().parents[1],
    )
)
sys.path.insert(0, str(_SOURCE_ROOT))

from cutecanvas import (
    ExecutionHandle,
    ExecutionRequest,
    ExecutionRequirements,
    ExecutionSnapshot,
    InlineDispatcher,
)

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime


@dataclass(frozen=True, slots=True)
class CanvasExecutionPerformance:
    """Summarize one deterministic dispatch campaign."""

    jobs: int
    batch_size: int
    elapsed_ms: float
    throughput_per_second: float
    start_p50_ms: float
    start_p95_ms: float
    start_p99_ms: float
    start_max_ms: float
    peak_accepted: int
    peak_pending: int
    peak_running: int
    peak_retained_bytes: int
    peak_worker_threads: int


class _ExecutionScope(Protocol):
    """Submit and close one public CuteCanvas execution scope."""

    def submit(
        self,
        request: ExecutionRequest[int, object],
    ) -> ExecutionHandle[int, object]:
        """Submit one measured request."""

    def close(self, *, reason: str) -> None:
        """Close the measured scope."""


def run_probe(*, jobs: int, batch_size: int) -> CanvasExecutionPerformance:
    """Run bounded batches through the production CuteCanvas integration."""

    if jobs <= 0:
        raise ValueError("jobs must be positive")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    runtime = ExecutionRuntime()
    canvas_runtime = runtime.canvas_execution_runtime
    scope = canvas_runtime.open_scope(
        owner_id="canvas-execution-performance",
        dispatcher=InlineDispatcher(),
    )
    start_latencies: list[float] = []
    latency_lock = Lock()
    pressure = _ProbePressure()
    subscription = canvas_runtime.subscribe_diagnostics(pressure.observe)
    started_at = time.perf_counter()
    try:
        completed = 0
        while completed < jobs:
            count = min(batch_size, jobs - completed)
            handles = [
                _submit_measured(
                    scope, start_latencies, latency_lock, completed + index
                )
                for index in range(count)
            ]
            pressure.observe_threads()
            _await_handles(handles)
            completed += count
        elapsed = time.perf_counter() - started_at
    finally:
        subscription.close()
        scope.close(reason="performance_probe_complete")
        runtime.shutdown()
    ordered = sorted(start_latencies)
    return CanvasExecutionPerformance(
        jobs=jobs,
        batch_size=batch_size,
        elapsed_ms=elapsed * 1000.0,
        throughput_per_second=jobs / elapsed,
        start_p50_ms=statistics.median(ordered),
        start_p95_ms=_nearest_rank(ordered, 0.95),
        start_p99_ms=_nearest_rank(ordered, 0.99),
        start_max_ms=ordered[-1],
        peak_accepted=pressure.peak_accepted,
        peak_pending=pressure.peak_pending,
        peak_running=pressure.peak_running,
        peak_retained_bytes=pressure.peak_retained_bytes,
        peak_worker_threads=pressure.peak_worker_threads,
    )


def _submit_measured(
    scope: _ExecutionScope,
    latencies: list[float],
    latency_lock: LockType,
    sequence: int,
) -> ExecutionHandle[int, object]:
    """Submit one job that records physical start latency."""

    queued_at = time.perf_counter()

    def work(_context: object) -> int:
        """Record physical activation and return stable identity."""

        latency_ms = (time.perf_counter() - queued_at) * 1000.0
        with latency_lock:
            latencies.append(latency_ms)
        return sequence

    return scope.submit(
        ExecutionRequest[int, object](
            operation="performance.canvas_dispatch",
            work=work,
            requirements=ExecutionRequirements(
                estimated_retained_bytes=4 * 1024,
            ),
        )
    )


def _await_handles(handles: list[ExecutionHandle[int, object]]) -> None:
    """Wait for a bounded batch using terminal handle state."""

    settlement = _BatchSettlement(len(handles))
    for handle in handles:
        handle.add_done_callback(settlement.accept)
    if not settlement.wait(timeout_seconds=10.0):
        raise TimeoutError("canvas execution performance batch did not settle")


class _BatchSettlement:
    """Signal when every handle in one bounded probe batch settles."""

    def __init__(self, remaining: int) -> None:
        """Create one exact terminal counter."""

        self._remaining = remaining
        self._event = Event()
        self._lock = Lock()
        if remaining == 0:
            self._event.set()

    def accept(self, _outcome: object) -> None:
        """Count one terminal outcome exactly once."""

        with self._lock:
            self._remaining -= 1
            if self._remaining == 0:
                self._event.set()

    def wait(self, *, timeout_seconds: float) -> bool:
        """Wait for the complete batch with a bounded deadline."""

        return self._event.wait(timeout=timeout_seconds)


class _ProbePressure:
    """Retain peak public diagnostics and physical worker counts."""

    def __init__(self) -> None:
        """Create zeroed, thread-safe peak counters."""

        self._lock = Lock()
        self.peak_accepted = 0
        self.peak_pending = 0
        self.peak_running = 0
        self.peak_retained_bytes = 0
        self.peak_worker_threads = 0

    def observe(self, snapshots: tuple[ExecutionSnapshot, ...]) -> None:
        """Fold one public runtime publication into the measured peaks."""

        accepted = sum(snapshot.accepted for snapshot in snapshots)
        pending = sum(snapshot.pending for snapshot in snapshots)
        running = sum(snapshot.running for snapshot in snapshots)
        retained_bytes = sum(snapshot.retained_bytes for snapshot in snapshots)
        with self._lock:
            self.peak_accepted = max(self.peak_accepted, accepted)
            self.peak_pending = max(self.peak_pending, pending)
            self.peak_running = max(self.peak_running, running)
            self.peak_retained_bytes = max(
                self.peak_retained_bytes,
                retained_bytes,
            )

    def observe_threads(self) -> None:
        """Capture the bounded workers that production execution has started."""

        workers = sum(
            thread.name.startswith("substitute-canvas-")
            and thread.name != "substitute-canvas-diagnostics"
            for thread in enumerate_threads()
        )
        with self._lock:
            self.peak_worker_threads = max(self.peak_worker_threads, workers)


def _nearest_rank(ordered: list[float], percentile: float) -> float:
    """Return one nearest-rank percentile from a non-empty ordered sample."""

    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def main() -> int:
    """Run the probe and print one machine-readable result."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=128)
    arguments = parser.parse_args()
    result = run_probe(jobs=arguments.jobs, batch_size=arguments.batch_size)
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
