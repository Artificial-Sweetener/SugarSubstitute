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

"""Build and encode managed runtime selections for setup evidence."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.domain.onboarding import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)


def managed_runtime_configuration_from_strategy(
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


def managed_runtime_configuration_payload(
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
        "stability": enum_value(configuration.stability),
        "prefer_edge_torch": configuration.prefer_edge_torch,
        "prefer_edge_comfy_channel": configuration.prefer_edge_comfy_channel,
        "force_cpu_mode": configuration.force_cpu_mode,
        "validation_status": enum_value(configuration.validation_status),
        "validation_detail": configuration.validation_detail,
        "last_validation_at": configuration.last_validation_at,
        "launch_status": enum_value(configuration.launch_status),
        "launch_detail": configuration.launch_detail,
        "last_launch_at": configuration.last_launch_at,
    }


def managed_runtime_configuration_from_payload(
    payload: object,
) -> ManagedRuntimeConfiguration | None:
    """Return managed runtime state from a setup-evidence payload."""

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


def enum_value(value: object) -> object:
    """Return a stable primitive value for enums and simple objects."""

    return getattr(value, "value", value)


def _optional_string(value: object) -> str | None:
    """Return a string value only when the payload contains one."""

    return value if isinstance(value, str) else None


__all__ = [
    "enum_value",
    "managed_runtime_configuration_from_payload",
    "managed_runtime_configuration_from_strategy",
    "managed_runtime_configuration_payload",
]
