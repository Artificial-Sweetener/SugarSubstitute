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

"""Verify application fallback when environment capabilities are unavailable."""

from __future__ import annotations

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.domain.comfy_environment import (
    ComfyEnvironmentComponent,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyMaintenancePlan,
)


def test_environment_service_skips_status_when_capabilities_are_unavailable() -> None:
    """Environment service should not call status routes without capabilities."""

    class Backend:
        """Backend test double with unavailable capabilities."""

        status_calls = 0

        def get_environment_capabilities(self) -> None:
            """Return no capabilities."""

            return None

        def get_environment_status(self) -> None:
            """Track unexpected status calls."""

            self.status_calls += 1
            return None

        def restart_comfy(self) -> None:
            """Return no restart job."""

            return None

        def get_environment_job(self, _job_id: str) -> None:
            """Return no job."""

            return None

        def plan_operation(
            self,
            _request: dict[str, object],
        ) -> ComfyEnvironmentOperationPlan | None:
            """Return no operation plan."""

            return None

        def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
            """Return no packages."""

            return ()

        def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
            """Return no components."""

            return ()

        def get_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def add_maintenance_plan_item(
            self,
            _request: dict[str, object],
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def remove_maintenance_plan_item(
            self,
            _item_id: str,
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def reorder_maintenance_plan_items(
            self,
            *,
            revision: int,
            item_ids: tuple[str, ...],
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            _ = (revision, item_ids)
            return None

        def clear_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def validate_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def apply_maintenance_plan(
            self,
            *,
            revision: int,
        ) -> None:
            """Return no apply job."""

            _ = revision
            return None

    backend = Backend()
    snapshot = ComfyEnvironmentService(backend).load_snapshot()

    assert snapshot.backend_available is False
    assert backend.status_calls == 0
