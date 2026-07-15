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

"""Tests for managed install target and torch policy selection."""

from __future__ import annotations

import subprocess

import pytest

from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionUnavailableError,
)
from substitute.infrastructure.comfy import (
    install_strategy,
    managed_runtime_selection_policy,
    python_policy,
)
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.install_strategy import select_install_strategy
from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.managed_runtime_selection_policy import (
    HardwareAwareManagedRuntimeSelectionPolicy,
)
from substitute.infrastructure.comfy.python_policy import PythonRuntimeSelection
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)


def _tooling() -> HardwareToolingAvailability:
    """Build a neutral tooling-availability record for strategy tests."""

    return HardwareToolingAvailability(
        nvidia_smi=False,
        amd_tooling=False,
        intel_xpu_tooling=False,
    )


@pytest.fixture(autouse=True)
def _use_deterministic_python_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep strategy unit tests independent of host interpreter discovery."""

    monkeypatch.setattr(
        install_strategy,
        "resolve_python_runtime",
        lambda: PythonRuntimeSelection(
            executable="python",
            selected_version="3.13",
            used_fallback=False,
        ),
    )


def test_python_probe_treats_timeout_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stalled optional interpreter probe should permit policy fallback."""

    def _time_out(*_args: object, **_kwargs: object) -> object:
        """Simulate a Python launcher that does not answer promptly."""

        raise subprocess.TimeoutExpired(["py", "-3.13"], timeout=5)

    monkeypatch.setattr(subprocess, "run", _time_out)

    assert python_policy._resolve_windows_py_launcher("3.13") is None


def test_select_install_strategy_chooses_windows_nvidia() -> None:
    """Windows NVIDIA detection should default to recommended stable CUDA torch."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.WINDOWS,
            adapters=(
                HardwareAdapterInfo(
                    name="NVIDIA GeForce RTX 5090",
                    accelerator_class=AcceleratorClass.NVIDIA,
                    generation_hint="blackwell",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.WINDOWS_NVIDIA
    assert result.torch_policy.backend_key == "cuda_cu130"
    assert "--extra-index-url" in result.torch_policy.install_arguments
    assert result.torch_policy.fallback_backend_key == "cuda_nightly_cu132"
    assert result.stability == "stable"
    assert result.torch_policy.stability == "stable"
    assert result.standalone_variant is StandaloneVariantId.WINDOWS_NVIDIA


def test_select_install_strategy_falls_back_to_windows_cpu_for_unsupported_amd() -> (
    None
):
    """Windows AMD detection should fall back to CPU when the README path is unsafe."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.WINDOWS,
            adapters=(
                HardwareAdapterInfo(
                    name="Radeon RX 6800 XT",
                    accelerator_class=AcceleratorClass.AMD,
                    generation_hint="rdna2",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.WINDOWS_CPU
    assert "falling back to CPU" in result.summary_reason


def test_windows_amd_policy_uses_the_preferred_adapter_generation() -> None:
    """Mixed-GPU policy must inspect the selected AMD adapter, not enumeration order."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.WINDOWS,
            adapters=(
                HardwareAdapterInfo(
                    name="Intel(R) UHD Graphics 770",
                    accelerator_class=AcceleratorClass.CPU,
                    is_discrete=False,
                ),
                HardwareAdapterInfo(
                    name="AMD Radeon RX 7900 XTX",
                    accelerator_class=AcceleratorClass.AMD,
                    generation_hint="rdna3",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.WINDOWS_AMD
    assert result.standalone_variant is StandaloneVariantId.WINDOWS_AMD
    assert result.torch_policy.fallback_install_arguments is not None
    assert (
        "https://rocm.nightlies.amd.com/v2/gfx110X-all/"
        in result.torch_policy.fallback_install_arguments
    )


def test_select_install_strategy_chooses_linux_intel_xpu() -> None:
    """Linux Intel Arc detection should default to stable XPU torch."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.LINUX,
            adapters=(
                HardwareAdapterInfo(
                    name="Intel Arc A770",
                    accelerator_class=AcceleratorClass.INTEL_XPU,
                    generation_hint="arc",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.LINUX_INTEL_XPU
    assert result.torch_policy.backend_key == "xpu"
    assert result.torch_policy.fallback_backend_key == "xpu_nightly"
    assert result.stability == "stable"
    assert result.torch_policy.stability == "stable"
    assert result.standalone_variant is StandaloneVariantId.LINUX_INTEL_XPU


def test_hardware_policy_reports_linux_without_accelerator_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CPU-only Linux is a deferred managed capability, not an onboarding crash."""

    detection = HardwareDetectionResult(
        platform=ManagedPlatform.LINUX,
        adapters=(),
        tooling=_tooling(),
    )
    monkeypatch.setattr(
        managed_runtime_selection_policy,
        "detect_hardware",
        lambda: detection,
    )

    with pytest.raises(
        ManagedRuntimeSelectionUnavailableError,
        match="requires a published NVIDIA, AMD, or Intel XPU",
    ):
        HardwareAwareManagedRuntimeSelectionPolicy().select_configuration()


def test_select_install_strategy_chooses_linux_amd_stable_rocm() -> None:
    """Linux AMD detection should default to the stable ROCm 7.2 policy."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.LINUX,
            adapters=(
                HardwareAdapterInfo(
                    name="AMD Radeon RX 7900 XTX",
                    accelerator_class=AcceleratorClass.AMD,
                    generation_hint="rdna3",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.LINUX_AMD
    assert result.torch_policy.backend_key == "rocm72"
    assert result.torch_policy.fallback_backend_key == "rocm72_nightly"
    assert result.stability == "stable"
    assert result.torch_policy.stability == "stable"
    assert result.standalone_variant is StandaloneVariantId.LINUX_AMD


def test_select_install_strategy_chooses_apple_silicon_mps() -> None:
    """Apple Silicon detection should select Comfy Desktop's stable MPS bundle."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.MACOS,
            adapters=(
                HardwareAdapterInfo(
                    name="Apple M4 Max",
                    accelerator_class=AcceleratorClass.APPLE_MPS,
                    generation_hint="m4",
                    is_discrete=False,
                ),
            ),
            tooling=_tooling(),
        )
    )

    assert result.target is ManagedInstallTarget.MACOS_APPLE_SILICON
    assert result.torch_policy.backend_key == "mps"
    assert result.torch_policy.validation_expected is AcceleratorClass.APPLE_MPS
    assert result.stability == "stable"
    assert result.standalone_variant is StandaloneVariantId.MACOS_MPS


def test_edge_torch_switches_stable_nvidia_to_comfy_recommended_nightly() -> None:
    """Opting into edge torch should select Comfy's current CUDA nightly path."""

    result = select_install_strategy(
        detection=HardwareDetectionResult(
            platform=ManagedPlatform.LINUX,
            adapters=(
                HardwareAdapterInfo(
                    name="NVIDIA GeForce RTX 5090",
                    accelerator_class=AcceleratorClass.NVIDIA,
                    generation_hint="blackwell",
                    is_discrete=True,
                ),
            ),
            tooling=_tooling(),
        ),
        prefer_edge_torch=True,
    )

    assert result.torch_policy.backend_key == "cuda_nightly_cu132"
    assert result.torch_policy.release_channel.value == "nightly"
    assert result.standalone_variant is None


def test_linux_cpu_is_rejected_without_a_published_standalone_environment() -> None:
    """Linux CPU should not be claimed while Comfy publishes no verified bundle."""

    with pytest.raises(ValueError, match="does not currently publish Linux CPU"):
        select_install_strategy(
            detection=HardwareDetectionResult(
                platform=ManagedPlatform.LINUX,
                adapters=(),
                tooling=_tooling(),
            )
        )
