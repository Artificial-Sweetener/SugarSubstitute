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

"""Verify pure generation queue count and skip-action policy."""

from __future__ import annotations

import pytest

from substitute.presentation.generation.queue_counts import (
    generation_skip_action_available,
    pending_generation_queue_job_count,
)
from tests.presentation.generation.queue.support import queue_job


def test_pending_generation_queue_job_count_excludes_active_and_terminal_jobs() -> None:
    """Count only jobs waiting for dispatch."""

    jobs = (
        queue_job("pending", status="pending"),
        queue_job("dispatching", status="dispatching"),
        queue_job("comfy-pending", status="comfy_pending"),
        queue_job("running", status="running"),
        queue_job("completed", status="completed"),
        queue_job("failed", status="failed"),
        queue_job("cancelled", status="cancelled"),
    )

    assert pending_generation_queue_job_count(jobs) == 1


@pytest.mark.parametrize(
    ("continuous_active", "queue_has_active", "pending_count", "expected"),
    (
        pytest.param(False, True, 0, False, id="normal-active-without-pending"),
        pytest.param(False, True, 1, True, id="normal-active-with-pending"),
        pytest.param(True, False, 0, True, id="continuous-without-visible-queue"),
        pytest.param(False, False, 1, False, id="pending-without-active"),
    ),
)
def test_generation_skip_action_available_requires_distinct_next_work(
    *,
    continuous_active: bool,
    queue_has_active: bool,
    pending_count: int,
    expected: bool,
) -> None:
    """Distinguish continuous loops from normal stop behavior."""

    assert (
        generation_skip_action_available(
            continuous_active=continuous_active,
            queue_has_active=queue_has_active,
            pending_queue_job_count=pending_count,
        )
        is expected
    )
