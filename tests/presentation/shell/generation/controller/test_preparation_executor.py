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

"""Contract tests for workspace generation presentation controller behavior."""

from __future__ import annotations


from substitute.application.generation import (
    GenerationPreparationResult,
)
from tests.support.execution import QueuedTaskSubmitter
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationPreparationExecutor,
)


def test_generation_preparation_executor_close_cancels_and_suppresses_callbacks() -> (
    None
):
    """Closing generation preparation should cancel scoped work and drop callbacks."""

    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    completed: list[GenerationPreparationResult] = []
    failed: list[BaseException] = []
    executor = GenerationPreparationExecutor(
        submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )

    executor.submit(
        prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
        on_completed=completed.append,
        on_failed=failed.append,
    )

    assert len(submitter.handles) == 1
    assert submitter.handles[0].state == "pending"

    executor.close()

    assert close_calls == ["closed"]
    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "generation_preparation_executor_closed"
    assert submitter.handles[0].state == "cancelled"
    assert completed == []
    assert failed == []

    try:
        executor.submit(
            prepare_snapshots=lambda: GenerationPreparationResult(snapshots=()),
            on_completed=completed.append,
            on_failed=failed.append,
        )
    except RuntimeError as error:
        assert "closed" in str(error)
    else:
        raise AssertionError("closed generation preparation accepted new work")
