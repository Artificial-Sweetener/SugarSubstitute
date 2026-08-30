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

"""Contract tests for shared Settings async task execution."""

from __future__ import annotations

from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskResult,
    SettingsAsyncTaskRunner,
)
from tests.support.execution import ImmediateTaskSubmitter


def test_settings_async_runner_emits_success_result() -> None:
    """Successful Settings tasks should emit typed result payloads."""

    runner = SettingsAsyncTaskRunner(
        submitter=ImmediateTaskSubmitter(),
    )
    completed: list[SettingsAsyncTaskResult] = []
    runner.taskCompleted.connect(completed.append)

    runner.run(
        task_id="settings.test.success",
        generation=3,
        operation=lambda: "loaded",
        context={"page": "test"},
    )

    assert completed == [
        SettingsAsyncTaskResult(
            task_id="settings.test.success",
            generation=3,
            value="loaded",
            error=None,
            context={"page": "test"},
        )
    ]
    runner.shutdown()


def test_settings_async_runner_emits_failure_result() -> None:
    """Failed Settings tasks should emit typed failures instead of vanishing."""

    runner = SettingsAsyncTaskRunner(
        submitter=ImmediateTaskSubmitter(),
    )
    completed: list[SettingsAsyncTaskResult] = []
    runner.taskCompleted.connect(completed.append)

    def fail() -> object:
        """Raise a deterministic task failure."""

        raise RuntimeError("deterministic failure")

    runner.run(
        task_id="settings.test.failure",
        generation=4,
        operation=fail,
        context={"page": "test"},
    )

    assert completed[0].task_id == "settings.test.failure"
    assert completed[0].generation == 4
    assert completed[0].value is None
    assert isinstance(completed[0].error, RuntimeError)
    assert completed[0].context == {"page": "test"}
    runner.shutdown()
