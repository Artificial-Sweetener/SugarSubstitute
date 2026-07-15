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

"""Application orchestration for Comfy Python environment management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.domain.comfy_environment import (
    ComfyEnvironmentCapabilities,
    ComfyEnvironmentComponent,
    ComfyEnvironmentJob,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyEnvironmentStatus,
    ComfyMaintenancePlan,
)


class ComfyEnvironmentBackend(Protocol):
    """Backend port for selected Comfy environment management routes."""

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities | None:
        """Return environment management capabilities or ``None`` when unavailable."""

    def get_environment_status(self) -> ComfyEnvironmentStatus | None:
        """Return current environment status or ``None`` when unavailable."""

    def restart_comfy(self) -> ComfyEnvironmentJob | None:
        """Request a Comfy restart job or ``None`` when unavailable."""

    def get_environment_job(self, job_id: str) -> ComfyEnvironmentJob | None:
        """Return one environment job or ``None`` when unavailable."""

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return installed packages visible to the BackEnd plugin."""

    def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
        """Return UI-friendly installed components."""

    def plan_operation(
        self,
        request: dict[str, object],
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return a reviewable operation plan or ``None`` when unavailable."""

    def get_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Return the current maintenance plan or ``None`` when unavailable."""

    def add_maintenance_plan_item(
        self,
        request: dict[str, object],
    ) -> ComfyMaintenancePlan | None:
        """Add one maintenance plan item or return ``None`` when unavailable."""

    def remove_maintenance_plan_item(self, item_id: str) -> ComfyMaintenancePlan | None:
        """Remove one maintenance plan item or return ``None`` when unavailable."""

    def reorder_maintenance_plan_items(
        self,
        *,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> ComfyMaintenancePlan | None:
        """Send a proposed maintenance plan order."""

    def clear_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Clear the maintenance plan or return ``None`` when unavailable."""

    def validate_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Validate the maintenance plan or return ``None`` when unavailable."""

    def apply_maintenance_plan(self, *, revision: int) -> ComfyEnvironmentJob | None:
        """Apply the maintenance plan or return ``None`` when unavailable."""


@dataclass(frozen=True)
class ComfyEnvironmentSnapshot:
    """Collect environment status needed by the Settings page."""

    capabilities: ComfyEnvironmentCapabilities | None
    status: ComfyEnvironmentStatus | None
    packages: tuple[ComfyEnvironmentPackage, ...] = ()
    components: tuple[ComfyEnvironmentComponent, ...] = ()
    maintenance_plan: ComfyMaintenancePlan | None = None

    @property
    def backend_available(self) -> bool:
        """Return whether the selected endpoint exposes environment management."""

        return self.capabilities is not None


class ComfyEnvironmentService:
    """Coordinate environment management use cases for Settings."""

    def __init__(self, backend: ComfyEnvironmentBackend) -> None:
        """Initialize the service with a selected Comfy backend port."""

        self._backend = backend

    def load_snapshot(self) -> ComfyEnvironmentSnapshot:
        """Load capabilities and current environment status."""

        capabilities = self._backend.get_environment_capabilities()
        status = (
            self._backend.get_environment_status() if capabilities is not None else None
        )
        packages: tuple[ComfyEnvironmentPackage, ...] = ()
        maintenance_plan: ComfyMaintenancePlan | None = None
        if capabilities is not None:
            packages = self._backend.list_packages()
            maintenance_plan = self._backend.get_maintenance_plan()
        return ComfyEnvironmentSnapshot(
            capabilities=capabilities,
            status=status,
            packages=packages,
            maintenance_plan=maintenance_plan,
        )

    def restart_comfy(self) -> ComfyEnvironmentJob | None:
        """Request a Comfy restart through the selected BackEnd plugin."""

        return self._backend.restart_comfy()

    def get_job(self, job_id: str) -> ComfyEnvironmentJob | None:
        """Return current state for one environment job."""

        return self._backend.get_environment_job(job_id)

    def plan_package_update(
        self,
        package: ComfyEnvironmentPackage,
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return an update plan for one package or supported management tag."""

        tag = package.management_tags[0] if package.management_tags else None
        if tag is not None:
            return self._backend.plan_operation(
                {
                    "operation": "update-component",
                    "componentId": tag.tag_id,
                }
            )
        return self._backend.plan_operation(
            {
                "operation": "update-package",
                "packageName": package.name,
            }
        )

    def add_package_update_to_plan(
        self,
        package: ComfyEnvironmentPackage,
    ) -> ComfyMaintenancePlan | None:
        """Add an update action for one package or supported runtime."""

        tag = package.management_tags[0] if package.management_tags else None
        if tag is not None and tag.tag_id == "pytorch":
            return self._backend.add_maintenance_plan_item(
                {
                    "operation": "update-runtime",
                    "runtimeId": "pytorch",
                }
            )
        if tag is not None:
            return self._backend.add_maintenance_plan_item(
                {
                    "operation": "update-package",
                    "packageName": tag.tag_id,
                }
            )
        return self._backend.add_maintenance_plan_item(
            {
                "operation": "update-package",
                "packageName": package.name,
            }
        )

    def plan_package_uninstall(
        self,
        package: ComfyEnvironmentPackage,
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return an uninstall plan for one package."""

        return self._backend.plan_operation(
            {
                "operation": "uninstall-package",
                "packageName": package.name,
            }
        )

    def add_package_uninstall_to_plan(
        self,
        package: ComfyEnvironmentPackage,
    ) -> ComfyMaintenancePlan | None:
        """Add an uninstall action for one package."""

        return self._backend.add_maintenance_plan_item(
            {
                "operation": "uninstall-package",
                "packageName": package.name,
            }
        )

    def remove_plan_item(self, item_id: str) -> ComfyMaintenancePlan | None:
        """Remove one item from the maintenance plan."""

        return self._backend.remove_maintenance_plan_item(item_id)

    def reorder_plan_items(
        self,
        *,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> ComfyMaintenancePlan | None:
        """Send a proposed maintenance plan order."""

        return self._backend.reorder_maintenance_plan_items(
            revision=revision,
            item_ids=item_ids,
        )

    def clear_plan(self) -> ComfyMaintenancePlan | None:
        """Clear the current maintenance plan."""

        return self._backend.clear_maintenance_plan()

    def validate_plan(self) -> ComfyMaintenancePlan | None:
        """Validate the current maintenance plan."""

        return self._backend.validate_maintenance_plan()

    def apply_plan(self, *, revision: int) -> ComfyEnvironmentJob | None:
        """Apply the current maintenance plan."""

        return self._backend.apply_maintenance_plan(revision=revision)
