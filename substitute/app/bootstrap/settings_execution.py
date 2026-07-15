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

"""Compose Settings execution runners from the application runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, TypeVar

from PySide6.QtCore import QObject

from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
    TaskSubmitter,
)
from substitute.infrastructure.execution.thread_pool_lane import CompletionDispatcher
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher

if TYPE_CHECKING:
    from substitute.presentation.settings.settings_async import (
        SettingsAsyncTaskRunner,
        SettingsAsyncTaskRunnerFactory,
    )

TResult = TypeVar("TResult")

_SETTINGS_LANE = "settings_io"


class RuntimeSettingsSubmitter(TaskSubmitter, Protocol):
    """Describe a runtime submitter with explicit dispatcher-route cleanup."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one settings task."""

    def close(self) -> None:
        """Release the runtime dispatcher route."""


class SettingsExecutionRuntime(Protocol):
    """Describe the runtime factory needed by Settings composition."""

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: CompletionDispatcher,
    ) -> RuntimeSettingsSubmitter:
        """Create one owner-scoped runtime submitter."""


class SettingsRunnerResourceLifecycle(Protocol):
    """Describe shell lifecycle registration for Settings runner cleanup."""

    def register(self, resource_name: str, cleanup: Callable[[], None]) -> None:
        """Register one Settings runner cleanup operation."""


def create_settings_task_runner_factory(
    execution_runtime: SettingsExecutionRuntime,
    *,
    resource_lifecycle: SettingsRunnerResourceLifecycle,
) -> SettingsAsyncTaskRunnerFactory:
    """Return a factory that binds Settings runners to shell-owned routes."""

    def create_runner(parent: QObject, *, owner_id: str) -> SettingsAsyncTaskRunner:
        """Create one Settings runner for a widget owner."""

        from substitute.presentation.settings.settings_async import (
            SettingsAsyncTaskRunner,
        )

        runtime_submitter = execution_runtime.submitter(
            _SETTINGS_LANE,
            owner_id=owner_id,
            dispatcher=QtOwnerThreadDispatcher(parent),
        )
        runner = SettingsAsyncTaskRunner(
            parent,
            submitter=runtime_submitter,
            close_submitter=runtime_submitter.close,
            owner_id=owner_id,
        )
        resource_lifecycle.register(
            f"settings_runner:{owner_id}",
            runner.shutdown,
        )
        return runner

    return create_runner


__all__ = [
    "SettingsExecutionRuntime",
    "SettingsRunnerResourceLifecycle",
    "RuntimeSettingsSubmitter",
    "create_settings_task_runner_factory",
]
