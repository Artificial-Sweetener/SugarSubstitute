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

"""Compose shell-scoped Comfy connection recovery collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer

from substitute.application.comfy_connection import ComfyConnectionRecoveryService
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionStateChange,
)
from substitute.presentation.shell.comfy_connection_presenter import (
    ComfyConnectionPresenter,
)
from substitute.presentation.shell.main_window_dependencies import (
    ComfyConnectionMonitorLifecycle,
    MainWindowDependencies,
)
from substitute.presentation.shell.settings_route_controller import (
    SettingsRouteController,
)


@dataclass(frozen=True, slots=True)
class ComfyConnectionRuntimeComposition:
    """Hold one shell's connection policy, monitor, and feedback owner."""

    recovery_service: ComfyConnectionRecoveryService
    monitor: ComfyConnectionMonitorLifecycle
    presenter: ComfyConnectionPresenter


def compose_comfy_connection_runtime(
    shell: Any,
    *,
    dependencies: MainWindowDependencies,
    settings_route_controller: SettingsRouteController,
) -> ComfyConnectionRuntimeComposition:
    """Compose, mount, and start non-destructive Comfy recovery for one shell."""

    recovery_service = ComfyConnectionRecoveryService(
        target=dependencies.comfy_target,
        set_backend_state=shell.generation_action_controller.set_backend_state,
        set_dispatch_available=shell.generation_job_queue_service.set_dispatch_available,
        schedule_delay=lambda delay_ms, callback: QTimer.singleShot(
            delay_ms,
            callback,
        ),
        restart_requester=dependencies.managed_comfy_restart_requester,
    )
    presenter = ComfyConnectionPresenter(
        notification_surface=shell.workspace_body_material_surface,
        request_restart=recovery_service.request_restart,
        open_connection_settings=settings_route_controller.project_comfyui_settings,
    )
    recovery_service.add_observer(presenter.present)

    def refresh_runtime_contracts(change: ComfyConnectionStateChange) -> None:
        """Refresh Comfy-derived caches after monitor-confirmed restart readiness."""

        if (
            change.previous.phase is ComfyConnectionPhase.RESTARTING
            and change.current.phase is ComfyConnectionPhase.READY
        ):
            settings_route_controller.refresh_runtime_contracts_after_cube_dependency_restart()

    recovery_service.add_observer(refresh_runtime_contracts)
    shell.generation_job_queue_service.set_connection_lost_handler(
        recovery_service.report_disconnected
    )
    monitor = dependencies.create_comfy_connection_monitor(
        recovery_service.report_connected,
        recovery_service.report_disconnected,
    )
    shell.shell_resource_lifecycle.register("comfy_connection_monitor", monitor.stop)
    shell.shell_resource_lifecycle.register(
        "comfy_connection_feedback", presenter.close
    )
    composition = ComfyConnectionRuntimeComposition(
        recovery_service=recovery_service,
        monitor=monitor,
        presenter=presenter,
    )
    shell.comfy_connection_recovery_service = recovery_service
    shell.comfy_connection_monitor = monitor
    shell.comfy_connection_presenter = presenter
    settings_route_controller.create_settings_workspace()
    monitor.start()
    return composition


__all__ = [
    "ComfyConnectionRuntimeComposition",
    "compose_comfy_connection_runtime",
]
