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

"""Compose long-lived backend event listeners on process-owned execution lanes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.application.execution import (
    DirectExecutionDispatcher,
    ExecutionContext,
    TaskIdentity,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.execution import LongLivedTaskHandle
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


class ComfyConnectionMonitorLifecycle(Protocol):
    """Describe the monitor lifecycle returned without importing its adapter."""

    def start(self) -> None:
        """Start connection monitoring."""

    def stop(self) -> None:
        """Stop connection monitoring."""


ComfyConnectionMonitorFactory = Callable[
    [Callable[[], None], Callable[[], None]],
    ComfyConnectionMonitorLifecycle,
]


def start_backend_event_listener_task(
    *,
    execution_runtime: ExecutionRuntime,
    registry_key: str,
    identity: TaskIdentity,
    context: ExecutionContext,
    work: LongLivedWork[None],
    thread_name: str,
) -> LongLivedTaskHandle[None]:
    """Start one registered backend listener on its process-lifetime lane."""

    return execution_runtime.start_long_lived(
        "backend_event_listener",
        registry_key,
        identity=identity,
        context=context,
        work=work,
        dispatcher=DirectExecutionDispatcher(),
        thread_name=thread_name,
    )


def build_comfy_connection_monitor_factory(
    *,
    endpoint: ComfyEndpoint,
    execution_runtime: ExecutionRuntime,
    qt_owner: QObject,
) -> ComfyConnectionMonitorFactory:
    """Build the shell factory for persistent Comfy connection monitors."""

    def create_monitor(
        on_connected: Callable[[], None],
        on_disconnected: Callable[[], None],
    ) -> ComfyConnectionMonitorLifecycle:
        """Create one monitor that projects connection edges onto the Qt owner."""

        from substitute.infrastructure.comfy.connection_monitor import (
            ComfyConnectionMonitor,
        )

        update_dispatcher = QtOwnerThreadDispatcher(qt_owner)
        return ComfyConnectionMonitor(
            endpoint=endpoint,
            on_connected=lambda: update_dispatcher.publish(
                on_connected,
                reason="comfy_connection_restored",
            ),
            on_disconnected=lambda: update_dispatcher.publish(
                on_disconnected,
                reason="comfy_connection_lost",
            ),
            task_factory=lambda identity, context, work, thread_name: (
                start_backend_event_listener_task(
                    execution_runtime=execution_runtime,
                    registry_key="comfy_connection",
                    identity=identity,
                    context=context,
                    work=work,
                    thread_name=thread_name,
                )
            ),
        )

    return create_monitor


__all__ = [
    "ComfyConnectionMonitorFactory",
    "build_comfy_connection_monitor_factory",
    "start_backend_event_listener_task",
]
