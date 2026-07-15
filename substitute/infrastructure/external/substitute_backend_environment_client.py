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

"""HTTP client for Substitute BackEnd environment management routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.domain.common import JsonObject
from substitute.domain.comfy_environment import (
    ComfyEnvironmentAvailability,
    ComfyEnvironmentCapabilities,
    ComfyEnvironmentComponent,
    ComfyEnvironmentJob,
    ComfyEnvironmentJobEvent,
    ComfyEnvironmentJobStatus,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyEnvironmentStatus,
    ComfyHostStatus,
    ComfyMaintenanceExecutionPhase,
    ComfyMaintenancePlan,
    ComfyMaintenancePlanIssue,
    ComfyMaintenancePlanItem,
    ComfyMaintenancePlanRequest,
    ComfyMaintenancePlanSummary,
    ComfyMaintenancePlanTarget,
    ComfyPackageClaimant,
    ComfyPackageManagementTag,
    ComfyPythonStatus,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_delete,
    default_http_get,
    default_http_post,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.external.substitute_backend_environment_client")
HttpGet = Callable[..., Any]
HttpPost = Callable[..., Any]
HttpDelete = Callable[..., Any]


class SubstituteBackendEnvironmentClient:
    """Query Substitute BackEnd environment management routes."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        http_post: HttpPost | None = None,
        http_delete: HttpDelete | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize the client with endpoint and injectable HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._http_delete = http_delete or default_http_delete
        self._timeout_seconds = timeout_seconds

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities | None:
        """Return environment management capabilities or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/environment/capabilities")
        if payload is None:
            return None
        try:
            return _parse_capabilities(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd environment capabilities payload",
                error=repr(error),
            )
            return None

    def get_environment_status(self) -> ComfyEnvironmentStatus | None:
        """Return current environment status or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/environment/status")
        if payload is None:
            return None
        try:
            return _parse_status(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd environment status payload",
                error=repr(error),
            )
            return None

    def restart_comfy(self) -> ComfyEnvironmentJob | None:
        """Request a Comfy restart job."""

        payload = self._post_json("/substitute/v1/environment/restart", {})
        if payload is None:
            return None
        try:
            return _parse_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd restart response",
                error=repr(error),
            )
            return None

    def get_environment_job(self, job_id: str) -> ComfyEnvironmentJob | None:
        """Return current state for one environment job."""

        payload = self._get_json(f"/substitute/v1/environment/jobs/{job_id}")
        if payload is None:
            return None
        try:
            return _parse_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd environment job response",
                error=repr(error),
            )
            return None

    def plan_operation(
        self,
        request: dict[str, object],
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return a backend-reviewed environment operation plan."""

        payload = self._post_json("/substitute/v1/environment/operations/plan", request)
        if payload is None:
            return None
        try:
            return _parse_operation_plan(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd operation plan response",
                error=repr(error),
            )
            return None

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return installed Python packages reported by Substitute BackEnd."""

        payload = self._get_json("/substitute/v1/environment/packages")
        if payload is None:
            return ()
        raw_packages = payload.get("packages")
        if not isinstance(raw_packages, list):
            log_warning(
                _LOGGER, "Invalid environment package payload: packages is not a list"
            )
            return ()
        packages: list[ComfyEnvironmentPackage] = []
        for raw_package in raw_packages:
            if not isinstance(raw_package, dict):
                continue
            try:
                packages.append(_parse_package(raw_package))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Skipped invalid environment package entry",
                    error=repr(error),
                )
        return tuple(packages)

    def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
        """Return UI-friendly environment components reported by Substitute BackEnd."""

        payload = self._get_json("/substitute/v1/environment/components")
        if payload is None:
            return ()
        raw_components = payload.get("components")
        if not isinstance(raw_components, list):
            log_warning(
                _LOGGER,
                "Invalid environment component payload: components is not a list",
            )
            return ()
        components: list[ComfyEnvironmentComponent] = []
        for raw_component in raw_components:
            if not isinstance(raw_component, dict):
                continue
            try:
                components.append(_parse_component(raw_component))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Skipped invalid environment component entry",
                    error=repr(error),
                )
        return tuple(components)

    def get_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Return the current backend-owned maintenance plan."""

        payload = self._get_json("/substitute/v1/environment/maintenance-plan")
        return _parse_optional_maintenance_plan(payload, "maintenance plan")

    def add_maintenance_plan_item(
        self,
        request: dict[str, object],
    ) -> ComfyMaintenancePlan | None:
        """Add one item to the backend-owned maintenance plan."""

        payload = self._post_json(
            "/substitute/v1/environment/maintenance-plan/items",
            request,
        )
        return _parse_optional_maintenance_plan(payload, "maintenance plan add")

    def remove_maintenance_plan_item(self, item_id: str) -> ComfyMaintenancePlan | None:
        """Remove one item from the backend-owned maintenance plan."""

        payload = self._delete_json(
            f"/substitute/v1/environment/maintenance-plan/items/{item_id}"
        )
        return _parse_optional_maintenance_plan(payload, "maintenance plan remove")

    def reorder_maintenance_plan_items(
        self,
        *,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> ComfyMaintenancePlan | None:
        """Send a proposed maintenance-plan item order."""

        payload = self._post_json(
            "/substitute/v1/environment/maintenance-plan/items/reorder",
            {
                "revision": revision,
                "itemIds": list(item_ids),
            },
        )
        return _parse_optional_maintenance_plan(payload, "maintenance plan reorder")

    def clear_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Clear the backend-owned maintenance plan."""

        payload = self._delete_json("/substitute/v1/environment/maintenance-plan")
        return _parse_optional_maintenance_plan(payload, "maintenance plan clear")

    def validate_maintenance_plan(self) -> ComfyMaintenancePlan | None:
        """Validate the backend-owned maintenance plan."""

        payload = self._post_json(
            "/substitute/v1/environment/maintenance-plan/validate",
            {},
        )
        return _parse_optional_maintenance_plan(payload, "maintenance plan validate")

    def apply_maintenance_plan(self, *, revision: int) -> ComfyEnvironmentJob | None:
        """Apply the backend-owned maintenance plan."""

        payload = self._post_json(
            "/substitute/v1/environment/maintenance-plan/apply",
            {"revision": revision},
        )
        if payload is None:
            return None
        try:
            return _parse_job(payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd maintenance plan apply response",
                error=repr(error),
            )
            return None

    def _get_json(self, path: str) -> JsonObject | None:
        """GET one backend route and return a JSON object on success."""

        try:
            response = self._http_get(self._url(path), timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment GET failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment GET returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _post_json(self, path: str, body: JsonObject) -> JsonObject | None:
        """POST one backend route and return a JSON object on success."""

        try:
            response = self._http_post(
                self._url(path),
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment POST failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment POST returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _delete_json(self, path: str) -> JsonObject | None:
        """DELETE one backend route and return a JSON object on success."""

        try:
            response = self._http_delete(
                self._url(path),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment DELETE failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd environment DELETE returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _url(self, path: str) -> str:
        """Return an HTTP URL rooted at the configured Comfy endpoint."""

        return f"http://{self._endpoint.host}:{self._endpoint.port}{path}"


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an HTTP operation failure should be converted to `None`."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _parse_capabilities(data: JsonObject) -> ComfyEnvironmentCapabilities:
    """Parse environment capability payload."""

    return ComfyEnvironmentCapabilities(
        schema_version=_required_int(data, "schemaVersion"),
        supported_features=_read_str_tuple(data, "supportedFeatures"),
        restart_supported=_read_bool(data, "restartSupported"),
        package_mutation_supported=_read_bool(data, "packageMutationSupported"),
        operation_planning_supported=_read_bool(data, "operationPlanningSupported"),
        restart_unavailable_reason=_read_str(data, "restartUnavailableReason"),
    )


def _parse_status(data: JsonObject) -> ComfyEnvironmentStatus:
    """Parse environment status payload."""

    python = _read_object(data, "python")
    comfy = _read_object(data, "comfy")
    environment = _read_object(data, "environment")
    return ComfyEnvironmentStatus(
        schema_version=_required_int(data, "schemaVersion"),
        python=ComfyPythonStatus(
            executable=_required_str(python, "executable"),
            version=_required_str(python, "version"),
            prefix=_required_str(python, "prefix"),
            base_prefix=_required_str(python, "basePrefix"),
            is_virtual_environment=_read_bool(python, "isVirtualEnvironment"),
        ),
        comfy=ComfyHostStatus(
            root=_required_str(comfy, "root"),
            process_id=_required_int(comfy, "processId"),
            restart_supported=_read_bool(comfy, "restartSupported"),
        ),
        environment=ComfyEnvironmentAvailability(
            inventory_available=_read_bool(environment, "inventoryAvailable"),
            mutation_available=_read_bool(environment, "mutationAvailable"),
        ),
    )


def _parse_job(data: JsonObject) -> ComfyEnvironmentJob:
    """Parse environment job payload."""

    raw_events = data.get("events")
    events: list[ComfyEnvironmentJobEvent] = []
    if isinstance(raw_events, list):
        for raw_event in raw_events:
            if isinstance(raw_event, dict):
                events.append(_parse_job_event(raw_event))
    return ComfyEnvironmentJob(
        job_id=_required_str(data, "jobId"),
        operation=_required_str(data, "operation"),
        status=_parse_job_status(_required_str(data, "status")),
        created_at=_required_str(data, "createdAt"),
        updated_at=_required_str(data, "updatedAt"),
        message=_required_str(data, "message"),
        host_process_id=_required_int(data, "hostProcessId"),
        started_at=_read_str(data, "startedAt"),
        completed_at=_read_str(data, "completedAt"),
        error=_read_str(data, "error"),
        events=tuple(events),
    )


def _parse_job_event(data: JsonObject) -> ComfyEnvironmentJobEvent:
    """Parse one environment job event payload."""

    return ComfyEnvironmentJobEvent(
        created_at=_required_str(data, "createdAt"),
        status=_parse_job_status(_required_str(data, "status")),
        message=_required_str(data, "message"),
    )


def _parse_operation_plan(data: JsonObject) -> ComfyEnvironmentOperationPlan:
    """Parse one operation plan payload."""

    return ComfyEnvironmentOperationPlan(
        plan_id=_required_str(data, "planId"),
        operation=_required_str(data, "operation"),
        affected_packages=_read_str_tuple(data, "affectedPackages"),
        summary=_required_str(data, "summary"),
        warnings=_read_str_tuple(data, "warnings"),
        requires_comfy_stop=_read_bool(data, "requiresComfyStop"),
        requires_restart=_read_bool(data, "requiresRestart"),
        requires_detached_runner=_read_bool(data, "requiresDetachedRunner"),
        display_commands=_parse_display_commands(data.get("displayCommands")),
    )


def _parse_optional_maintenance_plan(
    payload: JsonObject | None,
    operation: str,
) -> ComfyMaintenancePlan | None:
    """Parse an optional maintenance plan with operation-specific logging."""

    if payload is None:
        return None
    try:
        return _parse_maintenance_plan(payload)
    except ValueError as error:
        log_warning(
            _LOGGER,
            f"Invalid Substitute BackEnd {operation} response",
            error=repr(error),
        )
        return None


def _parse_maintenance_plan(data: JsonObject) -> ComfyMaintenancePlan:
    """Parse one maintenance plan payload."""

    return ComfyMaintenancePlan(
        schema_version=_required_int(data, "schemaVersion"),
        plan_id=_required_str(data, "planId"),
        environment_id=_required_str(data, "environmentId"),
        revision=_required_int(data, "revision"),
        items=_parse_plan_items(data.get("items")),
        execution_phases=_parse_execution_phases(data.get("executionPhases")),
        warnings=_parse_plan_issues(data.get("warnings")),
        blockers=_parse_plan_issues(data.get("blockers")),
        summary=_parse_plan_summary(_read_object(data, "summary")),
        last_validation_message=_read_str(data, "lastValidationMessage"),
    )


def _parse_plan_items(value: object) -> tuple[ComfyMaintenancePlanItem, ...]:
    """Parse maintenance plan item payloads."""

    if not isinstance(value, list):
        return ()
    items: list[ComfyMaintenancePlanItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        items.append(_parse_plan_item(raw_item))
    return tuple(items)


def _parse_plan_item(data: JsonObject) -> ComfyMaintenancePlanItem:
    """Parse one maintenance plan item payload."""

    return ComfyMaintenancePlanItem(
        item_id=_required_str(data, "itemId"),
        operation=_required_str(data, "operation"),
        title=_required_str(data, "title"),
        target=_parse_plan_target(_read_object(data, "target")),
        requested=_parse_plan_request(_read_object(data, "requested")),
        generated=_read_bool(data, "generated"),
        generated_by_item_id=_read_str(data, "generatedByItemId"),
        relationship=_required_str(data, "relationship"),
        affected_packages=_read_str_tuple(data, "affectedPackages"),
        install_requirements=_read_str_tuple(data, "installRequirements"),
        requires_comfy_stop=_read_bool(data, "requiresComfyStop"),
        requires_comfy_restart=_read_bool(data, "requiresComfyRestart"),
        locked_relative_order=_read_bool(data, "lockedRelativeOrder"),
        can_remove=_read_bool(data, "canRemove"),
        can_reorder=_read_bool(data, "canReorder"),
        warnings=_parse_plan_issues(data.get("warnings")),
        blockers=_parse_plan_issues(data.get("blockers")),
    )


def _parse_plan_target(data: JsonObject) -> ComfyMaintenancePlanTarget:
    """Parse one maintenance plan target payload."""

    return ComfyMaintenancePlanTarget(
        kind=_required_str(data, "kind"),
        target_id=_required_str(data, "id"),
        display_name=_required_str(data, "displayName"),
    )


def _parse_plan_request(data: JsonObject) -> ComfyMaintenancePlanRequest:
    """Parse one maintenance plan request payload."""

    return ComfyMaintenancePlanRequest(
        source=_required_str(data, "source"),
        package_name=_read_str(data, "packageName"),
    )


def _parse_plan_issues(value: object) -> tuple[ComfyMaintenancePlanIssue, ...]:
    """Parse maintenance plan warning or blocker payloads."""

    if not isinstance(value, list):
        return ()
    issues: list[ComfyMaintenancePlanIssue] = []
    for raw_issue in value:
        if not isinstance(raw_issue, dict):
            continue
        issues.append(
            ComfyMaintenancePlanIssue(
                code=_required_str(raw_issue, "code"),
                message=_required_str(raw_issue, "message"),
                item_id=_read_str(raw_issue, "itemId"),
            )
        )
    return tuple(issues)


def _parse_execution_phases(
    value: object,
) -> tuple[ComfyMaintenanceExecutionPhase, ...]:
    """Parse maintenance plan execution phase payloads."""

    if not isinstance(value, list):
        return ()
    phases: list[ComfyMaintenanceExecutionPhase] = []
    for raw_phase in value:
        if not isinstance(raw_phase, dict):
            continue
        phases.append(
            ComfyMaintenanceExecutionPhase(
                phase_id=_required_str(raw_phase, "phaseId"),
                title=_required_str(raw_phase, "title"),
                item_ids=_read_str_tuple(raw_phase, "itemIds"),
                requires_comfy_stop=_read_bool(raw_phase, "requiresComfyStop"),
                requires_comfy_restart=_read_bool(raw_phase, "requiresComfyRestart"),
            )
        )
    return tuple(phases)


def _parse_plan_summary(data: JsonObject) -> ComfyMaintenancePlanSummary:
    """Parse maintenance plan summary payload."""

    return ComfyMaintenancePlanSummary(
        item_count=_required_int(data, "itemCount"),
        affected_package_count=_required_int(data, "affectedPackageCount"),
        requires_comfy_stop=_read_bool(data, "requiresComfyStop"),
        requires_comfy_restart=_read_bool(data, "requiresComfyRestart"),
        applyable=_read_bool(data, "applyable"),
    )


def _parse_package(data: JsonObject) -> ComfyEnvironmentPackage:
    """Parse one environment package payload."""

    return ComfyEnvironmentPackage(
        name=_required_str(data, "name"),
        normalized_name=_required_str(data, "normalizedName"),
        version=_required_str(data, "version"),
        claimants=_parse_claimants(data.get("claimants")),
        management_tags=_parse_management_tags(data.get("managementTags")),
        attribution=_required_str(data, "attribution"),
        summary=_read_str(data, "summary"),
        summary_source=_required_str(data, "summarySource"),
        location=_read_str(data, "location"),
        installer=_read_str(data, "installer"),
        editable=_read_bool(data, "editable"),
    )


def _parse_component(data: JsonObject) -> ComfyEnvironmentComponent:
    """Parse one environment component payload."""

    return ComfyEnvironmentComponent(
        component_id=_required_str(data, "id"),
        display_name=_required_str(data, "displayName"),
        kind=_required_str(data, "kind"),
        status=_required_str(data, "status"),
        packages=_read_str_tuple(data, "packages"),
        summary=_read_str(data, "summary"),
        installed_version=_read_str(data, "installedVersion"),
        available_version=_read_str(data, "availableVersion"),
        actions=_read_str_tuple(data, "actions"),
    )


def _parse_claimants(value: object) -> tuple[ComfyPackageClaimant, ...]:
    """Parse package claimant payloads."""

    if not isinstance(value, list):
        return ()
    claimants: list[ComfyPackageClaimant] = []
    for raw_claimant in value:
        if not isinstance(raw_claimant, dict):
            continue
        claimants.append(
            ComfyPackageClaimant(
                kind=_required_str(raw_claimant, "kind"),
                claimant_id=_required_str(raw_claimant, "id"),
                display_name=_required_str(raw_claimant, "displayName"),
                requirement=_required_str(raw_claimant, "requirement"),
                source_path=_required_str(raw_claimant, "sourcePath"),
                required_via=_read_str(raw_claimant, "requiredVia"),
            )
        )
    return tuple(claimants)


def _parse_management_tags(value: object) -> tuple[ComfyPackageManagementTag, ...]:
    """Parse package management tag payloads."""

    if not isinstance(value, list):
        return ()
    tags: list[ComfyPackageManagementTag] = []
    for raw_tag in value:
        if not isinstance(raw_tag, dict):
            continue
        tags.append(
            ComfyPackageManagementTag(
                kind=_required_str(raw_tag, "kind"),
                tag_id=_required_str(raw_tag, "id"),
                display_name=_required_str(raw_tag, "displayName"),
                supported_actions=_read_str_tuple(raw_tag, "supportedActions"),
            )
        )
    return tuple(tags)


def _parse_display_commands(value: object) -> tuple[tuple[str, ...], ...]:
    """Parse display-only command argument lists."""

    if not isinstance(value, list):
        return ()
    commands: list[tuple[str, ...]] = []
    for raw_command in value:
        if not isinstance(raw_command, list):
            continue
        command = tuple(
            item for item in raw_command if isinstance(item, str) and item.strip()
        )
        if command:
            commands.append(command)
    return tuple(commands)


def _parse_job_status(value: str) -> ComfyEnvironmentJobStatus:
    """Parse an environment job status with a safe fallback."""

    try:
        return ComfyEnvironmentJobStatus(value)
    except ValueError:
        return ComfyEnvironmentJobStatus.FAILED


def _read_object(data: JsonObject, key: str) -> JsonObject:
    """Read a required JSON object field."""

    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_str(data: JsonObject, key: str) -> str:
    """Read a required string field."""

    value = _read_str(data, key)
    if value is None:
        raise ValueError(f"{key} must be a string")
    return value


def _read_str(data: JsonObject, key: str) -> str | None:
    """Read an optional string field."""

    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _required_int(data: JsonObject, key: str) -> int:
    """Read a required integer field."""

    value = _read_int(data, key)
    if value is None:
        raise ValueError(f"{key} must be an integer")
    return value


def _read_int(data: JsonObject, key: str) -> int | None:
    """Read an optional integer field."""

    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _read_bool(data: JsonObject, key: str) -> bool:
    """Read an optional boolean field with a false default."""

    value = data.get(key)
    return value if isinstance(value, bool) else False


def _read_str_tuple(data: JsonObject, key: str) -> tuple[str, ...]:
    """Read an optional list of strings as a tuple."""

    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


__all__ = ["SubstituteBackendEnvironmentClient"]
