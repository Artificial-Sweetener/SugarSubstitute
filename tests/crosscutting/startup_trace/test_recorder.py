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

"""Contract tests for truthful startup trace recording."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.shared import startup_trace


@pytest.fixture(autouse=True)
def _isolate_startup_trace_recorder() -> Iterator[None]:
    """Prevent test-configured startup recorders from leaking between tests."""

    startup_trace.close_startup_trace()
    yield
    startup_trace.close_startup_trace()


def _read_trace_records(trace_path: Path) -> list[dict[str, Any]]:
    """Return JSONL startup trace records from one trace file."""

    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_configure_startup_trace_writes_prompt_safe_mark(tmp_path: Path) -> None:
    """Configured startup traces should write structured prompt-safe mark events."""

    ticks = iter((100,))
    trace_path = startup_trace.configure_startup_trace(
        tmp_path,
        clock_ns=lambda: next(ticks),
    )

    startup_trace.trace_mark(
        "startup.ready",
        route="ready",
        workflow_count=2,
        install_root=tmp_path / "install",
        api_key="secret",
    )
    startup_trace.close_startup_trace()

    records = _read_trace_records(trace_path)
    assert trace_path == tmp_path.resolve() / "startup-trace.jsonl"
    assert records == [
        {
            "event": "startup.ready",
            "fields": {
                "rejected_field_count": 2,
                "route": "ready",
                "workflow_count": 2,
            },
            "kind": "mark",
            "sequence": 1,
            "timestamp_ns": 100,
        }
    ]
    assert "secret" not in trace_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in trace_path.read_text(encoding="utf-8")


def test_trace_span_records_elapsed_duration(tmp_path: Path) -> None:
    """Startup trace spans should record elapsed nanoseconds on normal exit."""

    ticks = iter((10, 50))
    trace_path = startup_trace.configure_startup_trace(
        tmp_path,
        clock_ns=lambda: next(ticks),
    )

    with startup_trace.trace_span("startup.phase", phase="theme"):
        pass
    startup_trace.close_startup_trace()

    assert _read_trace_records(trace_path) == [
        {
            "elapsed_ns": 40,
            "event": "startup.phase",
            "fields": {"phase": "theme"},
            "kind": "span",
            "sequence": 1,
            "timestamp_ns": 50,
        }
    ]


def test_trace_span_records_failure_without_exception_text(tmp_path: Path) -> None:
    """Startup trace spans should preserve failures without logging messages."""

    ticks = iter((1, 10))
    trace_path = startup_trace.configure_startup_trace(
        tmp_path,
        clock_ns=lambda: next(ticks),
    )

    with pytest.raises(RuntimeError, match="prompt text"):
        with startup_trace.trace_span("startup.failure"):
            raise RuntimeError("prompt text must not be serialized")
    startup_trace.close_startup_trace()

    written_text = trace_path.read_text(encoding="utf-8")
    assert "prompt text must not be serialized" not in written_text
    assert _read_trace_records(trace_path)[0]["fields"] == {
        "error_type": "RuntimeError"
    }


def test_trace_qtimer_single_shot_records_schedule_and_callback(
    tmp_path: Path,
) -> None:
    """Startup trace timer helper should record queued and fired callbacks."""

    ticks = iter((1, 10, 20))
    trace_path = startup_trace.configure_startup_trace(
        tmp_path,
        clock_ns=lambda: next(ticks),
    )
    scheduled_callbacks: list[Callable[[], None]] = []
    callback_calls: list[str] = []

    def scheduler(delay_ms: int, callback: Callable[[], None]) -> None:
        """Capture the scheduled timer callback."""

        assert delay_ms == 7
        scheduled_callbacks.append(callback)

    startup_trace.trace_qtimer_single_shot(
        "startup.delayed",
        scheduler,
        7,
        lambda: callback_calls.append("fired"),
    )
    scheduled_callbacks.pop()()
    startup_trace.close_startup_trace()

    records = _read_trace_records(trace_path)
    assert callback_calls == ["fired"]
    assert [record["event"] for record in records] == [
        "qtimer.single_shot.scheduled",
        "qtimer.single_shot.fired",
    ]
    assert records[0]["fields"] == {"delay_ms": 7, "timer_name": "startup.delayed"}
    assert records[1]["elapsed_ns"] == 19


def test_close_startup_trace_makes_late_events_safe(tmp_path: Path) -> None:
    """Late startup trace calls after close should be ignored safely."""

    ticks = iter((1,))
    trace_path = startup_trace.configure_startup_trace(
        tmp_path,
        clock_ns=lambda: next(ticks),
    )
    scheduled_callbacks: list[Callable[[], None]] = []

    startup_trace.close_startup_trace()
    startup_trace.trace_mark("startup.late")
    with startup_trace.trace_span("startup.late_span"):
        pass
    startup_trace.trace_qtimer_single_shot(
        "startup.late_timer",
        lambda delay_ms, callback: scheduled_callbacks.append(callback),
        1,
        lambda: None,
    )

    assert trace_path.read_text(encoding="utf-8") == ""
    assert len(scheduled_callbacks) == 1


def test_startup_trace_open_failure_disables_recording(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Recorder configuration failures should not block startup."""

    def fail_open(self: Path, *args: Any, **kwargs: Any) -> object:
        """Raise an OSError for trace file creation."""

        if self.name == "startup-trace.jsonl":
            raise OSError("cannot create trace")
        return cast(Any, original_open)(self, *args, **kwargs)

    original_open = Path.open
    monkeypatch.setattr(Path, "open", fail_open)

    trace_path = startup_trace.configure_startup_trace(tmp_path)
    startup_trace.trace_mark("startup.after_failure", route="ready")
    startup_trace.close_startup_trace()

    assert trace_path == tmp_path.resolve() / "startup-trace.jsonl"
    assert not trace_path.exists()
