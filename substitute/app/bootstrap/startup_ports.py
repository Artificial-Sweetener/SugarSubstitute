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

"""Typed callable ports used by startup orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import ComfyTargetConfiguration, InstallationContext

if TYPE_CHECKING:
    from substitute.app.bootstrap.startup_model_metadata import (
        ModelMetadataUpdateSignalBridgeProtocol,
    )
else:
    ModelMetadataUpdateSignalBridgeProtocol = object


class StartupRuntimeCompatibilityCheckerProtocol(Protocol):
    """Assess runtime compatibility for one managed-ready startup target."""

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Return compatibility facts for the target."""


@dataclass(frozen=True)
class StartupShellCompositionPorts:
    """Group shell composition callables consumed by startup controllers."""

    build_main_window: Callable[..., object]
    show_main_window: Callable[..., object]
    show_built_main_window: Callable[..., object]
    main_window_for_shell: Callable[[object], object]
    build_model_metadata_refresh_service: Callable[[InstallationContext], object]
    is_comfy_http_ready: Callable[[str, int], bool]


@dataclass(frozen=True)
class StartupManagedReadyFactoryPorts:
    """Group concrete factory and adapter callables for managed-ready startup."""

    create_startup_diagnostics_collector: Callable[[], ComfyStartupDiagnosticsCollector]
    create_startup_diagnostics_ignore_repository: Callable[
        [InstallationContext], StartupDiagnosticsIgnoreRepository
    ]
    create_runtime_compatibility_checker: Callable[
        [], StartupRuntimeCompatibilityCheckerProtocol
    ]
    create_managed_compatibility_recovery_bridge: Callable[[], Any]
    create_model_metadata_update_bridge: Callable[
        [object], ModelMetadataUpdateSignalBridgeProtocol
    ]
    request_startup_diagnostics_titlebar_update: Callable[..., bool]
    activate_target: Callable[..., object | None]
    managed_startup_fatal_incident: Callable[
        [object | None], ComfyStartupIncident | None
    ]
    present_startup_failure_report: Callable[[Any], None]
    build_startup_failure_report: Callable[..., Any]
    build_startup_readiness_timeout_incident: Callable[..., ComfyStartupIncident]
    build_startup_runtime_compatibility_incident: Callable[..., ComfyStartupIncident]


__all__ = [
    "StartupManagedReadyFactoryPorts",
    "StartupRuntimeCompatibilityCheckerProtocol",
    "StartupShellCompositionPorts",
]
