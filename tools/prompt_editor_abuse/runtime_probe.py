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

"""Capture harness-only Python runtime costs around one editor operation."""

from __future__ import annotations

from dataclasses import dataclass
import gc
import sys
from time import perf_counter
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptAbuseRuntimeSample:
    """Describe allocations and cyclic-GC work observed during one operation."""

    allocated_block_delta: int
    gc_collection_count: int
    gc_collected_objects: int
    gc_pause_ms: float


class PromptAbuseRuntimeProbe:
    """Own a temporary GC callback for one action's measured input units."""

    def __init__(self, *, enabled: bool) -> None:
        """Install no callback until the probe enters its bounded lifetime."""

        self._enabled = enabled
        self._active = False
        self._allocated_blocks_before = 0
        self._collection_started_at: float | None = None
        self._collection_count = 0
        self._collected_objects = 0
        self._gc_pause_ms = 0.0

    def __enter__(self) -> PromptAbuseRuntimeProbe:
        """Install the harness callback without changing GC policy."""

        if self._enabled:
            gc.callbacks.append(self._on_gc_phase)
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        """Remove the exact callback installed for this probe."""

        del exception_type, exception, traceback
        if self._enabled and self._on_gc_phase in gc.callbacks:
            gc.callbacks.remove(self._on_gc_phase)

    def begin_sample(self) -> None:
        """Begin attributing allocations and collections to one operation."""

        if not self._enabled:
            return
        self._active = True
        self._allocated_blocks_before = sys.getallocatedblocks()
        self._collection_started_at = None
        self._collection_count = 0
        self._collected_objects = 0
        self._gc_pause_ms = 0.0

    def finish_sample(self) -> PromptAbuseRuntimeSample:
        """Finish the active operation and return its runtime evidence."""

        if not self._enabled:
            return PromptAbuseRuntimeSample(0, 0, 0, 0.0)
        allocated_block_delta = sys.getallocatedblocks() - self._allocated_blocks_before
        self._active = False
        self._collection_started_at = None
        return PromptAbuseRuntimeSample(
            allocated_block_delta=allocated_block_delta,
            gc_collection_count=self._collection_count,
            gc_collected_objects=self._collected_objects,
            gc_pause_ms=self._gc_pause_ms,
        )

    def _on_gc_phase(self, phase: str, info: dict[str, Any]) -> None:
        """Record only collections occurring inside the active sample window."""

        if not self._active:
            return
        if phase == "start":
            self._collection_started_at = perf_counter()
            return
        if phase != "stop":
            return
        started_at = self._collection_started_at
        if started_at is not None:
            self._gc_pause_ms += (perf_counter() - started_at) * 1_000.0
        self._collection_started_at = None
        self._collection_count += 1
        self._collected_objects += int(info.get("collected", 0))


__all__ = ["PromptAbuseRuntimeProbe", "PromptAbuseRuntimeSample"]
