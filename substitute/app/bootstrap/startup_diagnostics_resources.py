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

"""Create concrete startup diagnostics resources for ready-shell startup."""

from __future__ import annotations

from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.onboarding import InstallationContext
from substitute.infrastructure.persistence import FileStartupDiagnosticsIgnoreRepository


def create_startup_diagnostics_collector() -> ComfyStartupDiagnosticsCollector:
    """Create the collector used for managed startup diagnostics."""

    return ComfyStartupDiagnosticsCollector()


def create_startup_diagnostics_ignore_repository(
    context: InstallationContext,
) -> StartupDiagnosticsIgnoreRepository:
    """Create the ignore repository for one installation context."""

    return FileStartupDiagnosticsIgnoreRepository(context.diagnostics_dir)


__all__ = [
    "create_startup_diagnostics_collector",
    "create_startup_diagnostics_ignore_repository",
]
