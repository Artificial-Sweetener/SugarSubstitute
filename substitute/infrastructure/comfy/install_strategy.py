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

"""Map detected hardware into one explicit managed install strategy."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.infrastructure.comfy.comfy_channel_policy import ComfyChannel
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.python_policy import (
    PythonRuntimeSelection,
    resolve_python_runtime,
)
from substitute.infrastructure.comfy.torch_policy import (
    TorchBackendPolicy,
    build_torch_policy,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.variant_policy import (
    standalone_variant_for_target,
)


@dataclass(frozen=True)
class ManagedInstallStrategy:
    """Describe the complete install decision for one managed Comfy workspace."""

    target: ManagedInstallTarget
    python_runtime: PythonRuntimeSelection
    comfy_channel: ComfyChannel
    torch_policy: TorchBackendPolicy
    standalone_variant: StandaloneVariantId | None
    stability: str
    summary_reason: str


def select_install_strategy(
    *,
    detection: HardwareDetectionResult,
    force_cpu: bool = False,
    prefer_edge_torch: bool = False,
    prefer_edge_comfy: bool = False,
) -> ManagedInstallStrategy:
    """Select one explicit managed install strategy from normalized hardware detection."""

    target, reason = _select_install_target(detection=detection, force_cpu=force_cpu)
    channel = ComfyChannel.NIGHTLY if prefer_edge_comfy else ComfyChannel.LATEST
    python_runtime = resolve_python_runtime()
    selected_adapter = detection.selected_adapter
    generation_hint = (
        selected_adapter.generation_hint if selected_adapter is not None else None
    )
    torch_policy = build_torch_policy(
        target=target,
        edge=prefer_edge_torch,
        generation_hint=generation_hint,
    )
    stability = "experimental" if torch_policy.stability == "experimental" else "stable"
    return ManagedInstallStrategy(
        target=target,
        python_runtime=python_runtime,
        comfy_channel=channel,
        torch_policy=torch_policy,
        standalone_variant=(
            None if prefer_edge_torch else standalone_variant_for_target(target)
        ),
        stability=stability,
        summary_reason=reason,
    )


def _select_install_target(
    *,
    detection: HardwareDetectionResult,
    force_cpu: bool,
) -> tuple[ManagedInstallTarget, str]:
    """Select the normalized install target from platform and accelerator inputs."""

    if force_cpu:
        return _cpu_target_for_platform(detection.platform), "CPU mode was forced."
    accelerator = detection.preferred_accelerator
    if detection.platform is ManagedPlatform.MACOS:
        if accelerator is AcceleratorClass.APPLE_MPS:
            return (
                ManagedInstallTarget.MACOS_APPLE_SILICON,
                "Detected Apple Silicon MPS acceleration.",
            )
        raise ValueError("Managed Comfy on macOS requires Apple Silicon MPS.")
    if detection.platform is ManagedPlatform.WINDOWS:
        if accelerator is AcceleratorClass.NVIDIA:
            return ManagedInstallTarget.WINDOWS_NVIDIA, "Detected NVIDIA acceleration."
        if accelerator is AcceleratorClass.AMD:
            if _supports_windows_amd(detection.selected_adapter):
                return (
                    ManagedInstallTarget.WINDOWS_AMD,
                    "Detected supported AMD RDNA acceleration.",
                )
            return ManagedInstallTarget.WINDOWS_CPU, (
                "Detected AMD graphics without a safe README-backed Windows path; "
                "falling back to CPU mode."
            )
        if accelerator is AcceleratorClass.INTEL_XPU:
            return (
                ManagedInstallTarget.WINDOWS_INTEL_XPU,
                "Detected Intel XPU acceleration.",
            )
        return (
            ManagedInstallTarget.WINDOWS_CPU,
            "No supported GPU acceleration was detected.",
        )
    if accelerator is AcceleratorClass.NVIDIA:
        return ManagedInstallTarget.LINUX_NVIDIA, "Detected NVIDIA acceleration."
    if accelerator is AcceleratorClass.AMD:
        return ManagedInstallTarget.LINUX_AMD, "Detected AMD acceleration."
    if accelerator is AcceleratorClass.INTEL_XPU:
        return ManagedInstallTarget.LINUX_INTEL_XPU, "Detected Intel XPU acceleration."
    raise ValueError(
        "Managed Comfy on Linux requires a published NVIDIA, AMD, or Intel XPU "
        "standalone environment. Comfy Desktop does not currently publish Linux CPU."
    )


def _supports_windows_amd(adapter: HardwareAdapterInfo | None) -> bool:
    """Return whether the detected AMD hardware matches the README-backed Windows path."""

    if adapter is None or adapter.accelerator_class is not AcceleratorClass.AMD:
        return False
    hint = (adapter.generation_hint or "").lower()
    name = adapter.name.lower()
    return any(
        token in hint or token in name
        for token in ("rdna3", "rdna3.5", "rdna4", "gfx110", "gfx1151", "gfx120")
    )


def _cpu_target_for_platform(platform: ManagedPlatform) -> ManagedInstallTarget:
    """Return the CPU fallback target for the supplied platform."""

    if platform is ManagedPlatform.WINDOWS:
        return ManagedInstallTarget.WINDOWS_CPU
    if platform is ManagedPlatform.MACOS:
        raise ValueError("CPU fallback is not supported for managed macOS installs.")
    raise ValueError(
        "CPU mode is unavailable on Linux because Comfy Desktop does not currently "
        "publish a verified Linux CPU standalone environment."
    )


__all__ = ["ManagedInstallStrategy", "select_install_strategy"]
