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

"""Build deterministic Comfy environment contract values."""

from __future__ import annotations

from substitute.domain.comfy_environment import (
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyMaintenanceExecutionPhase,
    ComfyMaintenancePlan,
    ComfyMaintenancePlanIssue,
    ComfyMaintenancePlanItem,
    ComfyMaintenancePlanRequest,
    ComfyMaintenancePlanSummary,
    ComfyMaintenancePlanTarget,
    ComfyPackageClaimant,
    ComfyPackageManagementTag,
)


def environment_package(
    *,
    name: str,
    version: str,
    summary: str | None,
    summary_source: str,
    attribution: str,
    claimants: tuple[ComfyPackageClaimant, ...] = (),
    tags: tuple[ComfyPackageManagementTag, ...] = (),
) -> ComfyEnvironmentPackage:
    """Return one package DTO for Settings tests."""

    return ComfyEnvironmentPackage(
        name=name,
        normalized_name=name.lower(),
        version=version,
        claimants=claimants,
        management_tags=tags,
        attribution=attribution,
        summary=summary,
        summary_source=summary_source,
        installer="pip",
    )


def package_claimant(
    name: str,
    requirement: str,
    *,
    required_via: str | None = None,
) -> ComfyPackageClaimant:
    """Return one custom-node claimant for Settings tests."""

    return ComfyPackageClaimant(
        kind="custom-node",
        claimant_id=name,
        display_name=name,
        requirement=requirement,
        source_path=f"E:\\ComfyUI\\custom_nodes\\{name}\\requirements.txt",
        required_via=required_via,
    )


def management_tag(tag_id: str, display_name: str) -> ComfyPackageManagementTag:
    """Return one supported management tag for Settings tests."""

    return ComfyPackageManagementTag(
        kind="supported-runtime",
        tag_id=tag_id,
        display_name=display_name,
        supported_actions=("plan-update",),
    )


def operation_plan(
    operation: str,
    affected_packages: tuple[str, ...],
) -> ComfyEnvironmentOperationPlan:
    """Return one operation plan for Settings tests."""

    return ComfyEnvironmentOperationPlan(
        plan_id="envplan-1",
        operation=operation,
        affected_packages=affected_packages,
        summary=f"Plan {operation}.",
        warnings=("Review before applying.",),
        requires_comfy_stop=True,
        requires_restart=True,
        requires_detached_runner=True,
    )


def maintenance_plan(
    *,
    items: tuple[ComfyMaintenancePlanItem, ...] = (),
    revision: int = 0,
    message: str | None = None,
    blocked: bool = True,
) -> ComfyMaintenancePlan:
    """Return a maintenance plan for Settings tests."""

    blockers = (
        (
            ComfyMaintenancePlanIssue(
                code="package-mutation-unavailable",
                message="Package execution is not available.",
            ),
        )
        if items and blocked
        else ()
    )
    affected_packages = {
        package for item in items for package in item.affected_packages
    }
    return ComfyMaintenancePlan(
        schema_version=1,
        plan_id="current",
        environment_id="E:\\ComfyUI",
        revision=revision,
        items=items,
        execution_phases=(
            (
                ComfyMaintenanceExecutionPhase(
                    phase_id="phase-1",
                    title="Package maintenance",
                    item_ids=tuple(item.item_id for item in items),
                    requires_comfy_stop=True,
                    requires_comfy_restart=True,
                ),
            )
            if items
            else ()
        ),
        warnings=tuple(warning for item in items for warning in item.warnings),
        blockers=blockers,
        summary=ComfyMaintenancePlanSummary(
            item_count=len(items),
            affected_package_count=len(affected_packages),
            requires_comfy_stop=bool(items),
            requires_comfy_restart=bool(items),
            applyable=bool(items) and not blockers,
        ),
        last_validation_message=message,
    )


def plan_item(
    *,
    item_id: str,
    title: str,
    operation: str,
    affected: tuple[str, ...],
    target_kind: str = "package",
    target_id: str | None = None,
    target_display: str | None = None,
    install_requirements: tuple[str, ...] | None = None,
    generated: bool = False,
    generated_by_item_id: str | None = None,
    can_remove: bool = True,
    can_reorder: bool = True,
) -> ComfyMaintenancePlanItem:
    """Return a maintenance plan item for Settings tests."""

    target = target_id or affected[0]
    return ComfyMaintenancePlanItem(
        item_id=item_id,
        operation=operation,
        title=title,
        target=ComfyMaintenancePlanTarget(
            kind=target_kind,
            target_id=target,
            display_name=target_display or target,
        ),
        requested=ComfyMaintenancePlanRequest(
            source="backend-policy" if generated else "user",
            package_name=target,
        ),
        generated=generated,
        generated_by_item_id=generated_by_item_id,
        relationship=(
            "required-compatibility-follow-up" if generated else "user-requested"
        ),
        affected_packages=affected,
        install_requirements=install_requirements or affected,
        requires_comfy_stop=True,
        requires_comfy_restart=True,
        locked_relative_order=generated,
        can_remove=can_remove,
        can_reorder=can_reorder,
        warnings=(
            (
                ComfyMaintenancePlanIssue(
                    code="runtime-compatibility",
                    message="Required by PyTorch update.",
                    item_id=item_id,
                ),
            )
            if generated
            else ()
        ),
        blockers=(),
    )
