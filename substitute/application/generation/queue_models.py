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

"""Define generation queue transaction and projection value objects."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Literal

from substitute.application.generation.generation_models import GenerationCallbacks
from substitute.domain.generation import GenerationJobSnapshot, GenerationQueueJob

GenerationQueueChangeKind = Literal["structural", "progress"]
QueueObserver = Callable[["GenerationQueueStateChange"], None]
GenerationJobLifecycleAction = Literal[
    "enqueued",
    "dispatching",
    "running",
    "output",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class GenerationJobLifecycleEvent:
    """Describe one queue lifecycle transition with its generation snapshot."""

    action: GenerationJobLifecycleAction
    job: GenerationQueueJob


@dataclass(frozen=True, slots=True)
class GenerationQueueStateChange:
    """Describe one queue publication for UI and action projection."""

    jobs: tuple[GenerationQueueJob, ...]
    change_kind: GenerationQueueChangeKind
    changed_job_id: str | None = None


GenerationJobLifecycleObserver = Callable[[GenerationJobLifecycleEvent], None]


@dataclass(frozen=True, slots=True)
class QueueProjectionCacheKey:
    """Identify one valid projected queue state."""

    queue_revision: int
    output_projection_key: Hashable


@dataclass(frozen=True, slots=True)
class GenerationQueueBatchEntry:
    """Pair one prepared snapshot with its queue callbacks for batched insertion."""

    snapshot: GenerationJobSnapshot
    callbacks: GenerationCallbacks


@dataclass(frozen=True, slots=True)
class QueueBatchContext:
    """Describe one queue insertion transaction for logging and diagnostics."""

    snapshot_count: int
    scene_run_id: str | None
    scene_count: int | None
    workflow_id: str | None
    workflow_name: str | None


__all__ = [
    "GenerationJobLifecycleAction",
    "GenerationJobLifecycleEvent",
    "GenerationJobLifecycleObserver",
    "GenerationQueueBatchEntry",
    "GenerationQueueChangeKind",
    "GenerationQueueStateChange",
    "QueueObserver",
    "QueueBatchContext",
    "QueueProjectionCacheKey",
]
