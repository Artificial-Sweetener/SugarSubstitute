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

"""Tests for one managed ComfyUI process behavior owner."""

from __future__ import annotations

from __future__ import annotations
from io import BytesIO
from pathlib import Path
import threading
from typing import IO, cast
import pytest
from substitute.infrastructure.comfy import (
    managed_launcher,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)

from tests.infrastructure.comfy.managed_process.threaded_task_support import (
    _managed_task_factory,
)


class _ControlledOutputStream:
    """Release one output chunk only after the test permits reading."""

    def __init__(self, chunk: bytes) -> None:
        """Store one chunk and initialize read coordination."""

        self._chunk = chunk
        self._released = threading.Event()
        self._emitted = False
        self.close_count = 0

    def release(self) -> None:
        """Allow the blocked pump read to continue."""

        self._released.set()

    def read(self, _size: int = -1) -> bytes:
        """Return the chunk once, then EOF."""

        assert self._released.wait(timeout=2)
        if self._emitted:
            return b""
        self._emitted = True
        return self._chunk

    def close(self) -> None:
        """Record close calls without invalidating the test stream."""

        self.close_count += 1


def test_iter_output_records_preserves_carriage_return_progress_updates() -> None:
    """Managed output parsing should preserve in-place redraw records."""

    records = tuple(
        managed_launcher._iter_output_records(
            BytesIO(
                (
                    b"FETCH ComfyRegistry Data: 5/133\r"
                    b"FETCH ComfyRegistry Data: 10/133\r"
                    b"Prompt executed in 12.61 seconds\n"
                )
            ),
            chunk_size=7,
        )
    )

    assert records == (
        "FETCH ComfyRegistry Data: 5/133\r",
        "FETCH ComfyRegistry Data: 10/133\r",
        "Prompt executed in 12.61 seconds\n",
    )


def test_iter_output_records_preserves_interleaved_carriage_return_and_newline_records() -> (
    None
):
    """Managed output parsing should preserve mixed redraw and stable records."""

    records = tuple(
        managed_launcher._iter_output_records(
            BytesIO(
                (
                    b"  0%|          | 0/28 [00:00<?, ?it/s]\r"
                    b"FETCH ComfyRegistry Data: 25/134\n"
                    b" 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r"
                )
            ),
            chunk_size=11,
        )
    )

    assert records == (
        "  0%|          | 0/28 [00:00<?, ?it/s]\r",
        "FETCH ComfyRegistry Data: 25/134\n",
        " 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r",
    )


def test_managed_output_pump_emits_harness_timing_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness runs should expose output-pump fanout timing."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    records: list[str] = []
    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    task = managed_launcher._start_output_pump_task(
        state=state,
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=BytesIO(b"Starting server\nTo see the GUI go to: http://x\n"),
        on_log=records.append,
    )
    join = getattr(task, "join")
    join(timeout=2)

    assert records[:2] == [
        "Starting server\n",
        "To see the GUI go to: http://x\n",
    ]
    assert any(
        record.startswith(
            "Substitute startup diagnostic event=managed_output_pump_timing "
        )
        and "record_count=2" in record
        and "total_on_log_ms=" in record
        and "max_on_log_ms=" in record
        for record in records
    )


def test_managed_request_stop_preserves_live_output_stream(
    tmp_path: Path,
) -> None:
    """Startup cancellation must not close Comfy's process-owned output pipe."""

    records: list[str] = []
    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    stdout_stream = _ControlledOutputStream(b"  0%|          | 0/28\r")

    task = managed_launcher._start_output_pump_task(
        state=state,
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=cast(IO[bytes], stdout_stream),
        on_log=records.append,
    )

    state.add_process_pump(task)
    state.request_stop(reason="startup_cancelled")
    stdout_stream.release()
    join = getattr(task, "join")
    join(timeout=2)

    assert records == ["  0%|          | 0/28\r"]
    assert stdout_stream.close_count == 1


def test_managed_output_pump_survives_log_consumer_failure(
    tmp_path: Path,
) -> None:
    """Output consumer failures must not close Comfy's process-owned pipe."""

    records: list[str] = []
    failures_remaining = 1

    def _flaky_consumer(record: str) -> None:
        """Fail once, then collect subsequent output records."""

        nonlocal failures_remaining
        if failures_remaining:
            failures_remaining -= 1
            raise RuntimeError("consumer disposed")
        records.append(record)

    task = managed_launcher._start_output_pump_task(
        state=managed_launcher.ManagedComfyState(
            registry=ManagedProcessRegistry(tmp_path)
        ),
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=BytesIO(b"first\rsecond\n"),
        on_log=_flaky_consumer,
    )
    join = getattr(task, "join")
    join(timeout=2)

    assert records == ["second\n"]
