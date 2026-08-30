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

"""Provide the standard Comfy environment backend test double."""

from __future__ import annotations

from substitute.domain.comfy_environment import (
    ComfyEnvironmentAvailability,
    ComfyEnvironmentCapabilities,
    ComfyEnvironmentComponent,
    ComfyEnvironmentJob,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyEnvironmentStatus,
    ComfyHostStatus,
    ComfyMaintenancePlan,
    ComfyPythonStatus,
)
from tests.presentation.settings.comfy_environment.builders import (
    environment_package,
    maintenance_plan,
    management_tag,
    operation_plan,
    package_claimant,
    plan_item,
)


class EnvironmentBackend:
    """Environment backend test double for Settings widgets."""

    def __init__(
        self,
        *,
        planning_supported: bool = True,
        plan_blocked: bool = True,
    ) -> None:
        """Configure environment management capabilities."""

        self._planning_supported = planning_supported
        self._plan_blocked = plan_blocked
        self.maintenance_plan = maintenance_plan(blocked=plan_blocked)
        self.reorder_requests: list[tuple[int, tuple[str, ...]]] = []

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities:
        """Return restart-capable environment management."""

        return ComfyEnvironmentCapabilities(
            schema_version=1,
            supported_features=(
                "restart",
                *(("operation-planning",) if self._planning_supported else ()),
            ),
            restart_supported=True,
            package_mutation_supported=not self._plan_blocked,
            operation_planning_supported=self._planning_supported,
        )

    def get_environment_status(self) -> ComfyEnvironmentStatus:
        """Return one current environment status."""

        return ComfyEnvironmentStatus(
            schema_version=1,
            python=ComfyPythonStatus(
                executable="E:\\ComfyUI\\venv\\Scripts\\python.exe",
                version="3.12.7",
                prefix="E:\\ComfyUI\\venv",
                base_prefix="C:\\Python312",
                is_virtual_environment=True,
            ),
            comfy=ComfyHostStatus(
                root="E:\\ComfyUI",
                process_id=1234,
                restart_supported=True,
            ),
            environment=ComfyEnvironmentAvailability(
                inventory_available=True,
                mutation_available=False,
            ),
        )

    def restart_comfy(self) -> None:
        """Return no restart job because this test does not click restart."""

        return None

    def get_environment_job(self, _job_id: str) -> None:
        """Return no job because this test does not poll restart."""

        return None

    def plan_operation(
        self,
        request: dict[str, object],
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return one operation plan for Settings tests."""

        operation = str(request["operation"])
        if operation == "update-component":
            return operation_plan(
                "update-component", ("torch", "torchvision", "torchaudio")
            )
        return operation_plan(operation, (str(request["packageName"]),))

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return installed packages for the package-first inventory."""

        return (
            environment_package(
                name="torch",
                version="2.8.0",
                summary="Tensors and dynamic neural networks in Python.",
                summary_source="installed-metadata",
                attribution="supported",
                tags=(management_tag("pytorch", "PyTorch"),),
            ),
            environment_package(
                name="torchvision",
                version="0.23.0",
                summary="Image and video datasets and models for torch.",
                summary_source="installed-metadata",
                attribution="supported",
                tags=(management_tag("pytorch", "PyTorch"),),
            ),
            environment_package(
                name="torchaudio",
                version="2.8.0",
                summary=None,
                summary_source="unavailable",
                attribution="supported",
                tags=(management_tag("pytorch", "PyTorch"),),
            ),
            environment_package(
                name="triton",
                version="3.4.0",
                summary="A language and compiler for custom deep learning operations.",
                summary_source="pypi",
                attribution="supported",
                tags=(management_tag("triton", "Triton"),),
            ),
            environment_package(
                name="sageattention",
                version="2.2.0",
                summary=None,
                summary_source="unavailable",
                attribution="supported",
                tags=(management_tag("sageattention", "SageAttention"),),
            ),
            environment_package(
                name="custom-node-helper",
                version="1.4.0",
                summary="Helper package from installed metadata.",
                summary_source="installed-metadata",
                attribution="custom-node",
                claimants=(
                    package_claimant("ComfyUI-VFI", "custom-node-helper>=1.0"),
                    package_claimant(
                        "ComfyUI-Manager",
                        "base-helper",
                        required_via="base-helper",
                    ),
                    package_claimant(
                        "ComfyUI-EyeCandy",
                        "base-helper",
                        required_via="base-helper",
                    ),
                ),
            ),
            environment_package(
                name="manual-tool",
                version="0.9.1",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
        )

    def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
        """Return no components because Settings renders packages as primary."""

        return ()

    def get_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Return the current maintenance plan."""

        return self.maintenance_plan

    def add_maintenance_plan_item(
        self,
        request: dict[str, object],
    ) -> ComfyMaintenancePlan:
        """Add one fake item to the maintenance plan."""

        operation = str(request["operation"])
        if operation == "update-runtime":
            self.maintenance_plan = maintenance_plan(
                items=(
                    plan_item(
                        item_id="plan-item-1",
                        title="Update PyTorch runtime",
                        operation="update-runtime",
                        affected=("torch", "torchvision", "torchaudio"),
                        target_kind="runtime-family",
                        target_id="pytorch",
                        target_display="PyTorch runtime",
                    ),
                    plan_item(
                        item_id="plan-item-2",
                        title="Reinstall Triton",
                        operation="reinstall-package",
                        affected=("triton",),
                        install_requirements=("triton-windows",),
                        generated=True,
                        generated_by_item_id="plan-item-1",
                        can_remove=False,
                        can_reorder=False,
                    ),
                    plan_item(
                        item_id="plan-item-3",
                        title="Reinstall SageAttention",
                        operation="reinstall-package",
                        affected=("sageattention",),
                        generated=True,
                        generated_by_item_id="plan-item-1",
                        can_remove=False,
                        can_reorder=False,
                    ),
                ),
                revision=self.maintenance_plan.revision + 1,
                message="Planned item added with required compatibility follow-ups.",
                blocked=self._plan_blocked,
            )
        else:
            package_name = str(request["packageName"])
            operation_title = (
                "Uninstall" if operation == "uninstall-package" else "Update"
            )
            self.maintenance_plan = maintenance_plan(
                items=(
                    *self.maintenance_plan.items,
                    plan_item(
                        item_id=f"plan-item-{len(self.maintenance_plan.items) + 1}",
                        title=f"{operation_title} {package_name}",
                        operation=operation,
                        affected=(package_name,),
                    ),
                ),
                revision=self.maintenance_plan.revision + 1,
                message="Planned item added.",
                blocked=self._plan_blocked,
            )
        return self.maintenance_plan

    def remove_maintenance_plan_item(self, item_id: str) -> ComfyMaintenancePlan:
        """Remove one fake item from the maintenance plan."""

        self.maintenance_plan = maintenance_plan(
            items=tuple(
                item
                for item in self.maintenance_plan.items
                if item.item_id != item_id and item.generated_by_item_id != item_id
            ),
            revision=self.maintenance_plan.revision + 1,
            message="Planned item removed.",
            blocked=self._plan_blocked,
        )
        return self.maintenance_plan

    def reorder_maintenance_plan_items(
        self,
        *,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> ComfyMaintenancePlan:
        """Record and normalize a fake reorder request."""

        self.reorder_requests.append((revision, item_ids))
        by_id = {item.item_id: item for item in self.maintenance_plan.items}
        ordered = tuple(by_id[item_id] for item_id in item_ids if item_id in by_id)
        if ordered and ordered[0].generated:
            ordered = (
                by_id["plan-item-1"],
                *(item for item in ordered if item.item_id != "plan-item-1"),
            )
        self.maintenance_plan = maintenance_plan(
            items=ordered,
            revision=self.maintenance_plan.revision + 1,
            message="Order adjusted because compatibility follow-ups must run after their parent.",
            blocked=self._plan_blocked,
        )
        return self.maintenance_plan

    def clear_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Clear the fake maintenance plan."""

        self.maintenance_plan = maintenance_plan(
            revision=self.maintenance_plan.revision + 1,
            message="Planned changes cleared.",
            blocked=self._plan_blocked,
        )
        return self.maintenance_plan

    def validate_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Return the current fake maintenance plan."""

        return self.maintenance_plan

    def apply_maintenance_plan(self, *, revision: int) -> ComfyEnvironmentJob | None:
        """Return no apply job because fake plans are blocked."""

        _ = revision
        return None
