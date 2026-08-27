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

"""Tests for byte-bounded closed workflow reopen buffering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowRecord,
)


def _record(
    close_id: str,
    *,
    size: int,
    closed_at: datetime | None = None,
) -> ClosedWorkflowRecord:
    """Build a closed workflow record with deterministic payload size."""

    payload = close_id.encode("utf-8") * size
    return ClosedWorkflowRecord(
        close_id=close_id,
        workflow_id=f"workflow-{close_id}",
        tab_label=f"Workflow {close_id}",
        tab_index=0,
        snapshot_payload=payload,
        payload_size_bytes=len(payload),
        closed_at=closed_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_push_stores_record_and_tracks_total_bytes() -> None:
    """Pushing an accepted record should expose it in newest-first summaries."""

    buffer = ClosedWorkflowBuffer(budget_bytes=100)
    record = _record("a", size=10)

    result = buffer.push(record)

    assert result.accepted is True
    assert result.record is record
    assert result.evicted_records == ()
    assert buffer.total_bytes == record.payload_size_bytes
    summaries = buffer.summaries()
    assert len(summaries) == 1
    assert summaries[0].close_id == "a"
    assert summaries[0].payload_size_bytes == record.payload_size_bytes


def test_push_evicts_oldest_records_until_under_budget() -> None:
    """Buffer budget enforcement should evict oldest retained records first."""

    buffer = ClosedWorkflowBuffer(budget_bytes=9)
    first = _record("a", size=3, closed_at=datetime(2026, 1, 1, tzinfo=UTC))
    second = _record(
        "b",
        size=3,
        closed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=1),
    )
    third = _record(
        "c",
        size=4,
        closed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=2),
    )

    assert buffer.push(first).evicted_records == ()
    assert buffer.push(second).evicted_records == ()
    result = buffer.push(third)

    assert result.accepted is True
    assert result.evicted_records == (first,)
    assert buffer.total_bytes <= buffer.budget_bytes
    assert [summary.close_id for summary in buffer.summaries()] == ["c", "b"]


def test_push_rejects_record_larger_than_budget() -> None:
    """Oversized records should not be retained."""

    buffer = ClosedWorkflowBuffer(budget_bytes=4)
    record = _record("large", size=1)

    result = buffer.push(record)

    assert result.accepted is False
    assert result.record is None
    assert result.evicted_records == ()
    assert buffer.total_bytes == 0
    assert buffer.summaries() == ()


def test_pop_latest_returns_newest_record() -> None:
    """Latest pop should remove the newest retained record."""

    buffer = ClosedWorkflowBuffer(budget_bytes=100)
    first = _record("a", size=3)
    second = _record("b", size=3)
    buffer.push(first)
    buffer.push(second)

    popped = buffer.pop_latest()

    assert popped is second
    assert buffer.total_bytes == first.payload_size_bytes
    assert [summary.close_id for summary in buffer.summaries()] == ["a"]


def test_pop_specific_record_removes_only_that_record() -> None:
    """Specific pop should leave unrelated records in newest-first order."""

    buffer = ClosedWorkflowBuffer(budget_bytes=100)
    first = _record("a", size=3)
    second = _record("b", size=3)
    third = _record("c", size=3)
    buffer.push(first)
    buffer.push(second)
    buffer.push(third)

    popped = buffer.pop("b")

    assert popped is second
    assert [summary.close_id for summary in buffer.summaries()] == ["c", "a"]
    assert buffer.total_bytes == first.payload_size_bytes + third.payload_size_bytes


def test_clear_returns_all_records_and_resets_total_bytes() -> None:
    """Clearing the buffer should return newest-first records and reset size."""

    buffer = ClosedWorkflowBuffer(budget_bytes=100)
    first = _record("a", size=3)
    second = _record("b", size=3)
    buffer.push(first)
    buffer.push(second)

    cleared = buffer.clear()

    assert cleared == (second, first)
    assert buffer.total_bytes == 0
    assert buffer.summaries() == ()
