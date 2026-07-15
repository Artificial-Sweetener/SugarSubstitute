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

"""Own mutable state composition for managed ready-shell startup."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryControllerState,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBackendStateUpdater,
)
from substitute.app.bootstrap.ready_shell_state import ReadyShellStartupState
from substitute.app.bootstrap.startup_model_metadata import (
    StartupModelMetadataRefreshState,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessControllerState,
    StartupReadinessStarter,
)
from substitute.app.bootstrap.startup_warmup_controller import StartupWarmupState


@dataclass(slots=True)
class StartupManagedReadyStateBundle:
    """Group mutable managed-ready startup state under one bootstrap owner."""

    ready_state: ReadyShellStartupState
    model_metadata_refresh_state: StartupModelMetadataRefreshState
    startup_warmup_state: StartupWarmupState
    readiness_controller_state: StartupReadinessControllerState
    readiness_starter: StartupReadinessStarter
    backend_state_updater: ReadyShellBackendStateUpdater
    managed_compatibility_recovery_state: ManagedCompatibilityRecoveryControllerState
    pre_show_restore_projection_state: PreShowRestoreProjectionState


def create_startup_managed_ready_state_bundle() -> StartupManagedReadyStateBundle:
    """Create managed-ready startup state with each controller at defaults."""

    return StartupManagedReadyStateBundle(
        ready_state=ReadyShellStartupState(),
        model_metadata_refresh_state=StartupModelMetadataRefreshState(),
        startup_warmup_state=StartupWarmupState(),
        readiness_controller_state=StartupReadinessControllerState(),
        readiness_starter=StartupReadinessStarter(),
        backend_state_updater=ReadyShellBackendStateUpdater(),
        managed_compatibility_recovery_state=(
            ManagedCompatibilityRecoveryControllerState()
        ),
        pre_show_restore_projection_state=PreShowRestoreProjectionState(),
    )


__all__ = (
    "StartupManagedReadyStateBundle",
    "create_startup_managed_ready_state_bundle",
)
