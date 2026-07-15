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

"""Compose runtime compatibility checks for bootstrap readiness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    BackendCompatibilityService,
)
from substitute.application.runtime_mode import ApplicationRuntimeModeService
from substitute.domain.onboarding import ComfyTargetConfiguration


class RuntimeCompatibilityCheckerProtocol(Protocol):
    """Assess runtime compatibility for one Comfy target."""

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Return compatibility facts for the target."""


@dataclass(frozen=True)
class EndpointBackendCompatibilityChecker:
    """Assess BackEnd/SugarCubes compatibility for a target endpoint."""

    runtime_mode: ApplicationRuntimeModeService

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Return compatibility facts by reading the target capabilities route."""

        from substitute.infrastructure.external.substitute_backend_model_metadata_client import (
            SubstituteBackendModelMetadataClient,
        )

        return BackendCompatibilityService(
            capability_provider=SubstituteBackendModelMetadataClient(target.endpoint),
            runtime_mode=self.runtime_mode,
        ).assess()


class ManagedStartupCompatibilityAssessor:
    """Gate managed startup compatibility checks on live managed state."""

    def __init__(
        self,
        *,
        comfy_state: Callable[[], object | None],
        checker: RuntimeCompatibilityCheckerProtocol,
        target: ComfyTargetConfiguration,
    ) -> None:
        """Store the live managed state getter and compatibility checker."""

        self._comfy_state = comfy_state
        self._checker = checker
        self._target = target

    def assess(self) -> BackendCompatibilityResult | None:
        """Assess compatibility only after managed Comfy has been launched."""

        if self._comfy_state() is None:
            return None
        return self._checker.assess_target(self._target)


def create_managed_startup_compatibility_assessor(
    *,
    comfy_state: Callable[[], object | None],
    checker: RuntimeCompatibilityCheckerProtocol,
    target: ComfyTargetConfiguration,
) -> ManagedStartupCompatibilityAssessor:
    """Create the managed startup runtime compatibility assessor."""

    return ManagedStartupCompatibilityAssessor(
        comfy_state=comfy_state,
        checker=checker,
        target=target,
    )


def create_endpoint_backend_compatibility_checker() -> (
    EndpointBackendCompatibilityChecker
):
    """Create the endpoint compatibility checker for the current runtime mode."""

    return EndpointBackendCompatibilityChecker(
        ApplicationRuntimeModeService.from_environment()
    )


__all__ = [
    "EndpointBackendCompatibilityChecker",
    "ManagedStartupCompatibilityAssessor",
    "RuntimeCompatibilityCheckerProtocol",
    "create_endpoint_backend_compatibility_checker",
    "create_managed_startup_compatibility_assessor",
]
