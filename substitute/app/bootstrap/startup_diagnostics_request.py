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

"""Request startup diagnostics titlebar preparation with concrete resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.app.bootstrap.startup_diagnostics_presenter import (
    PreparedDiagnosticsBridgeProtocol,
    request_startup_diagnostics_titlebar_preparation,
    startup_extension_metadata_providers,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_signal_bridges import (
    StartupDiagnosticsTitlebarBridge,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.application.execution import TaskSubmitter
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext


class StartupDiagnosticsSubmitterResource:
    """Close a diagnostics execution submitter during startup cleanup."""

    def __init__(self, submitter: TaskSubmitter) -> None:
        """Store the submitter whose dispatcher route must be released."""

        self._submitter = submitter

    def shutdown(self) -> None:
        """Close the runtime submitter when it exposes a close hook."""

        close = getattr(self._submitter, "close", None)
        if callable(close):
            close()


def request_startup_diagnostics_titlebar_update(
    *,
    main_window: object,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignore_repository: StartupDiagnosticsIgnoreRepository,
    installation_context: InstallationContext,
    startup_resources: StartupResourceRegistry,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
    startup_cancelled: Callable[[], bool],
    shell_frame_available: Callable[[], bool],
) -> bool:
    """Request async startup diagnostics titlebar preparation for one shell."""

    return request_startup_diagnostics_titlebar_preparation(
        main_window=main_window,
        incidents=incidents,
        transcript=transcript,
        ignore_repository=ignore_repository,
        metadata_providers=startup_extension_metadata_providers(installation_context),
        bridge_factory=create_startup_diagnostics_bridge,
        register_bridge=lambda bridge: register_startup_diagnostics_bridge(
            startup_resources,
            bridge,
        ),
        submitter_factory=lambda: create_startup_diagnostics_submitter(
            execution_runtime=execution_runtime,
            execution_dispatcher_factory=execution_dispatcher_factory,
        ),
        register_submitter=lambda submitter: register_startup_diagnostics_submitter(
            startup_resources,
            submitter,
        ),
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
    )


def create_startup_diagnostics_bridge() -> PreparedDiagnosticsBridgeProtocol:
    """Create the Qt bridge for diagnostics titlebar preparation."""

    return cast(
        PreparedDiagnosticsBridgeProtocol,
        StartupDiagnosticsTitlebarBridge(),
    )


def register_startup_diagnostics_bridge(
    startup_resources: StartupResourceRegistry,
    bridge: PreparedDiagnosticsBridgeProtocol,
) -> None:
    """Register one diagnostics bridge for startup lifetime cleanup."""

    startup_resources.register_startup_diagnostics_bridge(
        cast(StartupDiagnosticsTitlebarBridge, bridge)
    )


def create_startup_diagnostics_submitter(
    *,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
) -> TaskSubmitter:
    """Create the startup-lane submitter for diagnostics titlebar preparation."""

    return cast(
        TaskSubmitter,
        cast(Any, execution_runtime).submitter(
            "startup",
            owner_id="startup_diagnostics_titlebar",
            dispatcher=execution_dispatcher_factory(),
        ),
    )


def register_startup_diagnostics_submitter(
    startup_resources: StartupResourceRegistry,
    submitter: TaskSubmitter,
) -> None:
    """Register one diagnostics submitter for startup cleanup."""

    startup_resources.register_startup_diagnostics_task(
        StartupDiagnosticsSubmitterResource(submitter)
    )


__all__ = [
    "create_startup_diagnostics_bridge",
    "create_startup_diagnostics_submitter",
    "register_startup_diagnostics_bridge",
    "register_startup_diagnostics_submitter",
    "request_startup_diagnostics_titlebar_update",
    "StartupDiagnosticsSubmitterResource",
]
