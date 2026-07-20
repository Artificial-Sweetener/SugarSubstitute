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

"""Parse SugarCubes maintenance reports into startup diagnostics."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class SugarCubesMaintenanceDiagnostic:
    """Describe one SugarCubes maintenance diagnostic emitted during startup."""

    code: str
    severity: str
    title: ApplicationText
    message: ApplicationText
    details: Mapping[str, object]


@dataclass(frozen=True)
class SugarCubesMaintenanceResult:
    """Describe the parsed result of one SugarCubes maintenance command."""

    exit_code: int
    payload: Mapping[str, object]
    diagnostics: tuple[SugarCubesMaintenanceDiagnostic, ...]
    output_excerpt: tuple[str, ...]


def sugarcubes_maintenance_result(
    exit_code: int,
    output_lines: Sequence[str],
) -> SugarCubesMaintenanceResult:
    """Build a parsed SugarCubes maintenance result from streamed output."""

    payload = parse_sugarcubes_maintenance_payload(output_lines)
    diagnostics = sugarcubes_diagnostics_from_payload(
        payload=payload,
        exit_code=exit_code,
        output_lines=output_lines,
    )
    return SugarCubesMaintenanceResult(
        exit_code=exit_code,
        payload=payload,
        diagnostics=diagnostics,
        output_excerpt=tuple(output_lines[-40:]),
    )


def parse_sugarcubes_maintenance_payload(
    output_lines: Sequence[str],
) -> Mapping[str, object]:
    """Parse the first complete JSON object from pretty maintenance output."""

    text = "\n".join(output_lines)
    start = text.find("{")
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def sugarcubes_diagnostics_from_payload(
    *,
    payload: Mapping[str, object],
    exit_code: int,
    output_lines: Sequence[str],
) -> tuple[SugarCubesMaintenanceDiagnostic, ...]:
    """Return normalized SugarCubes diagnostics from maintenance output."""

    diagnostics = _explicit_sugarcubes_diagnostics(payload.get("diagnostics"))
    if diagnostics:
        return diagnostics
    synthesized: list[SugarCubesMaintenanceDiagnostic] = []
    synthesized.extend(_diagnostics_from_sync_errors(payload.get("syncErrors")))
    repair_result = payload.get("repairResult")
    if isinstance(repair_result, Mapping):
        synthesized.extend(_diagnostics_from_repair_payload(repair_result))
    synthesized.extend(_diagnostics_from_repair_payload(payload))
    pending_diagnostic = _diagnostic_from_dependency_readiness(
        payload,
        exit_code=exit_code,
    )
    if pending_diagnostic is not None:
        synthesized.append(pending_diagnostic)
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        synthesized.append(
            SugarCubesMaintenanceDiagnostic(
                code="sugarcubes_maintenance_failed",
                severity="error",
                title=app_text("SugarCubes maintenance failed"),
                message=error.strip(),
                details=details_mapping(payload.get("details")),
            )
        )
    if not synthesized and exit_code != 0:
        synthesized.append(
            SugarCubesMaintenanceDiagnostic(
                code="sugarcubes_maintenance_output_unparseable",
                severity="error",
                title=app_text("SugarCubes maintenance output was unreadable"),
                message=(
                    app_text(
                        "SugarCubes maintenance did not return parseable diagnostics. "
                        "Startup is continuing."
                    )
                ),
                details={"outputExcerpt": "\n".join(output_lines[-20:])},
            )
        )
    return tuple(synthesized)


def sugarcubes_required_dependency_failure_message(
    result: SugarCubesMaintenanceResult,
) -> str:
    """Return a setup-facing failure message for incomplete SugarCubes maintenance."""

    readiness = current_dependency_readiness(result.payload)
    missing_nodes = (
        string_sequence(readiness.get("missingCustomNodes"))
        if readiness is not None
        else ()
    )
    failed_nodes = repair_result_node_ids(result.payload, "failedNodes")
    skipped_nodes = repair_result_node_ids(result.payload, "skippedNodes")
    parts = ["SugarCubes could not prepare all required Base-Cubes dependencies."]
    if missing_nodes:
        parts.append(f"Missing nodepacks: {', '.join(missing_nodes)}.")
    if failed_nodes:
        parts.append(f"Failed installs: {', '.join(failed_nodes)}.")
    if skipped_nodes:
        parts.append(f"Skipped installs: {', '.join(skipped_nodes)}.")
    parts.append("Setup cannot continue until these required custom nodes install.")
    return " ".join(parts)


def repair_result_node_ids(
    payload: Mapping[str, object],
    field_name: str,
) -> tuple[str, ...]:
    """Return node IDs from a top-level or nested SugarCubes repair result list."""

    repair_result = payload.get("repairResult")
    source = repair_result if isinstance(repair_result, Mapping) else payload
    node_ids: list[str] = []
    for item in mapping_items(source.get(field_name)):
        node_id = string_value(item.get("nodeId"))
        if node_id:
            node_ids.append(node_id)
    return tuple(dict.fromkeys(node_ids))


def current_dependency_readiness(
    payload: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Return the latest readiness mapping from a SugarCubes payload."""

    top_level = payload.get("dependencyReadiness")
    if isinstance(top_level, Mapping):
        return top_level
    repair_result = payload.get("repairResult")
    if isinstance(repair_result, Mapping):
        repair_readiness = repair_result.get("readinessAfter")
        if isinstance(repair_readiness, Mapping):
            return repair_readiness
    direct_readiness = payload.get("readinessAfter")
    if isinstance(direct_readiness, Mapping):
        return direct_readiness
    if "ready" in payload and (
        "missingCustomNodes" in payload or "restartRequired" in payload
    ):
        return payload
    return None


def payload_restart_required(payload: Mapping[str, object]) -> bool:
    """Return whether the maintenance payload requires another startup pass."""

    if payload.get("restartRequired") is True:
        return True
    readiness = current_dependency_readiness(payload)
    if readiness is not None and readiness.get("restartRequired") is True:
        return True
    repair_result = payload.get("repairResult")
    if isinstance(repair_result, Mapping):
        return repair_result.get("restartRequiredAfterRepair") is True
    return False


def install_plan_node_ids(readiness: Mapping[str, object]) -> tuple[str, ...]:
    """Return node IDs from readiness install plan entries."""

    node_ids: list[str] = []
    for item in mapping_items(readiness.get("installPlan")):
        node_id = string_value(item.get("nodeId"))
        if node_id:
            node_ids.append(node_id)
    return tuple(dict.fromkeys(node_ids))


def diagnostic_detail_summary(details: Mapping[str, object]) -> str:
    """Return compact diagnostic details suitable for a startup log line."""

    parts: list[str] = []
    for key in ("repoRef", "nodeId", "reason", "error", "status"):
        value = details.get(key)
        if value is None:
            nested = details.get("details")
            value = nested.get(key) if isinstance(nested, Mapping) else None
        text = string_value(value)
        if text:
            parts.append(f"{key}={text}")
    return "; ".join(parts[:4])


def mapping_items(value: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping items from an arbitrary JSON field."""

    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def has_sequence_items(value: object) -> bool:
    """Return whether an arbitrary JSON array has any meaningful item."""

    return bool(mapping_items(value) or string_sequence(value))


def details_mapping(value: object) -> Mapping[str, object]:
    """Return a details mapping from an arbitrary JSON field."""

    return value if isinstance(value, Mapping) else {}


def normalized_diagnostic_severity(value: object) -> str:
    """Return a supported SugarCubes diagnostic severity."""

    severity = string_value(value).lower()
    return severity if severity in {"info", "warning", "error"} else "error"


def string_value(value: object) -> str:
    """Return a stripped string value for diagnostic text fields."""

    return value.strip() if isinstance(value, str) else ""


def string_sequence(value: object) -> tuple[str, ...]:
    """Return stripped string items from an arbitrary JSON array."""

    if not isinstance(value, list):
        return ()
    strings: list[str] = []
    for item in value:
        text = string_value(item)
        if text:
            strings.append(text)
    return tuple(strings)


def _explicit_sugarcubes_diagnostics(
    raw_diagnostics: object,
) -> tuple[SugarCubesMaintenanceDiagnostic, ...]:
    """Normalize diagnostics already emitted by SugarCubes."""

    if not isinstance(raw_diagnostics, list):
        return ()
    diagnostics: list[SugarCubesMaintenanceDiagnostic] = []
    for item in raw_diagnostics:
        if not isinstance(item, Mapping):
            continue
        diagnostic = _maintenance_diagnostic_from_mapping(item)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return tuple(diagnostics)


def _maintenance_diagnostic_from_mapping(
    item: Mapping[str, object],
) -> SugarCubesMaintenanceDiagnostic | None:
    """Coerce one JSON diagnostic mapping into the local diagnostic type."""

    title = string_value(item.get("title"))
    message = string_value(item.get("message"))
    if not title and not message:
        return None
    return SugarCubesMaintenanceDiagnostic(
        code=string_value(item.get("code")) or "sugarcubes_maintenance_issue",
        severity=normalized_diagnostic_severity(item.get("severity")),
        title=title or app_text("SugarCubes maintenance issue"),
        message=message or title,
        details=details_mapping(item.get("details")),
    )


def _diagnostics_from_sync_errors(
    sync_errors: object,
) -> tuple[SugarCubesMaintenanceDiagnostic, ...]:
    """Synthesize diagnostics from legacy sync error payloads."""

    if not isinstance(sync_errors, list):
        return ()
    diagnostics: list[SugarCubesMaintenanceDiagnostic] = []
    for item in sync_errors:
        if not isinstance(item, Mapping):
            continue
        repo_ref = string_value(item.get("repoRef"))
        diagnostics.append(
            SugarCubesMaintenanceDiagnostic(
                code="base_cubes_sync_failed",
                severity="warning",
                title=app_text("Base-Cubes sync failed"),
                message=(
                    app_text(
                        "SugarCubes could not update Base-Cubes and is using the local "
                        "checkout."
                    )
                    if "Base-Cubes" in repo_ref
                    else app_text(
                        "SugarCubes could not update one cube pack and is using local "
                        "data."
                    )
                ),
                details=dict(item),
            )
        )
    return tuple(diagnostics)


def _diagnostics_from_repair_payload(
    payload: Mapping[str, object],
) -> tuple[SugarCubesMaintenanceDiagnostic, ...]:
    """Synthesize diagnostics from legacy repair result fields."""

    diagnostics: list[SugarCubesMaintenanceDiagnostic] = []
    for item in mapping_items(payload.get("failedNodes")):
        node_id = string_value(item.get("nodeId"))
        diagnostics.append(
            SugarCubesMaintenanceDiagnostic(
                code="sugarcubes_dependency_install_failed",
                severity="error",
                title=app_text("SugarCubes dependency install failed"),
                message=(
                    app_text("%1 could not be installed automatically.", node_id)
                    if node_id
                    else app_text(
                        "A cube dependency could not be installed automatically."
                    )
                ),
                details=item,
            )
        )
    for item in mapping_items(payload.get("failedVersionItems")):
        node_id = string_value(item.get("nodeId"))
        diagnostics.append(
            SugarCubesMaintenanceDiagnostic(
                code="sugarcubes_dependency_version_repair_failed",
                severity="error",
                title=app_text("SugarCubes dependency version repair failed"),
                message=(
                    app_text(
                        "%1 could not be moved to the cube-required version.",
                        node_id,
                    )
                    if node_id
                    else app_text(
                        "A cube dependency could not be moved to the required version."
                    )
                ),
                details=item,
            )
        )
    return tuple(diagnostics)


def _diagnostic_from_dependency_readiness(
    payload: Mapping[str, object],
    *,
    exit_code: int,
) -> SugarCubesMaintenanceDiagnostic | None:
    """Synthesize a diagnostic from current dependency readiness state."""

    readiness = current_dependency_readiness(payload)
    if readiness is None or readiness.get("ready") is True:
        return None
    restart_required = payload_restart_required(payload)
    missing_nodes = string_sequence(readiness.get("missingCustomNodes"))
    installed_nodes = string_sequence(readiness.get("installedCustomNodes"))
    install_plan_ids = install_plan_node_ids(readiness)
    if not (restart_required or missing_nodes or install_plan_ids):
        return None
    details: dict[str, object] = {"restartRequired": restart_required}
    if missing_nodes:
        details["missingCustomNodes"] = list(missing_nodes)
    if installed_nodes:
        details["installedCustomNodes"] = list(installed_nodes)
    if install_plan_ids:
        details["installPlanNodeIds"] = list(install_plan_ids)
    title = app_text("SugarCubes required dependencies are missing")
    message = app_text("SugarCubes still reports missing baseline cube dependencies.")
    if missing_nodes:
        message = app_text(
            "%1 Missing: %2.",
            message,
            ", ".join(missing_nodes[:5]),
        )
    return SugarCubesMaintenanceDiagnostic(
        code="sugarcubes_dependency_maintenance_pending",
        severity="error" if exit_code != 0 else "warning",
        title=title,
        message=message,
        details=details,
    )


__all__ = [
    "SugarCubesMaintenanceDiagnostic",
    "SugarCubesMaintenanceResult",
    "current_dependency_readiness",
    "details_mapping",
    "diagnostic_detail_summary",
    "has_sequence_items",
    "install_plan_node_ids",
    "mapping_items",
    "normalized_diagnostic_severity",
    "parse_sugarcubes_maintenance_payload",
    "payload_restart_required",
    "repair_result_node_ids",
    "string_sequence",
    "string_value",
    "sugarcubes_diagnostics_from_payload",
    "sugarcubes_maintenance_result",
    "sugarcubes_required_dependency_failure_message",
]
