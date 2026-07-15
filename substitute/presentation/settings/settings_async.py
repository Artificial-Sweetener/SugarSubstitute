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

"""Run Settings page work off the UI thread with Qt-safe result delivery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.settings.settings_async")
_SETTINGS_LANE = "settings_io"


@dataclass(frozen=True, slots=True)
class SettingsAsyncTaskResult:
    """Describe the completed result of one Settings background task."""

    task_id: str
    generation: int
    value: object | None
    error: BaseException | None
    context: Mapping[str, object]

    @property
    def succeeded(self) -> bool:
        """Return whether the background operation completed without error."""

        return self.error is None


class SettingsAsyncTaskRunner(QObject):
    """Execute Settings page operations through the injected task route."""

    taskCompleted = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
        owner_id: str = "settings_async",
    ) -> None:
        """Create a settings task runner backed by the execution layer."""

        super().__init__(parent)
        self._owner_id = owner_id
        self._scope = TaskScope(submitter=submitter, scope_id=owner_id)
        self._close_submitter = close_submitter
        self.destroyed.connect(lambda _obj=None: self.shutdown())

    def run(
        self,
        *,
        task_id: str,
        generation: int,
        operation: Callable[[], object],
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Submit one settings operation and emit a typed result on completion."""

        context_snapshot = dict(context or {})
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=max(0, generation),
                domain="settings",
                parts=(("operation_key", task_id),),
            ),
            context=ExecutionContext(
                operation=task_id,
                reason="settings_async_task",
                lane=_SETTINGS_LANE,
                owner_id=self._owner_id,
                safe_fields=_execution_safe_fields(
                    task_id=task_id,
                    generation=generation,
                    context=context_snapshot,
                ),
            ),
            work=lambda _token: operation(),
        )
        handle = self._scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._emit_result(
                outcome,
                task_id=task_id,
                generation=generation,
                context=context_snapshot,
            ),
            reason="settings_async_completed",
        )

    def has_pending_work(self) -> bool:
        """Return whether this runner still owns unsettled settings work."""

        return self._scope.has_pending_work()

    def shutdown(self) -> None:
        """Cancel pending work and release any locally owned execution lane."""

        self._scope.close(reason="settings_async_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _emit_result(
        self,
        outcome: TaskOutcome[object],
        *,
        task_id: str,
        generation: int,
        context: Mapping[str, object],
    ) -> None:
        """Emit one settings task result from a settled execution outcome."""

        if outcome.cancelled:
            return
        if outcome.error is not None:
            log_exception(
                _LOGGER,
                "Settings async task failed",
                task_id=task_id,
                generation=generation,
                context=dict(context),
                error_type=type(outcome.error).__name__,
            )
            self.taskCompleted.emit(
                SettingsAsyncTaskResult(
                    task_id=task_id,
                    generation=generation,
                    value=None,
                    error=outcome.error,
                    context=context,
                )
            )
            return
        self.taskCompleted.emit(
            SettingsAsyncTaskResult(
                task_id=task_id,
                generation=generation,
                value=outcome.result,
                error=None,
                context=context,
            )
        )


def _execution_safe_fields(
    *,
    task_id: str,
    generation: int,
    context: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    """Return sanitized execution fields for settings async diagnostics."""

    fields: list[tuple[str, object]] = [
        ("operation_key", task_id),
        ("generation", generation),
    ]
    page = context.get("page")
    if isinstance(page, str) and page.strip():
        fields.append(("page_id", page))
    return tuple(fields)


class SettingsAsyncTaskRunnerFactory(Protocol):
    """Create Settings async runners for owner widgets."""

    def __call__(
        self,
        parent: QObject,
        *,
        owner_id: str,
    ) -> SettingsAsyncTaskRunner:
        """Return a runner whose lifecycle is bound to the parent owner."""


__all__ = [
    "SettingsAsyncTaskResult",
    "SettingsAsyncTaskRunner",
    "SettingsAsyncTaskRunnerFactory",
]
