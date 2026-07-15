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

"""Domain models for Comfy Python environment management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComfyEnvironmentJobStatus(StrEnum):
    """Identify lifecycle state for Comfy environment jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_RESTART = "waiting-for-restart"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ComfyEnvironmentCapabilities:
    """Describe BackEnd support for Comfy environment management."""

    schema_version: int
    supported_features: tuple[str, ...]
    restart_supported: bool
    package_mutation_supported: bool
    operation_planning_supported: bool
    restart_unavailable_reason: str | None = None


@dataclass(frozen=True)
class ComfyPythonStatus:
    """Describe the Python interpreter running the selected Comfy server."""

    executable: str
    version: str
    prefix: str
    base_prefix: str
    is_virtual_environment: bool


@dataclass(frozen=True)
class ComfyHostStatus:
    """Describe selected Comfy process facts relevant to environment operations."""

    root: str
    process_id: int
    restart_supported: bool


@dataclass(frozen=True)
class ComfyEnvironmentAvailability:
    """Describe available environment management surfaces."""

    inventory_available: bool
    mutation_available: bool


@dataclass(frozen=True)
class ComfyEnvironmentStatus:
    """Describe the selected Comfy Python environment."""

    schema_version: int
    python: ComfyPythonStatus
    comfy: ComfyHostStatus
    environment: ComfyEnvironmentAvailability


@dataclass(frozen=True)
class ComfyEnvironmentJobEvent:
    """Describe one user-visible environment job event."""

    created_at: str
    status: ComfyEnvironmentJobStatus
    message: str


@dataclass(frozen=True)
class ComfyEnvironmentJob:
    """Describe one BackEnd environment management job."""

    job_id: str
    operation: str
    status: ComfyEnvironmentJobStatus
    created_at: str
    updated_at: str
    message: str
    host_process_id: int
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    events: tuple[ComfyEnvironmentJobEvent, ...] = ()


@dataclass(frozen=True)
class ComfyEnvironmentOperationPlan:
    """Describe a backend-reviewed package operation plan."""

    plan_id: str
    operation: str
    affected_packages: tuple[str, ...]
    summary: str
    warnings: tuple[str, ...]
    requires_comfy_stop: bool
    requires_restart: bool
    requires_detached_runner: bool
    display_commands: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class ComfyMaintenancePlanTarget:
    """Describe the primary target for one planned maintenance item."""

    kind: str
    target_id: str
    display_name: str


@dataclass(frozen=True)
class ComfyMaintenancePlanRequest:
    """Describe who requested one planned maintenance item."""

    source: str
    package_name: str | None = None


@dataclass(frozen=True)
class ComfyMaintenancePlanIssue:
    """Describe one warning or blocker on a maintenance plan."""

    code: str
    message: str
    item_id: str | None = None


@dataclass(frozen=True)
class ComfyMaintenancePlanItem:
    """Describe one item in the editable maintenance queue."""

    item_id: str
    operation: str
    title: str
    target: ComfyMaintenancePlanTarget
    requested: ComfyMaintenancePlanRequest
    generated: bool
    relationship: str
    affected_packages: tuple[str, ...]
    install_requirements: tuple[str, ...]
    requires_comfy_stop: bool
    requires_comfy_restart: bool
    locked_relative_order: bool
    can_remove: bool
    can_reorder: bool
    generated_by_item_id: str | None = None
    warnings: tuple[ComfyMaintenancePlanIssue, ...] = ()
    blockers: tuple[ComfyMaintenancePlanIssue, ...] = ()


@dataclass(frozen=True)
class ComfyMaintenanceExecutionPhase:
    """Describe one backend-planned execution phase."""

    phase_id: str
    title: str
    item_ids: tuple[str, ...]
    requires_comfy_stop: bool
    requires_comfy_restart: bool


@dataclass(frozen=True)
class ComfyMaintenancePlanSummary:
    """Summarize whether a maintenance queue can be applied."""

    item_count: int
    affected_package_count: int
    requires_comfy_stop: bool
    requires_comfy_restart: bool
    applyable: bool


@dataclass(frozen=True)
class ComfyMaintenancePlan:
    """Describe the backend-owned maintenance queue for the selected Comfy."""

    schema_version: int
    plan_id: str
    environment_id: str
    revision: int
    items: tuple[ComfyMaintenancePlanItem, ...]
    execution_phases: tuple[ComfyMaintenanceExecutionPhase, ...]
    warnings: tuple[ComfyMaintenancePlanIssue, ...]
    blockers: tuple[ComfyMaintenancePlanIssue, ...]
    summary: ComfyMaintenancePlanSummary
    last_validation_message: str | None = None


@dataclass(frozen=True)
class ComfyPackageClaimant:
    """Describe one dependency claimant for a Python package."""

    kind: str
    claimant_id: str
    display_name: str
    requirement: str
    source_path: str
    required_via: str | None = None


@dataclass(frozen=True)
class ComfyPackageManagementTag:
    """Describe supported management behavior for a Python package."""

    kind: str
    tag_id: str
    display_name: str
    supported_actions: tuple[str, ...]


@dataclass(frozen=True)
class ComfyEnvironmentPackage:
    """Describe one installed Python package in the selected Comfy environment."""

    name: str
    normalized_name: str
    version: str
    claimants: tuple[ComfyPackageClaimant, ...]
    management_tags: tuple[ComfyPackageManagementTag, ...]
    attribution: str
    summary: str | None = None
    summary_source: str = "unavailable"
    location: str | None = None
    installer: str | None = None
    editable: bool = False


@dataclass(frozen=True)
class ComfyEnvironmentComponent:
    """Describe one UI-friendly environment component."""

    component_id: str
    display_name: str
    kind: str
    status: str
    packages: tuple[str, ...]
    summary: str | None = None
    installed_version: str | None = None
    available_version: str | None = None
    actions: tuple[str, ...] = ()
