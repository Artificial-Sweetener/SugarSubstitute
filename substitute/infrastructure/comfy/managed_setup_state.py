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

"""Own persisted managed-setup selection and freshness evidence."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import UTC, datetime
import json
import os
from pathlib import Path

from substitute.application.onboarding.managed_runtime_state_recorder import (
    ManagedRuntimeStateRecorder,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
    workspace_venv_dir,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SUGARCUBES_COMPANION_NODEPACKS,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    repository_service,
)
from substitute.shared.startup_trace import trace_mark

_MANAGED_SETUP_FRESHNESS_SCHEMA_VERSION = 2
_MANAGED_SETUP_FRESHNESS_MAX_AGE_SECONDS = 6 * 60 * 60
_MANAGED_SETUP_FRESHNESS_DISABLE_ENV = "SUGARSUB_DISABLE_MANAGED_SETUP_CACHE"


def _managed_runtime_configuration_from_strategy(
    *,
    workspace: Path,
    detection: object,
    strategy: object,
    force_cpu_mode: bool,
    prefer_edge_torch: bool,
    prefer_edge_comfy_channel: bool,
) -> ManagedRuntimeConfiguration:
    """Build managed runtime selection state from the install strategy."""

    adapters = getattr(detection, "adapters", ())
    adapter = adapters[0] if adapters else None
    platform = getattr(getattr(detection, "platform", None), "value", None)
    accelerator = getattr(
        getattr(detection, "preferred_accelerator", None),
        "value",
        None,
    )
    python_runtime = getattr(strategy, "python_runtime")
    torch_policy = getattr(strategy, "torch_policy")
    stability = (
        ManagedRuntimeStability.EXPERIMENTAL
        if getattr(strategy, "stability", "stable") == "experimental"
        else ManagedRuntimeStability.STABLE
    )
    return ManagedRuntimeConfiguration(
        workspace_path=str(workspace.resolve()),
        detected_platform=platform,
        detected_accelerator=accelerator,
        detected_adapter_name=getattr(adapter, "name", None),
        install_target=getattr(getattr(strategy, "target"), "value", None),
        python_version=getattr(python_runtime, "selected_version", None),
        python_fallback_used=bool(getattr(python_runtime, "used_fallback", False)),
        comfy_channel=getattr(getattr(strategy, "comfy_channel"), "value", None),
        backend_policy=getattr(torch_policy, "backend_key", None),
        torch_release_channel=getattr(
            getattr(torch_policy, "release_channel", None),
            "value",
            None,
        ),
        torch_selection_reason=getattr(torch_policy, "selection_reason", None),
        torch_fallback_used=False,
        stability=stability,
        prefer_edge_torch=prefer_edge_torch,
        prefer_edge_comfy_channel=prefer_edge_comfy_channel,
        force_cpu_mode=force_cpu_mode,
        validation_status=ManagedRuntimeValidationStatus.UNKNOWN,
        launch_status=ManagedRuntimeLaunchStatus.UNKNOWN,
    )


def _installed_setup_freshness_path(workspace: Path) -> Path:
    """Return the installed-workspace setup freshness record path."""

    return workspace / ".substitute" / "managed_setup_freshness.json"


def _installed_setup_freshness_key(
    *,
    workspace: Path,
    strategy: object,
) -> dict[str, object]:
    """Build a stable key for recurring installed-workspace setup checks."""

    key = _installed_setup_static_freshness_key(workspace)
    key["strategy"] = _strategy_freshness_key(strategy)
    return key


def _installed_setup_static_freshness_key(workspace: Path) -> dict[str, object]:
    """Build installed-workspace freshness inputs independent of hardware probing."""

    return {
        "schema_version": _MANAGED_SETUP_FRESHNESS_SCHEMA_VERSION,
        "workspace": {
            "python": _path_signature(workspace_python_path(workspace)),
            "main": _path_signature(workspace_main_path(workspace)),
            "site_packages": _site_packages_signature(workspace),
        },
        "manager": _manager_freshness_key(workspace),
        "core_nodepacks": [
            _core_nodepack_freshness_key(workspace, nodepack)
            for nodepack in CORE_COMFY_NODEPACKS
        ],
        "sugarcubes_baseline": _sugarcubes_baseline_freshness_key(workspace),
    }


def _installed_setup_freshness_request(
    *,
    force_cpu_mode: bool,
    prefer_edge_torch: bool,
    prefer_edge_comfy_channel: bool,
) -> dict[str, object]:
    """Return caller preferences that can change the selected runtime strategy."""

    return {
        "force_cpu_mode": force_cpu_mode,
        "prefer_edge_torch": prefer_edge_torch,
        "prefer_edge_comfy_channel": prefer_edge_comfy_channel,
    }


def _fresh_installed_setup_record_without_hardware_probe(
    *,
    workspace: Path,
    request: Mapping[str, object],
    refresh_core_nodepacks: Collection[CoreNodepackId],
) -> dict[str, object] | None:
    """Return a fresh installed-workspace setup record without hardware probing."""

    if refresh_core_nodepacks:
        trace_mark(
            "managed_setup.existing.fast_cache_skip",
            reason="refresh_requested",
        )
        return None
    if os.getenv(_MANAGED_SETUP_FRESHNESS_DISABLE_ENV) == "1":
        trace_mark(
            "managed_setup.existing.fast_cache_skip",
            reason="disabled",
        )
        return None
    record = _load_installed_setup_freshness(workspace)
    if record is None:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="missing")
        return None
    if record.get("schema_version") != _MANAGED_SETUP_FRESHNESS_SCHEMA_VERSION:
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
    if recorded_static_key != _installed_setup_static_freshness_key(workspace):
        trace_mark("managed_setup.existing.fast_cache_miss", reason="key_changed")
        return None
    age_seconds = _freshness_record_age_seconds(record)
    if age_seconds is None or age_seconds > _MANAGED_SETUP_FRESHNESS_MAX_AGE_SECONDS:
        trace_mark("managed_setup.existing.fast_cache_miss", reason="expired")
        return None
    trace_mark(
        "managed_setup.existing.cache_hit",
        age_seconds=round(age_seconds, 3),
    )
    return record


def _installed_setup_freshness_is_current(
    *,
    workspace: Path,
    key: Mapping[str, object],
    refresh_core_nodepacks: Collection[CoreNodepackId],
) -> bool:
    """Return whether installed-workspace setup can reuse a recent success."""

    if refresh_core_nodepacks:
        trace_mark(
            "managed_setup.existing.cache_skip",
            reason="refresh_requested",
        )
        return False
    if os.getenv(_MANAGED_SETUP_FRESHNESS_DISABLE_ENV) == "1":
        trace_mark(
            "managed_setup.existing.cache_skip",
            reason="disabled",
        )
        return False
    record = _load_installed_setup_freshness(workspace)
    if record is None:
        trace_mark("managed_setup.existing.cache_miss", reason="missing")
        return False
    if record.get("schema_version") != _MANAGED_SETUP_FRESHNESS_SCHEMA_VERSION:
        trace_mark("managed_setup.existing.cache_miss", reason="schema")
        return False
    if record.get("success") is not True:
        trace_mark("managed_setup.existing.cache_miss", reason="not_successful")
        return False
    if record.get("key") != dict(key):
        trace_mark("managed_setup.existing.cache_miss", reason="key_changed")
        return False
    age_seconds = _freshness_record_age_seconds(record)
    if age_seconds is None or age_seconds > _MANAGED_SETUP_FRESHNESS_MAX_AGE_SECONDS:
        trace_mark("managed_setup.existing.cache_miss", reason="expired")
        return False
    trace_mark(
        "managed_setup.existing.cache_hit",
        age_seconds=round(age_seconds, 3),
    )
    return True


def _load_installed_setup_freshness(workspace: Path) -> dict[str, object] | None:
    """Load one installed-workspace setup freshness record if it is valid JSON."""

    path = _installed_setup_freshness_path(workspace)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_installed_setup_freshness(
    *,
    workspace: Path,
    key: Mapping[str, object],
    request: Mapping[str, object],
    runtime_configuration: ManagedRuntimeConfiguration,
    validation: ManagedEnvironmentValidationResult,
) -> None:
    """Persist successful installed-workspace setup freshness evidence."""

    path = _installed_setup_freshness_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _MANAGED_SETUP_FRESHNESS_SCHEMA_VERSION,
        "recorded_at": datetime.now(UTC).isoformat(),
        "request": dict(request),
        "runtime_configuration": _managed_runtime_configuration_payload(
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    trace_mark("managed_setup.existing.cache_written")


def _record_cached_installed_setup_success(
    *,
    runtime_recorder: ManagedRuntimeStateRecorder,
    record: Mapping[str, object],
) -> None:
    """Record cached runtime success without revalidating the installed workspace."""

    configuration = _managed_runtime_configuration_from_payload(
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


def _validation_from_installed_setup_record(
    record: Mapping[str, object],
) -> ManagedEnvironmentValidationResult | None:
    """Return cached validation details from an installed-workspace setup record."""

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


def _managed_runtime_configuration_payload(
    configuration: ManagedRuntimeConfiguration,
) -> dict[str, object]:
    """Return a JSON-safe managed runtime configuration payload."""

    return {
        "workspace_path": configuration.workspace_path,
        "detected_platform": configuration.detected_platform,
        "detected_accelerator": configuration.detected_accelerator,
        "detected_adapter_name": configuration.detected_adapter_name,
        "install_target": configuration.install_target,
        "python_version": configuration.python_version,
        "python_fallback_used": configuration.python_fallback_used,
        "comfy_channel": configuration.comfy_channel,
        "backend_policy": configuration.backend_policy,
        "torch_release_channel": configuration.torch_release_channel,
        "torch_selection_reason": configuration.torch_selection_reason,
        "torch_fallback_used": configuration.torch_fallback_used,
        "stability": _enum_value(configuration.stability),
        "prefer_edge_torch": configuration.prefer_edge_torch,
        "prefer_edge_comfy_channel": configuration.prefer_edge_comfy_channel,
        "force_cpu_mode": configuration.force_cpu_mode,
        "validation_status": _enum_value(configuration.validation_status),
        "validation_detail": configuration.validation_detail,
        "last_validation_at": configuration.last_validation_at,
        "launch_status": _enum_value(configuration.launch_status),
        "launch_detail": configuration.launch_detail,
        "last_launch_at": configuration.last_launch_at,
    }


def _managed_runtime_configuration_from_payload(
    payload: object,
) -> ManagedRuntimeConfiguration | None:
    """Return a managed runtime configuration from a freshness-cache payload."""

    if not isinstance(payload, Mapping):
        return None
    try:
        return ManagedRuntimeConfiguration(
            workspace_path=_optional_string(payload.get("workspace_path")),
            detected_platform=_optional_string(payload.get("detected_platform")),
            detected_accelerator=_optional_string(payload.get("detected_accelerator")),
            detected_adapter_name=_optional_string(
                payload.get("detected_adapter_name")
            ),
            install_target=_optional_string(payload.get("install_target")),
            python_version=_optional_string(payload.get("python_version")),
            python_fallback_used=bool(payload.get("python_fallback_used", False)),
            comfy_channel=_optional_string(payload.get("comfy_channel")),
            backend_policy=_optional_string(payload.get("backend_policy")),
            torch_release_channel=_optional_string(
                payload.get("torch_release_channel")
            ),
            torch_selection_reason=_optional_string(
                payload.get("torch_selection_reason")
            ),
            torch_fallback_used=bool(payload.get("torch_fallback_used", False)),
            stability=ManagedRuntimeStability(
                payload.get("stability", ManagedRuntimeStability.STABLE.value)
            ),
            prefer_edge_torch=bool(payload.get("prefer_edge_torch", False)),
            prefer_edge_comfy_channel=bool(
                payload.get("prefer_edge_comfy_channel", False)
            ),
            force_cpu_mode=bool(payload.get("force_cpu_mode", False)),
            validation_status=ManagedRuntimeValidationStatus(
                payload.get(
                    "validation_status",
                    ManagedRuntimeValidationStatus.UNKNOWN.value,
                )
            ),
            validation_detail=_optional_string(payload.get("validation_detail")),
            last_validation_at=_optional_string(payload.get("last_validation_at")),
            launch_status=ManagedRuntimeLaunchStatus(
                payload.get("launch_status", ManagedRuntimeLaunchStatus.UNKNOWN.value)
            ),
            launch_detail=_optional_string(payload.get("launch_detail")),
            last_launch_at=_optional_string(payload.get("last_launch_at")),
        )
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    """Return a string value only when the payload contains one."""

    return value if isinstance(value, str) else None


def _freshness_record_age_seconds(record: Mapping[str, object]) -> float | None:
    """Return the age in seconds for a freshness record."""

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


def _strategy_freshness_key(strategy: object) -> dict[str, object]:
    """Return the install strategy fields that affect setup validity."""

    python_runtime = getattr(strategy, "python_runtime", None)
    torch_policy = getattr(strategy, "torch_policy", None)
    return {
        "target": _enum_value(getattr(strategy, "target", None)),
        "python_version": getattr(python_runtime, "selected_version", None),
        "python_executable": str(getattr(python_runtime, "executable", "")),
        "python_fallback_used": bool(getattr(python_runtime, "used_fallback", False)),
        "comfy_channel": _enum_value(getattr(strategy, "comfy_channel", None)),
        "stability": _enum_value(getattr(strategy, "stability", None)),
        "torch_backend_key": getattr(torch_policy, "backend_key", None),
        "torch_release_channel": _enum_value(
            getattr(torch_policy, "release_channel", None)
        ),
        "torch_selection_reason": getattr(torch_policy, "selection_reason", None),
        "torch_install_arguments": list(
            getattr(torch_policy, "install_arguments", ()) or ()
        ),
        "torch_fallback_backend_key": getattr(
            torch_policy, "fallback_backend_key", None
        ),
        "torch_fallback_release_channel": _enum_value(
            getattr(torch_policy, "fallback_release_channel", None)
        ),
        "torch_fallback_install_arguments": list(
            getattr(torch_policy, "fallback_install_arguments", ()) or ()
        ),
        "validation_expected": _enum_value(
            getattr(torch_policy, "validation_expected", None)
        ),
    }


def _manager_freshness_key(workspace: Path) -> dict[str, object]:
    """Return the workspace manager files that affect setup validity."""

    manager_dir = workspace / "custom_nodes" / "ComfyUI-Manager"
    return {
        "directory": _path_signature(manager_dir),
        "git": _git_head_signature(manager_dir),
        "cli": _path_signature(manager_dir / "cm-cli.py"),
        "requirements": _path_signature(workspace / "manager_requirements.txt"),
    }


def _core_nodepack_freshness_key(
    workspace: Path,
    nodepack: object,
) -> dict[str, object]:
    """Return freshness inputs for one required core nodepack."""

    expected_folder = getattr(nodepack, "expected_folder")
    nodepack_root = workspace / expected_folder
    return {
        "id": _enum_value(getattr(nodepack, "nodepack_id", None)),
        "project": getattr(nodepack, "project_name", None),
        "registry": getattr(nodepack, "registry_id", None),
        "folder": str(expected_folder),
        "folder_signature": _path_signature(nodepack_root),
        "git": _git_head_signature(nodepack_root),
        "sentinels": [
            _path_signature(nodepack_root / sentinel)
            for sentinel in getattr(nodepack, "sentinel_files", ())
        ],
        "source_url": getattr(nodepack, "source_url", None),
        "python_distribution": getattr(nodepack, "python_distribution_name", None),
        "minimum_version": getattr(
            nodepack, "minimum_python_distribution_version", None
        ),
        "pinned_archive": getattr(nodepack, "pinned_source_archive_url", None),
    }


def _sugarcubes_baseline_freshness_key(workspace: Path) -> dict[str, object]:
    """Return freshness inputs for SugarCubes baseline dependency maintenance."""

    sugarcubes_root = workspace / "custom_nodes" / "SugarCubes"
    return {
        "maintenance": _path_signature(sugarcubes_root / "backend" / "maintenance.py"),
        "backend": _path_signature(sugarcubes_root / "backend" / "__init__.py"),
        "install_mapping": {
            node_id: [
                {
                    "install_id": candidate.install_id,
                    "cloned_folder_name": candidate.cloned_folder_name,
                    "expected_folder_name": candidate.expected_folder_name,
                }
                for candidate in candidates
            ]
            for node_id, candidates in sorted(SUGARCUBES_BASE_NODEPACK_INSTALLS.items())
        },
        "companions": {
            node_id: list(companions)
            for node_id, companions in sorted(SUGARCUBES_COMPANION_NODEPACKS.items())
        },
    }


def _site_packages_signature(workspace: Path) -> dict[str, object]:
    """Return a coarse signature for the managed workspace site-packages root."""

    venv_dir = workspace_venv_dir(workspace)
    candidates = [venv_dir / "Lib" / "site-packages"]
    lib_dir = venv_dir / "lib"
    if lib_dir.exists():
        candidates.extend(lib_dir.glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.exists():
            return _path_signature(candidate)
    return {"exists": False}


def _path_signature(path: Path) -> dict[str, object]:
    """Return a cheap filesystem signature for one path."""

    try:
        stat = path.stat()
    except OSError:
        return {"exists": False}
    return {
        "exists": True,
        "is_dir": path.is_dir(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _git_head_signature(path: Path) -> dict[str, object]:
    """Return a lightweight git HEAD signature for a checkout path."""

    if not (path / ".git").exists():
        return {"exists": False}
    try:
        head_commit = repository_service().head_commit_id(path)
    except RepositoryOperationError:
        return {"exists": False}
    return {"exists": True, "head": head_commit}


def _read_text(path: Path, *, limit: int = 4096) -> str:
    """Read a small text file payload for freshness signatures."""

    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit].strip()
    except OSError:
        return ""


def _enum_value(value: object) -> object:
    """Return a stable primitive value for enums and simple objects."""

    return getattr(value, "value", value)
