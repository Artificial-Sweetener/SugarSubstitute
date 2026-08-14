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

"""Own managed-setup evidence freshness, recovery, and runtime projection."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import UTC, datetime
import os
from pathlib import Path

from substitute.application.onboarding.managed_runtime_state_recorder import (
    ManagedRuntimeStateRecorder,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
)
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_runtime_configuration_codec import (
    managed_runtime_configuration_from_payload,
    managed_runtime_configuration_payload,
)
from substitute.infrastructure.comfy.managed_setup_evidence import (
    load_json_object,
    write_json_object_atomic,
)
from substitute.infrastructure.comfy.managed_setup_freshness_inputs import (
    installed_setup_static_freshness_key,
)
from substitute.shared.startup_trace import trace_mark

_SCHEMA_VERSION = 5
_MAX_AGE_SECONDS = 6 * 60 * 60
_DISABLE_ENV = "SUGARSUB_DISABLE_MANAGED_SETUP_CACHE"


def fresh_installed_setup_record_without_hardware_probe(
    *,
    workspace: Path,
    record_path: Path,
    request: Mapping[str, object],
    refresh_core_nodepacks: Collection[CoreNodepackId],
) -> dict[str, object] | None:
    """Return fresh setup evidence without initializing accelerator hardware."""

    if refresh_core_nodepacks:
        trace_mark("managed_setup.existing.fast_cache_skip", reason="refresh_requested")
        return None
    if os.getenv(_DISABLE_ENV) == "1":
        trace_mark("managed_setup.existing.fast_cache_skip", reason="disabled")
        return None
    record = load_installed_setup_freshness(record_path)
    if record is None:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="missing")
        return None
    if record.get("schema_version") != _SCHEMA_VERSION:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="schema")
        return None
    if record.get("success") is not True:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="not_successful")
        return None
    if record.get("request") != dict(request):
        trace_mark("managed_setup.existing.fast_cache_miss", reason="request_changed")
        return None
    key = record.get("key")
    if not isinstance(key, dict):
        trace_mark("managed_setup.existing.fast_cache_miss", reason="key")
        return None
    recorded_static_key = {
        name: value for name, value in key.items() if name != "strategy"
    }
    if recorded_static_key != installed_setup_static_freshness_key(workspace):
        trace_mark("managed_setup.existing.fast_cache_miss", reason="key_changed")
        return None
    age_seconds = _freshness_record_age_seconds(record)
    if age_seconds is None or age_seconds > _MAX_AGE_SECONDS:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="expired")
        return None
    trace_mark("managed_setup.existing.cache_hit", age_seconds=round(age_seconds, 3))
    return record


def installed_setup_freshness_is_current(
    *,
    record_path: Path,
    key: Mapping[str, object],
    refresh_core_nodepacks: Collection[CoreNodepackId],
) -> bool:
    """Return whether setup can reuse a recent successful reconciliation."""

    if refresh_core_nodepacks:
        trace_mark("managed_setup.existing.cache_skip", reason="refresh_requested")
        return False
    if os.getenv(_DISABLE_ENV) == "1":
        trace_mark("managed_setup.existing.cache_skip", reason="disabled")
        return False
    record = load_installed_setup_freshness(record_path)
    if record is None:
        trace_mark("managed_setup.existing.cache_miss", reason="missing")
        return False
    if record.get("schema_version") != _SCHEMA_VERSION:
        trace_mark("managed_setup.existing.cache_miss", reason="schema")
        return False
    if record.get("success") is not True:
        trace_mark("managed_setup.existing.cache_miss", reason="not_successful")
        return False
    if record.get("key") != dict(key):
        trace_mark("managed_setup.existing.cache_miss", reason="key_changed")
        return False
    age_seconds = _freshness_record_age_seconds(record)
    if age_seconds is None or age_seconds > _MAX_AGE_SECONDS:
        trace_mark("managed_setup.existing.cache_miss", reason="expired")
        return False
    trace_mark("managed_setup.existing.cache_hit", age_seconds=round(age_seconds, 3))
    return True


def load_installed_setup_freshness(record_path: Path) -> dict[str, object] | None:
    """Load setup evidence, treating corrupt or unreadable data as a cache miss."""

    return load_json_object(record_path)


def write_installed_setup_freshness(
    *,
    record_path: Path,
    key: Mapping[str, object],
    request: Mapping[str, object],
    runtime_configuration: ManagedRuntimeConfiguration,
    validation: ManagedEnvironmentValidationResult,
) -> None:
    """Persist successful setup evidence in the prepared cache namespace."""

    payload = {
        "schema_version": _SCHEMA_VERSION,
        "recorded_at": datetime.now(UTC).isoformat(),
        "request": dict(request),
        "runtime_configuration": managed_runtime_configuration_payload(
            runtime_configuration
        ),
        "success": validation.success,
        "validation": {
            "detail": validation.detail,
            "detected_backend": getattr(validation, "detected_backend", None),
            "detected_torch_channel": getattr(
                validation, "detected_torch_channel", None
            ),
            "torch_version": getattr(validation, "torch_version", None),
            "device_name": getattr(validation, "device_name", None),
        },
        "key": dict(key),
    }
    write_json_object_atomic(record_path, payload)
    trace_mark("managed_setup.existing.cache_written")


def record_cached_installed_setup_success(
    *,
    runtime_recorder: ManagedRuntimeStateRecorder,
    record: Mapping[str, object],
) -> None:
    """Project cached setup evidence into the managed runtime state owner."""

    configuration = managed_runtime_configuration_from_payload(
        record.get("runtime_configuration")
    )
    if configuration is not None:
        runtime_recorder.record_selection(configuration)
    validation = record.get("validation")
    detail = None
    if isinstance(validation, Mapping):
        raw_detail = validation.get("detail")
        detail = raw_detail if isinstance(raw_detail, str) else None
    runtime_recorder.record_validation(
        status=ManagedRuntimeValidationStatus.VALID,
        detail=detail,
    )


def validation_from_installed_setup_record(
    record: Mapping[str, object],
) -> ManagedEnvironmentValidationResult | None:
    """Return validated runtime details from one setup-evidence record."""

    validation = record.get("validation")
    if not isinstance(validation, Mapping):
        return None
    detail = validation.get("detail")
    detected_backend = validation.get("detected_backend")
    detected_torch_channel = validation.get("detected_torch_channel")
    torch_version = validation.get("torch_version")
    device_name = validation.get("device_name")
    if not (
        isinstance(detail, str)
        and isinstance(detected_backend, str)
        and isinstance(detected_torch_channel, str)
        and (isinstance(torch_version, str) or torch_version is None)
        and (isinstance(device_name, str) or device_name is None)
    ):
        return None
    return ManagedEnvironmentValidationResult(
        success=record.get("success") is True,
        detail=detail,
        detected_backend=detected_backend,
        detected_torch_channel=detected_torch_channel,
        torch_version=torch_version,
        device_name=device_name,
    )


def _freshness_record_age_seconds(record: Mapping[str, object]) -> float | None:
    """Return the nonnegative age in seconds for one cache record."""

    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str):
        return None
    try:
        timestamp = datetime.fromisoformat(recorded_at)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds())


__all__ = [
    "fresh_installed_setup_record_without_hardware_probe",
    "installed_setup_freshness_is_current",
    "load_installed_setup_freshness",
    "record_cached_installed_setup_success",
    "validation_from_installed_setup_record",
    "write_installed_setup_freshness",
]
