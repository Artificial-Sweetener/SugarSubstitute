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

"""Provide specialized Comfy environment backend test doubles."""

from __future__ import annotations

from substitute.domain.comfy_environment import (
    ComfyEnvironmentCapabilities,
    ComfyEnvironmentJob,
    ComfyEnvironmentJobEvent,
    ComfyEnvironmentJobStatus,
    ComfyEnvironmentPackage,
)
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.builders import (
    environment_package,
    package_claimant,
)


class CountingEnvironmentBackend(EnvironmentBackend):
    """Environment backend that counts snapshot capability requests."""

    def __init__(self) -> None:
        """Create a counting backend with default environment data."""

        super().__init__()
        self.capability_requests = 0

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities:
        """Count capability requests before returning normal capabilities."""

        self.capability_requests += 1
        return super().get_environment_capabilities()


class ApplyEnvironmentBackend(EnvironmentBackend):
    """Backend test double that accepts plan apply."""

    def __init__(self) -> None:
        """Create an applyable backend."""

        super().__init__(plan_blocked=False)
        self.applied_revisions: list[int] = []

    def apply_maintenance_plan(
        self,
        *,
        revision: int,
    ) -> ComfyEnvironmentJob:
        """Return a queued maintenance job."""

        self.applied_revisions.append(revision)
        return ComfyEnvironmentJob(
            job_id="envjob-apply",
            operation="apply-maintenance-plan",
            status=ComfyEnvironmentJobStatus.QUEUED,
            created_at="2026-04-17T00:00:00Z",
            updated_at="2026-04-17T00:00:00Z",
            message="Maintenance plan queued for execution.",
            host_process_id=1234,
            events=(
                ComfyEnvironmentJobEvent(
                    created_at="2026-04-17T00:00:00Z",
                    status=ComfyEnvironmentJobStatus.QUEUED,
                    message="Maintenance plan queued for execution.",
                ),
            ),
        )


class SearchSortEnvironmentBackend(EnvironmentBackend):
    """Environment backend test double with targeted sort/search data."""

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return packages that separate name matches from claimant matches."""

        return (
            environment_package(
                name="beta-package",
                version="1.0.0",
                summary=None,
                summary_source="unavailable",
                attribution="custom-node",
                claimants=(
                    package_claimant("HelperNodeA", "beta-package"),
                    package_claimant("HelperNodeB", "beta-package"),
                    package_claimant("HelperNodeC", "beta-package"),
                ),
            ),
            environment_package(
                name="alpha-helper",
                version="0.1.0",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
            environment_package(
                name="gamma-tool",
                version="2.0.0",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
        )
