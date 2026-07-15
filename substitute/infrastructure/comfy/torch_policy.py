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

"""Define torch backend policy commands for managed Comfy install targets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget


class TorchReleaseChannel(str, Enum):
    """Identify the torch release channel chosen for one managed install target."""

    STABLE = "stable"
    NIGHTLY = "nightly"


@dataclass(frozen=True)
class TorchBackendPolicy:
    """Describe the torch install command and validation expectations for one target."""

    backend_key: str
    install_arguments: tuple[str, ...]
    release_channel: TorchReleaseChannel
    selection_reason: str
    stability: str
    validation_expected: AcceleratorClass
    fallback_backend_key: str | None = None
    fallback_install_arguments: tuple[str, ...] | None = None
    fallback_release_channel: TorchReleaseChannel | None = None
    fallback_selection_reason: str | None = None


def build_torch_policy(
    *,
    target: ManagedInstallTarget,
    edge: bool,
    generation_hint: str | None,
) -> TorchBackendPolicy:
    """Return the explicit torch/backend install policy for one install target."""

    if target in {
        ManagedInstallTarget.WINDOWS_NVIDIA,
        ManagedInstallTarget.LINUX_NVIDIA,
    }:
        if edge:
            return TorchBackendPolicy(
                backend_key="cuda_nightly_cu132",
                install_arguments=(
                    "--pre",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/nightly/cu132",
                ),
                release_channel=TorchReleaseChannel.NIGHTLY,
                selection_reason=(
                    "Nightly torch was requested explicitly for this NVIDIA install."
                ),
                stability="experimental",
                validation_expected=AcceleratorClass.NVIDIA,
                fallback_backend_key="cuda_cu130",
                fallback_install_arguments=(
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--extra-index-url",
                    "https://download.pytorch.org/whl/cu130",
                ),
                fallback_release_channel=TorchReleaseChannel.STABLE,
                fallback_selection_reason=(
                    "Substitute is using Comfy's recommended stable CUDA path after "
                    "the requested nightly path failed."
                ),
            )
        return TorchBackendPolicy(
            backend_key="cuda_cu130",
            install_arguments=(
                "torch",
                "torchvision",
                "torchaudio",
                "--extra-index-url",
                "https://download.pytorch.org/whl/cu130",
            ),
            release_channel=TorchReleaseChannel.STABLE,
            selection_reason="NVIDIA installs use Comfy's recommended stable CUDA path.",
            stability="stable",
            validation_expected=AcceleratorClass.NVIDIA,
            fallback_backend_key="cuda_nightly_cu132",
            fallback_install_arguments=(
                "--pre",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/nightly/cu132",
            ),
            fallback_release_channel=TorchReleaseChannel.NIGHTLY,
            fallback_selection_reason=(
                "Substitute is trying Comfy's optional CUDA nightly path after the "
                "stable path failed."
            ),
        )
    if target is ManagedInstallTarget.LINUX_AMD:
        if edge:
            return TorchBackendPolicy(
                backend_key="rocm72_nightly",
                install_arguments=(
                    "--pre",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/nightly/rocm7.2",
                ),
                release_channel=TorchReleaseChannel.NIGHTLY,
                selection_reason=(
                    "Nightly ROCm torch was requested explicitly for this AMD install."
                ),
                stability="experimental",
                validation_expected=AcceleratorClass.AMD,
                fallback_backend_key="rocm72",
                fallback_install_arguments=(
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/rocm7.2",
                ),
                fallback_release_channel=TorchReleaseChannel.STABLE,
                fallback_selection_reason=(
                    "Substitute is using Comfy's stable ROCm 7.2 path after the "
                    "requested nightly path failed."
                ),
            )
        return TorchBackendPolicy(
            backend_key="rocm72",
            install_arguments=(
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/rocm7.2",
            ),
            release_channel=TorchReleaseChannel.STABLE,
            selection_reason="Linux AMD installs use Comfy's stable ROCm 7.2 path.",
            stability="stable",
            validation_expected=AcceleratorClass.AMD,
            fallback_backend_key="rocm72_nightly",
            fallback_install_arguments=(
                "--pre",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/nightly/rocm7.2",
            ),
            fallback_release_channel=TorchReleaseChannel.NIGHTLY,
            fallback_selection_reason=(
                "Substitute is trying Comfy's optional ROCm 7.2 nightly path after "
                "the stable path failed."
            ),
        )
    if target is ManagedInstallTarget.WINDOWS_AMD:
        index_url = _windows_amd_index_url(generation_hint)
        if not edge:
            return TorchBackendPolicy(
                backend_key="windows_rocm721",
                install_arguments=(
                    "rocm-sdk-core==7.2.1",
                    "rocm-sdk-devel==7.2.1",
                    "rocm-sdk-libraries-custom==7.2.1",
                    "rocm==7.2.1",
                    "torch==2.9.1+rocm7.2.1",
                    "torchvision==0.24.1+rocm7.2.1",
                    "torchaudio==2.9.1+rocm7.2.1",
                    "--find-links",
                    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/",
                ),
                release_channel=TorchReleaseChannel.STABLE,
                selection_reason=(
                    "Windows AMD installs use Comfy Desktop's verified ROCm 7.2.1 "
                    "environment."
                ),
                stability="stable",
                validation_expected=AcceleratorClass.AMD,
                fallback_backend_key=(
                    index_url.rsplit("/", 2)[-2] if "gfx" in index_url else None
                ),
                fallback_install_arguments=(
                    "--pre",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    index_url,
                ),
                fallback_release_channel=TorchReleaseChannel.NIGHTLY,
                fallback_selection_reason=(
                    "Substitute is trying ComfyUI's hardware-specific Windows AMD "
                    "nightly path after the verified stable environment failed."
                ),
            )
        return TorchBackendPolicy(
            backend_key=index_url.rsplit("/", 2)[-2] if "gfx" in index_url else "cpu",
            install_arguments=(
                "--pre",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                index_url,
            ),
            release_channel=TorchReleaseChannel.NIGHTLY,
            selection_reason=(
                "Windows AMD installs use the README-backed experimental ROCm "
                "nightly path for supported RDNA hardware."
            ),
            stability="experimental",
            validation_expected=AcceleratorClass.AMD,
        )
    if target in {
        ManagedInstallTarget.WINDOWS_INTEL_XPU,
        ManagedInstallTarget.LINUX_INTEL_XPU,
    }:
        if edge:
            return TorchBackendPolicy(
                backend_key="xpu_nightly",
                install_arguments=(
                    "--pre",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/nightly/xpu",
                ),
                release_channel=TorchReleaseChannel.NIGHTLY,
                selection_reason="Nightly XPU torch was requested explicitly.",
                stability="experimental",
                validation_expected=AcceleratorClass.INTEL_XPU,
                fallback_backend_key="xpu",
                fallback_install_arguments=(
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/xpu",
                ),
                fallback_release_channel=TorchReleaseChannel.STABLE,
                fallback_selection_reason=(
                    "Substitute is using Comfy's stable XPU path after the requested "
                    "nightly path failed."
                ),
            )
        return TorchBackendPolicy(
            backend_key="xpu",
            install_arguments=(
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/xpu",
            ),
            release_channel=TorchReleaseChannel.STABLE,
            selection_reason="Intel installs use Comfy's recommended stable XPU path.",
            stability="stable",
            validation_expected=AcceleratorClass.INTEL_XPU,
            fallback_backend_key="xpu_nightly",
            fallback_install_arguments=(
                "--pre",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/nightly/xpu",
            ),
            fallback_release_channel=TorchReleaseChannel.NIGHTLY,
            fallback_selection_reason=(
                "Substitute is trying Comfy's optional XPU nightly path after the "
                "stable path failed."
            ),
        )
    if target is ManagedInstallTarget.MACOS_APPLE_SILICON:
        if edge:
            return TorchBackendPolicy(
                backend_key="mps_nightly",
                install_arguments=(
                    "--pre",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/nightly/cpu",
                ),
                release_channel=TorchReleaseChannel.NIGHTLY,
                selection_reason="Nightly MPS torch was requested explicitly.",
                stability="experimental",
                validation_expected=AcceleratorClass.APPLE_MPS,
                fallback_backend_key="mps",
                fallback_install_arguments=("torch", "torchvision", "torchaudio"),
                fallback_release_channel=TorchReleaseChannel.STABLE,
                fallback_selection_reason=(
                    "Substitute is using Comfy Desktop's stable MPS path after the "
                    "requested nightly path failed."
                ),
            )
        return TorchBackendPolicy(
            backend_key="mps",
            install_arguments=("torch", "torchvision", "torchaudio"),
            release_channel=TorchReleaseChannel.STABLE,
            selection_reason=(
                "Apple Silicon installs use Comfy Desktop's verified stable MPS "
                "environment."
            ),
            stability="stable",
            validation_expected=AcceleratorClass.APPLE_MPS,
            fallback_backend_key="mps_nightly",
            fallback_install_arguments=(
                "--pre",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                "https://download.pytorch.org/whl/nightly/cpu",
            ),
            fallback_release_channel=TorchReleaseChannel.NIGHTLY,
            fallback_selection_reason=(
                "Substitute is trying ComfyUI's MPS nightly path after the stable "
                "environment failed."
            ),
        )
    return TorchBackendPolicy(
        backend_key="cpu",
        install_arguments=(
            "torch",
            "torchvision",
            "torchaudio",
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
        ),
        release_channel=TorchReleaseChannel.STABLE,
        selection_reason="CPU installs use the stable torch wheels.",
        stability="stable",
        validation_expected=AcceleratorClass.CPU,
    )


def _windows_amd_index_url(generation_hint: str | None) -> str:
    """Return the README-matched ROCm nightly index for Windows AMD support."""

    normalized = (generation_hint or "").strip().lower()
    if "gfx120" in normalized or "rdna4" in normalized or "rx 90" in normalized:
        return "https://rocm.nightlies.amd.com/v2/gfx120X-all/"
    if "gfx1151" in normalized or "strix" in normalized or "ryzen ai max" in normalized:
        return "https://rocm.nightlies.amd.com/v2/gfx1151/"
    return "https://rocm.nightlies.amd.com/v2/gfx110X-all/"


__all__ = ["TorchBackendPolicy", "TorchReleaseChannel", "build_torch_policy"]
