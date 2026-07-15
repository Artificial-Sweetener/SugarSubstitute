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

"""Provide byte-bounded process-local storage for closed workflows."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime

CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ClosedWorkflowRecord:
    """Store one serialized process-local closed workflow snapshot."""

    close_id: str
    workflow_id: str
    tab_label: str
    tab_index: int
    snapshot_payload: bytes
    payload_size_bytes: int
    closed_at: datetime


@dataclass(frozen=True, slots=True)
class ClosedWorkflowSummary:
    """Expose UI-safe metadata for one closed workflow record."""

    close_id: str
    workflow_id: str
    tab_label: str
    tab_index: int
    payload_size_bytes: int
    closed_at: datetime


@dataclass(frozen=True, slots=True)
class ClosedWorkflowPushResult:
    """Describe the outcome of pushing one closed workflow record."""

    accepted: bool
    record: ClosedWorkflowRecord | None
    evicted_records: tuple[ClosedWorkflowRecord, ...]


class ClosedWorkflowBuffer:
    """Bound process-local closed workflow snapshots by serialized byte size."""

    def __init__(
        self,
        *,
        budget_bytes: int = CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES,
    ) -> None:
        """Create an empty closed workflow buffer."""

        if budget_bytes < 0:
            raise ValueError("Closed workflow buffer budget cannot be negative.")
        self._budget_bytes = budget_bytes
        self._records: OrderedDict[str, ClosedWorkflowRecord] = OrderedDict()
        self._total_bytes = 0

    @property
    def budget_bytes(self) -> int:
        """Return the configured byte budget."""

        return self._budget_bytes

    @property
    def total_bytes(self) -> int:
        """Return current retained serialized payload bytes."""

        return self._total_bytes

    def push(self, record: ClosedWorkflowRecord) -> ClosedWorkflowPushResult:
        """Store record and evict older records until within budget."""

        normalized = self._normalized_record(record)
        if normalized.payload_size_bytes > self._budget_bytes:
            return ClosedWorkflowPushResult(
                accepted=False,
                record=None,
                evicted_records=(),
            )

        replaced = self._records.pop(normalized.close_id, None)
        if replaced is not None:
            self._total_bytes -= replaced.payload_size_bytes

        self._records[normalized.close_id] = normalized
        self._total_bytes += normalized.payload_size_bytes
        evicted = self._evict_until_within_budget()
        return ClosedWorkflowPushResult(
            accepted=True,
            record=normalized,
            evicted_records=evicted,
        )

    def pop_latest(self) -> ClosedWorkflowRecord | None:
        """Remove and return the most recently closed workflow record."""

        if not self._records:
            return None
        _close_id, record = self._records.popitem(last=True)
        self._total_bytes -= record.payload_size_bytes
        return record

    def pop(self, close_id: str) -> ClosedWorkflowRecord | None:
        """Remove and return one closed workflow record by id."""

        record = self._records.pop(close_id, None)
        if record is None:
            return None
        self._total_bytes -= record.payload_size_bytes
        return record

    def summaries(self) -> tuple[ClosedWorkflowSummary, ...]:
        """Return newest-first summaries for presentation commands."""

        return tuple(
            ClosedWorkflowSummary(
                close_id=record.close_id,
                workflow_id=record.workflow_id,
                tab_label=record.tab_label,
                tab_index=record.tab_index,
                payload_size_bytes=record.payload_size_bytes,
                closed_at=record.closed_at,
            )
            for record in reversed(self._records.values())
        )

    def clear(self) -> tuple[ClosedWorkflowRecord, ...]:
        """Remove all records and return them for caller-owned cleanup."""

        records = tuple(reversed(self._records.values()))
        self._records.clear()
        self._total_bytes = 0
        return records

    def _evict_until_within_budget(self) -> tuple[ClosedWorkflowRecord, ...]:
        """Evict oldest records until retained payload bytes fit the budget."""

        evicted: list[ClosedWorkflowRecord] = []
        while self._total_bytes > self._budget_bytes and self._records:
            _close_id, record = self._records.popitem(last=False)
            self._total_bytes -= record.payload_size_bytes
            evicted.append(record)
        return tuple(evicted)

    @staticmethod
    def _normalized_record(record: ClosedWorkflowRecord) -> ClosedWorkflowRecord:
        """Return record with payload size derived from its retained bytes."""

        payload_size = len(record.snapshot_payload)
        if record.payload_size_bytes == payload_size:
            return record
        return ClosedWorkflowRecord(
            close_id=record.close_id,
            workflow_id=record.workflow_id,
            tab_label=record.tab_label,
            tab_index=record.tab_index,
            snapshot_payload=record.snapshot_payload,
            payload_size_bytes=payload_size,
            closed_at=record.closed_at,
        )


__all__ = [
    "CLOSED_WORKFLOW_BUFFER_BUDGET_BYTES",
    "ClosedWorkflowBuffer",
    "ClosedWorkflowPushResult",
    "ClosedWorkflowRecord",
    "ClosedWorkflowSummary",
]
