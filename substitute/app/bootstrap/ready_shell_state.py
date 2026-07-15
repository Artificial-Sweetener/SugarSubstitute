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

"""Track readiness gates for showing the preloaded shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from substitute.app.bootstrap.launch_splash import LaunchSplashClient
    from substitute.app.bootstrap.startup_model_metadata import (
        ModelMetadataUpdateSignalBridgeProtocol,
    )


@dataclass
class ReadyShellStartupState:
    """Track readiness gates for showing the preloaded shell."""

    comfy_activation_started: bool = False
    minimum_shell_ready: bool = False
    comfy_http_ready: bool = False
    main_window_shown: bool = False
    prehydration_attempted: bool = False
    prehydration_succeeded: bool = False
    hydration_started: bool = False


@dataclass
class ReadyShellRuntimeState:
    """Track ready-shell runtime references shared by startup controllers."""

    comfy_state: object | None = None
    metadata_update_bridge: ModelMetadataUpdateSignalBridgeProtocol | None = None

    def set_comfy_state(self, state: object | None) -> None:
        """Store the managed Comfy state produced during startup."""

        self.comfy_state = state

    def set_metadata_update_bridge(
        self,
        bridge: ModelMetadataUpdateSignalBridgeProtocol | None,
    ) -> None:
        """Store the model metadata bridge kept alive for warmups."""

        self.metadata_update_bridge = bridge


@dataclass
class ReadyShellReferenceState:
    """Track live ready-shell references shared by startup adapters."""

    splash: LaunchSplashClient | None = None
    hidden_restore_runtime_prepared: bool = False

    def set_splash(self, splash: object | None) -> None:
        """Store the active launch splash reference."""

        self.splash = cast("LaunchSplashClient | None", splash)

    def set_hidden_restore_runtime_prepared(self, prepared: bool) -> None:
        """Store whether hidden restore runtime preparation succeeded."""

        self.hidden_restore_runtime_prepared = prepared


@dataclass
class ReadyShellStateBundle:
    """Group ready-shell state objects owned by the bootstrap state module."""

    reference_state: ReadyShellReferenceState
    runtime_state: ReadyShellRuntimeState


def create_ready_shell_state_bundle(
    *,
    initial_splash: LaunchSplashClient | None = None,
) -> ReadyShellStateBundle:
    """Create the ready-shell state objects used by startup orchestration."""

    return ReadyShellStateBundle(
        reference_state=ReadyShellReferenceState(splash=initial_splash),
        runtime_state=ReadyShellRuntimeState(),
    )


__all__ = [
    "ReadyShellReferenceState",
    "ReadyShellRuntimeState",
    "ReadyShellStateBundle",
    "ReadyShellStartupState",
    "create_ready_shell_state_bundle",
]
