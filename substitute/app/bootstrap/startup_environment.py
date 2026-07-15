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

"""Prepare installation context and readiness state for startup routing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from typing import Protocol

from substitute.app.bootstrap.installation_context import (
    build_startup_readiness_service_bundle,
    create_default_installation_context,
    load_persisted_installation_context,
    resolve_installation_root,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.application.onboarding.installation_layout_migration_service import (
    ManagedWorkspaceLayoutMigrationService,
)
from substitute.domain.onboarding import InstallationContext, ReadinessAssessment
from substitute.infrastructure.comfy.managed_workspace_operations import (
    migrate_nested_workspace_layout,
)


class StartupReadinessServiceProtocol(Protocol):
    """Assess startup readiness for route selection."""

    def assess(self) -> ReadinessAssessment:
        """Return the current startup route assessment."""


class StartupReadinessServiceBundleProtocol(Protocol):
    """Expose the readiness service needed before startup routing."""

    @property
    def readiness_service(self) -> StartupReadinessServiceProtocol:
        """Return a service with an `assess()` readiness method."""


@dataclass(frozen=True)
class StartupEnvironment:
    """Resolved install environment required before route-specific startup."""

    install_root: Path
    service_bundle: StartupReadinessServiceBundleProtocol
    readiness_assessment: ReadinessAssessment
    installation_context: InstallationContext


def prepare_startup_environment(
    *,
    explicit_install_root: Path | None,
    startup_timer: StartupTimer,
    resolve_root: Callable[[Path | None], Path] = resolve_installation_root,
    load_persisted_context: Callable[
        [Path | None], InstallationContext | None
    ] = load_persisted_installation_context,
    build_service_bundle: Callable[
        [Path | None], StartupReadinessServiceBundleProtocol
    ] = build_startup_readiness_service_bundle,
    create_default_context: Callable[
        [Path | None], InstallationContext
    ] = create_default_installation_context,
    migrate_managed_workspace_layout: Callable[
        [Path], bool
    ] = migrate_nested_workspace_layout,
) -> StartupEnvironment:
    """Resolve install context, migrate managed workspace layout, and assess route."""

    with startup_timer.phase("startup.resolve_installation_root"):
        install_root = resolve_root(explicit_install_root)
    trace_mark("startup.install_root.resolved", install_root=install_root)

    with startup_timer.phase("startup.load_persisted_context"):
        persisted_context = load_persisted_context(install_root)
    trace_mark(
        "startup.persisted_context.loaded",
        persisted_context_present=persisted_context is not None,
    )

    with startup_timer.phase("startup.migrate_managed_workspace_layout"):
        ManagedWorkspaceLayoutMigrationService(
            migrate_nested_workspace_layout=migrate_managed_workspace_layout
        ).migrate(persisted_context)

    with startup_timer.phase("startup.build_onboarding_service_bundle"):
        service_bundle = build_service_bundle(install_root)
    with startup_timer.phase("startup.assess_readiness"):
        readiness_assessment = service_bundle.readiness_service.assess()
    trace_mark("startup.readiness.assessed", route=readiness_assessment.route)

    with startup_timer.phase("startup.create_installation_context"):
        installation_context = persisted_context or create_default_context(install_root)

    return StartupEnvironment(
        install_root=install_root,
        service_bundle=service_bundle,
        readiness_assessment=readiness_assessment,
        installation_context=installation_context,
    )


__all__ = [
    "StartupEnvironment",
    "prepare_startup_environment",
]
