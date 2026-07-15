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

"""Compose startup support state and adapter bundles."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.ready_shell_state import (
    ReadyShellStateBundle,
    create_ready_shell_state_bundle,
)
from substitute.app.bootstrap.shell_reload_adapter import (
    StartupShellReloadState,
    create_startup_shell_reload_state,
)
from substitute.app.bootstrap.startup_cancellation import (
    StartupCancellationState,
    create_startup_cancellation_state,
)
from substitute.app.bootstrap.startup_managed_ready_ports import (
    create_startup_managed_ready_factory_ports,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import (
    StartupQtSchedulerPorts,
    create_startup_qt_scheduler_ports,
)
from substitute.app.bootstrap.startup_shell_ports import (
    create_startup_shell_composition_ports,
)
from substitute.app.bootstrap.startup_splash_controller import (
    StartupCancelBridge,
    StartupSplashPorts,
    create_startup_splash_ports,
)


@dataclass(frozen=True, slots=True)
class StartupSupportGraph:
    """Group startup support objects built before route orchestration."""

    ready_shell_state: ReadyShellStateBundle
    shell_reload_state: StartupShellReloadState
    startup_splash_ports: StartupSplashPorts
    startup_cancel_bridge: StartupCancelBridge
    startup_cancellation_state: StartupCancellationState
    startup_qt_schedulers: StartupQtSchedulerPorts
    shell_ports: StartupShellCompositionPorts
    managed_ready_ports: StartupManagedReadyFactoryPorts


def create_startup_support_graph(
    *,
    initial_splash: LaunchSplashClient | None,
) -> StartupSupportGraph:
    """Create startup support state and adapter bundles for the facade."""

    startup_splash_ports = create_startup_splash_ports()
    return StartupSupportGraph(
        ready_shell_state=create_ready_shell_state_bundle(
            initial_splash=initial_splash
        ),
        shell_reload_state=create_startup_shell_reload_state(),
        startup_splash_ports=startup_splash_ports,
        startup_cancel_bridge=startup_splash_ports.create_cancel_bridge(),
        startup_cancellation_state=create_startup_cancellation_state(),
        startup_qt_schedulers=create_startup_qt_scheduler_ports(),
        shell_ports=create_startup_shell_composition_ports(),
        managed_ready_ports=create_startup_managed_ready_factory_ports(),
    )


__all__ = [
    "StartupSupportGraph",
    "create_startup_support_graph",
]
