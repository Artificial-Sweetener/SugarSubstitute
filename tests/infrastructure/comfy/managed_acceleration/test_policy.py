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

"""Tests for managed acceleration compatibility policy selection."""

from __future__ import annotations

from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.managed_acceleration_policy import (
    ManagedAccelerationRuntime,
    managed_acceleration_policy_fingerprint,
    resolve_managed_acceleration_policy,
)


def test_windows_blackwell_policy_selects_complete_verified_stack() -> None:
    """Windows Blackwell should receive every verified SeedVR2 accelerator."""

    policy = resolve_managed_acceleration_policy(
        detection=_detection(ManagedPlatform.WINDOWS, "blackwell"),
        runtime=_runtime(machine="amd64", capability=(12, 0)),
    )

    assert tuple(package.distribution_name for package in policy.packages) == (
        "transformers",
        "triton-windows",
        "sageattention",
        "flash-attn",
    )
    assert policy.packages[0].required is True
    assert all(package.required is False for package in policy.packages[1:])
    assert "sha256=2262bf" in " ".join(policy.packages[2].install_arguments)
    assert "sha256=86a7e6" in " ".join(policy.packages[3].install_arguments)


def test_windows_ada_policy_omits_flash_attention_three() -> None:
    """Ada receives Triton and Sage without an incompatible FA3 wheel."""

    policy = resolve_managed_acceleration_policy(
        detection=_detection(ManagedPlatform.WINDOWS, "ada"),
        runtime=_runtime(machine="amd64", capability=(8, 9)),
    )

    assert tuple(package.distribution_name for package in policy.packages) == (
        "transformers",
        "triton-windows",
        "sageattention",
    )


def test_linux_hopper_policy_uses_linux_triton_and_flash_wheel() -> None:
    """Linux Hopper should use official Triton and a matching FA3 wheel."""

    policy = resolve_managed_acceleration_policy(
        detection=_detection(ManagedPlatform.LINUX, "hopper"),
        runtime=_runtime(machine="x86_64", capability=(9, 0)),
    )

    assert tuple(package.distribution_name for package in policy.packages) == (
        "transformers",
        "triton",
        "flash-attn-3",
    )
    assert "linux_x86_64" in " ".join(policy.packages[-1].install_arguments)


def test_unverified_runtime_keeps_required_seedvr2_compatibility_only() -> None:
    """Unknown native tuples should retain SDPA without speculative wheels."""

    policy = resolve_managed_acceleration_policy(
        detection=_detection(ManagedPlatform.MACOS, "apple_silicon"),
        runtime=ManagedAccelerationRuntime(
            python_version="3.13.5",
            machine="arm64",
            torch_version="2.10.0",
            cuda_version=None,
            hip_version=None,
            compute_capability=None,
        ),
    )

    assert tuple(package.distribution_name for package in policy.packages) == (
        "transformers",
    )
    assert policy.fallback_notes


def test_package_constraints_accept_only_the_vetted_runtime_versions() -> None:
    """Native artifact drift should force reconciliation."""

    policy = resolve_managed_acceleration_policy(
        detection=_detection(ManagedPlatform.WINDOWS, "blackwell"),
        runtime=_runtime(machine="amd64", capability=(12, 0)),
    )
    by_name = {package.distribution_name: package for package in policy.packages}

    assert by_name["transformers"].accepts_version("5.10.1")
    assert by_name["transformers"].accepts_version("5.14.0")
    assert not by_name["transformers"].accepts_version("5.8.0")
    assert not by_name["transformers"].accepts_version("6.0.0")
    assert by_name["triton-windows"].accepts_version("3.6.0.post26")
    assert not by_name["triton-windows"].accepts_version("3.7.0.post26")


def test_policy_fingerprint_is_stable_and_covers_native_artifacts() -> None:
    """Setup freshness should derive from the complete compatibility manifest."""

    fingerprint = managed_acceleration_policy_fingerprint()

    assert len(fingerprint) == 64
    assert fingerprint == managed_acceleration_policy_fingerprint()


def _detection(
    platform: ManagedPlatform,
    generation_hint: str,
) -> HardwareDetectionResult:
    """Build one deterministic NVIDIA hardware detection result."""

    accelerator = (
        AcceleratorClass.APPLE_MPS
        if platform is ManagedPlatform.MACOS
        else AcceleratorClass.NVIDIA
    )
    return HardwareDetectionResult(
        platform=platform,
        adapters=(
            HardwareAdapterInfo(
                name="Test adapter",
                accelerator_class=accelerator,
                generation_hint=generation_hint,
            ),
        ),
        tooling=HardwareToolingAvailability(
            nvidia_smi=accelerator is AcceleratorClass.NVIDIA,
            amd_tooling=False,
            intel_xpu_tooling=False,
        ),
    )


def _runtime(
    *,
    machine: str,
    capability: tuple[int, int],
) -> ManagedAccelerationRuntime:
    """Build the currently verified CUDA runtime tuple."""

    return ManagedAccelerationRuntime(
        python_version="3.13.12",
        machine=machine,
        torch_version="2.10.0+cu130",
        cuda_version="13.0",
        hip_version=None,
        compute_capability=capability,
    )
