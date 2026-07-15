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

"""Count pending queue jobs for generation queue presentation surfaces."""

from __future__ import annotations

from collections.abc import Iterable

PENDING_QUEUE_JOB_STATUSES = frozenset({"pending"})


def pending_generation_queue_job_count(jobs: Iterable[object]) -> int:
    """Return the pending job count for queue badges and headers."""

    return sum(
        1 for job in jobs if getattr(job, "status", None) in PENDING_QUEUE_JOB_STATUSES
    )


def generation_skip_action_available(
    *,
    continuous_active: bool,
    queue_has_active: bool,
    pending_queue_job_count: int,
) -> bool:
    """Return whether skip advances distinct generation work."""

    return continuous_active or (queue_has_active and pending_queue_job_count > 0)


__all__ = [
    "PENDING_QUEUE_JOB_STATUSES",
    "generation_skip_action_available",
    "pending_generation_queue_job_count",
]
