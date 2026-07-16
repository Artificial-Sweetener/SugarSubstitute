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

"""Select verified package artifacts for managed acceleration runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareDetectionResult,
    ManagedPlatform,
)

_TRANSFORMERS_VERIFICATION = r"""
import importlib.machinery
import sys
import types

stub = types.ModuleType("flash_attn")
stub.__spec__ = importlib.machinery.ModuleSpec("flash_attn", None)
stub.__file__ = None
stub.__path__ = []
sys.modules["flash_attn"] = stub

import transformers
from transformers.utils import is_flash_attn_2_available

is_flash_attn_2_available()
import diffusers
"""
_TRITON_VERIFICATION = "import triton; import triton.language"
_SAGEATTENTION_VERIFICATION = (
    "from sageattention import sageattn_varlen; assert callable(sageattn_varlen)"
)
_FLASH_ATTENTION_3_VERIFICATION = (
    "import flash_attn_interface; "
    "assert callable(flash_attn_interface.flash_attn_varlen_func)"
)
_FLASH_ATTENTION_2_VERIFICATION = r"""
import torch
from flash_attn import flash_attn_varlen_func

q = torch.randn(16, 4, 64, device="cuda", dtype=torch.float16)
k = torch.randn(16, 4, 64, device="cuda", dtype=torch.float16)
v = torch.randn(16, 4, 64, device="cuda", dtype=torch.float16)
cu_seqlens = torch.tensor([0, 16], device="cuda", dtype=torch.int32)
output = flash_attn_varlen_func(q, k, v, cu_seqlens, cu_seqlens, 16, 16)
assert output.shape == q.shape
assert torch.isfinite(output).all()
"""

_SAGEATTENTION_WINDOWS_URL = (
    "https://github.com/woct0rdho/SageAttention/releases/download/"
    "v2.2.0-windows.post5/"
    "sageattention-2.2.0%2Bcu130torch2.10.0andhigher.post5-"
    "cp310-abi3-win_amd64.whl"
    "#sha256=2262bfebb5466a4ed979613bd24ba674aceacb5fed6b43d8d6e4b847d1742943"
)
_FLASH_ATTENTION_3_RELEASE_ROOT = (
    "https://github.com/windreamer/flash-attention3-wheels/releases/download/"
    "2026.03.19-850211f/"
)
_FLASH_ATTENTION_3_VERSION = "3.0.0+20260318.cu130torch2100cxx11abitrue.8afc61"
_FLASH_ATTENTION_2_VERSION = "2.8.3"
_FLASH_ATTENTION_2_WINDOWS_PY313_URL = (
    "https://github.com/johnarizona/flash-attn2-wheels/releases/download/0.1.0/"
    "flash_attn-2.8.3%2Bcu131torch2.10.0cx11abiTRUE-cp313-cp313-win_amd64.whl"
    "#sha256=86a7e6369e038fca652c9c8579375390882ec7644c32e79df557a242ad88d137"
)
_FLASH_ATTENTION_2_WINDOWS_PY312_URL = (
    "https://github.com/johnarizona/flash-attn2-wheels/releases/download/0.1.0/"
    "flash_attn-2.8.3%2Bcu13torch2.10.0cx11abiTRUE-cp312-cp312-win_amd64.whl"
    "#sha256=8bf1383517b34691f63ee6e7576fe69c858eda59e2c8f06c2fb2490ac6a93d47"
)
_FLASH_ATTENTION_3_LINUX_X64_URL = (
    f"{_FLASH_ATTENTION_3_RELEASE_ROOT}"
    "flash_attn_3-3.0.0%2B20260318.cu130torch2100cxx11abitrue.8afc61-"
    "cp39-abi3-linux_x86_64.whl"
    "#sha256=632763af4cd55b35e6bbd0e467a445035fb8d376783bfa436c66dda79684fcd1"
)
_FLASH_ATTENTION_3_LINUX_ARM64_URL = (
    f"{_FLASH_ATTENTION_3_RELEASE_ROOT}"
    "flash_attn_3-3.0.0%2B20260318.cu130torch2100cxx11abitrue.8afc61-"
    "cp39-abi3-linux_aarch64.whl"
    "#sha256=cd278ff6365048e7e58df459b6e06699bb8127db56aedb74740ec523ca80794c"
)


@dataclass(frozen=True)
class ManagedAccelerationRuntime:
    """Describe the ABI and device facts that constrain native wheels."""

    python_version: str
    machine: str
    torch_version: str
    cuda_version: str | None
    hip_version: str | None
    compute_capability: tuple[int, int] | None


@dataclass(frozen=True)
class ManagedPackageVersion:
    """Accept one exact version or one bounded numeric release range."""

    exact_version: str | None = None
    minimum_release: tuple[int, int, int] | None = None
    maximum_exclusive: tuple[int, int, int] | None = None

    def accepts(self, installed_version: str | None) -> bool:
        """Return whether an installed distribution satisfies this policy."""

        if installed_version is None:
            return False
        if self.exact_version is not None:
            return installed_version.lower() == self.exact_version.lower()
        release = _release_tuple(installed_version)
        if release is None:
            return False
        if self.minimum_release is not None and release < self.minimum_release:
            return False
        return not (
            self.maximum_exclusive is not None and release >= self.maximum_exclusive
        )

    def fingerprint_payload(self) -> dict[str, object]:
        """Return deterministic policy fields for managed setup freshness."""

        return {
            "exact": self.exact_version,
            "minimum": self.minimum_release,
            "maximum_exclusive": self.maximum_exclusive,
        }


@dataclass(frozen=True)
class ManagedAccelerationPackage:
    """Describe one managed Python package and its post-install verification."""

    distribution_name: str
    display_name: str
    version: ManagedPackageVersion
    install_arguments: tuple[str, ...]
    verification_code: str
    required: bool
    conflicting_distributions: tuple[str, ...] = ()

    def accepts_version(self, installed_version: str | None) -> bool:
        """Return whether the supplied installed version is ready for verification."""

        return self.version.accepts(installed_version)

    def fingerprint_payload(self) -> dict[str, object]:
        """Return stable package fields that affect environment compatibility."""

        return {
            "distribution": self.distribution_name,
            "display_name": self.display_name,
            "version": self.version.fingerprint_payload(),
            "install_arguments": self.install_arguments,
            "verification_code": self.verification_code,
            "required": self.required,
            "conflicting_distributions": self.conflicting_distributions,
        }


@dataclass(frozen=True)
class ManagedAccelerationPolicy:
    """Describe every package selected for one managed runtime tuple."""

    packages: tuple[ManagedAccelerationPackage, ...]
    fallback_notes: tuple[str, ...]


def resolve_managed_acceleration_policy(
    *,
    detection: HardwareDetectionResult,
    runtime: ManagedAccelerationRuntime,
) -> ManagedAccelerationPolicy:
    """Return only artifacts verified for the detected managed runtime."""

    packages = [_transformers_package()]
    fallback_notes: list[str] = []
    if not _supports_native_cuda_stack(detection=detection, runtime=runtime):
        fallback_notes.append(
            "PyTorch SDPA remains active because this runtime has no verified native "
            "acceleration artifact tuple."
        )
        return ManagedAccelerationPolicy(
            packages=tuple(packages),
            fallback_notes=tuple(fallback_notes),
        )

    if detection.platform is ManagedPlatform.WINDOWS:
        packages.extend((_windows_triton_package(), _windows_sageattention_package()))
        flash_package = _windows_flash_attention_package(runtime)
        if flash_package is not None:
            packages.append(flash_package)
        else:
            fallback_notes.append(
                "Flash Attention requires a verified Blackwell and Python wheel tuple; "
                "SeedVR2 will use SageAttention or PyTorch SDPA."
            )
    elif detection.platform is ManagedPlatform.LINUX:
        packages.append(_linux_triton_package())
        flash_url = _linux_flash_attention_url(runtime.machine)
        if flash_url is not None and _supports_flash_attention_three(
            runtime.compute_capability
        ):
            packages.append(_flash_attention_three_package(flash_url))
        else:
            fallback_notes.append(
                "No verified Flash Attention 3 wheel matches this Linux machine and "
                "GPU tuple; PyTorch SDPA remains available."
            )
        fallback_notes.append(
            "SageAttention 2 remains on SDPA fallback until a reproducible managed "
            "Linux wheel is available for this Torch ABI."
        )
    return ManagedAccelerationPolicy(
        packages=tuple(packages),
        fallback_notes=tuple(fallback_notes),
    )


def managed_acceleration_policy_fingerprint() -> str:
    """Return a content-derived freshness key for every managed artifact rule."""

    manifest = {
        "runtime_tuple": {
            "python_minimum": (3, 10, 0),
            "torch_release": (2, 10, 0),
            "cuda_release": (13, 0, 0),
            "minimum_compute_capability": (8, 0),
            "flash_attention_2_compute_capabilities": ((12, 0),),
            "flash_attention_3_compute_capabilities": ((9, 0),),
        },
        "packages": [
            package.fingerprint_payload()
            for package in (
                _transformers_package(),
                _windows_triton_package(),
                _windows_sageattention_package(),
                _linux_triton_package(),
                _flash_attention_two_package(_FLASH_ATTENTION_2_WINDOWS_PY313_URL),
                _flash_attention_two_package(_FLASH_ATTENTION_2_WINDOWS_PY312_URL),
                _flash_attention_three_package(_FLASH_ATTENTION_3_LINUX_X64_URL),
                _flash_attention_three_package(_FLASH_ATTENTION_3_LINUX_ARM64_URL),
            )
        ],
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _transformers_package() -> ManagedAccelerationPackage:
    """Return the required SeedVR2 Flash Attention fallback repair."""

    return ManagedAccelerationPackage(
        distribution_name="transformers",
        display_name="Transformers compatibility",
        version=ManagedPackageVersion(
            minimum_release=(5, 10, 1),
            maximum_exclusive=(6, 0, 0),
        ),
        install_arguments=("--upgrade", "transformers>=5.10.1,<6"),
        verification_code=_TRANSFORMERS_VERIFICATION,
        required=True,
    )


def _windows_triton_package() -> ManagedAccelerationPackage:
    """Return Triton matched to PyTorch 2.10 on Windows."""

    return ManagedAccelerationPackage(
        distribution_name="triton-windows",
        display_name="Triton",
        version=ManagedPackageVersion(exact_version="3.6.0.post26"),
        install_arguments=(
            "--upgrade",
            "--no-deps",
            "triton-windows==3.6.0.post26",
        ),
        verification_code=_TRITON_VERIFICATION,
        required=False,
        conflicting_distributions=("triton",),
    )


def _linux_triton_package() -> ManagedAccelerationPackage:
    """Return Triton matched to PyTorch 2.10 on Linux."""

    return ManagedAccelerationPackage(
        distribution_name="triton",
        display_name="Triton",
        version=ManagedPackageVersion(exact_version="3.6.0"),
        install_arguments=("--upgrade", "--no-deps", "triton==3.6.0"),
        verification_code=_TRITON_VERIFICATION,
        required=False,
        conflicting_distributions=("triton-windows",),
    )


def _windows_sageattention_package() -> ManagedAccelerationPackage:
    """Return the attested Windows SageAttention ABI3 artifact."""

    return ManagedAccelerationPackage(
        distribution_name="sageattention",
        display_name="SageAttention",
        version=ManagedPackageVersion(
            exact_version="2.2.0+cu130torch2.10.0andhigher.post5"
        ),
        install_arguments=("--upgrade", "--no-deps", _SAGEATTENTION_WINDOWS_URL),
        verification_code=_SAGEATTENTION_VERIFICATION,
        required=False,
    )


def _flash_attention_three_package(url: str) -> ManagedAccelerationPackage:
    """Return one platform-specific Flash Attention 3 artifact."""

    return ManagedAccelerationPackage(
        distribution_name="flash-attn-3",
        display_name="Flash Attention 3",
        version=ManagedPackageVersion(exact_version=_FLASH_ATTENTION_3_VERSION),
        install_arguments=("--upgrade", "--no-deps", url),
        verification_code=_FLASH_ATTENTION_3_VERIFICATION,
        required=False,
    )


def _flash_attention_two_package(url: str) -> ManagedAccelerationPackage:
    """Return one checksum-pinned Windows Flash Attention 2 artifact."""

    return ManagedAccelerationPackage(
        distribution_name="flash-attn",
        display_name="Flash Attention 2",
        version=ManagedPackageVersion(exact_version=_FLASH_ATTENTION_2_VERSION),
        install_arguments=("--upgrade", "--no-deps", url),
        verification_code=_FLASH_ATTENTION_2_VERIFICATION,
        required=False,
        conflicting_distributions=("flash-attn-3",),
    )


def _windows_flash_attention_package(
    runtime: ManagedAccelerationRuntime,
) -> ManagedAccelerationPackage | None:
    """Return the Blackwell artifact matching the workspace Python ABI."""

    capability = runtime.compute_capability
    if capability is None or capability[0] != 12:
        return None
    python_release = _release_tuple(runtime.python_version)
    if python_release is None:
        return None
    if python_release[:2] == (3, 13):
        return _flash_attention_two_package(_FLASH_ATTENTION_2_WINDOWS_PY313_URL)
    if python_release[:2] == (3, 12):
        return _flash_attention_two_package(_FLASH_ATTENTION_2_WINDOWS_PY312_URL)
    return None


def _supports_native_cuda_stack(
    *,
    detection: HardwareDetectionResult,
    runtime: ManagedAccelerationRuntime,
) -> bool:
    """Return whether the runtime matches the currently verified CUDA wheel set."""

    if detection.preferred_accelerator is not AcceleratorClass.NVIDIA:
        return False
    if detection.platform not in {ManagedPlatform.WINDOWS, ManagedPlatform.LINUX}:
        return False
    python_release = _release_tuple(runtime.python_version)
    torch_release = _release_tuple(runtime.torch_version)
    cuda_release = _release_tuple(runtime.cuda_version or "")
    capability = runtime.compute_capability
    return bool(
        python_release is not None
        and python_release >= (3, 10, 0)
        and torch_release is not None
        and torch_release[:2] == (2, 10)
        and cuda_release is not None
        and cuda_release[:2] == (13, 0)
        and runtime.hip_version is None
        and capability is not None
        and capability >= (8, 0)
    )


def _supports_flash_attention_three(
    compute_capability: tuple[int, int] | None,
) -> bool:
    """Return whether FA3 supports this managed NVIDIA architecture."""

    if compute_capability is None:
        return False
    return compute_capability[0] == 9


def _linux_flash_attention_url(machine: str) -> str | None:
    """Return the pinned Linux artifact for one normalized machine name."""

    normalized = machine.strip().lower()
    if normalized in {"amd64", "x86_64"}:
        return _FLASH_ATTENTION_3_LINUX_X64_URL
    if normalized in {"arm64", "aarch64"}:
        return _FLASH_ATTENTION_3_LINUX_ARM64_URL
    return None


def _release_tuple(value: str) -> tuple[int, int, int] | None:
    """Parse the leading three numeric PEP 440 release components."""

    match = re.match(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor or 0), int(patch or 0)


__all__ = [
    "ManagedAccelerationPackage",
    "ManagedAccelerationPolicy",
    "ManagedAccelerationRuntime",
    "ManagedPackageVersion",
    "managed_acceleration_policy_fingerprint",
    "resolve_managed_acceleration_policy",
]
