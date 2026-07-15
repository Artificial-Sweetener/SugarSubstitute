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

"""Tests for managed Comfy hardware detection normalization."""

from __future__ import annotations

import json
import subprocess
import shutil
import sys

import pytest

from substitute.infrastructure.comfy import (
    hardware_detection,
    hardware_linux,
    hardware_macos,
    hardware_windows,
)
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.intel_xpu_detection import (
    _adapters_from_xpu_smi_output,
)


def test_detect_windows_hardware_prefers_nvidia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows detection should prefer NVIDIA over lower-priority adapters."""

    monkeypatch.setattr(
        hardware_windows,
        "_read_windows_adapters",
        lambda: [
            HardwareAdapterInfo(
                name="Intel(R) UHD Graphics 770",
                accelerator_class=AcceleratorClass.CPU,
                is_discrete=False,
            ),
            HardwareAdapterInfo(
                name="NVIDIA GeForce RTX 5090",
                accelerator_class=AcceleratorClass.NVIDIA,
                is_discrete=True,
            ),
        ],
    )

    result = hardware_windows.detect_windows_hardware()

    assert result.platform is ManagedPlatform.WINDOWS
    assert result.preferred_accelerator is AcceleratorClass.NVIDIA
    assert result.selected_adapter is not None
    assert result.selected_adapter.name == "NVIDIA GeForce RTX 5090"


def test_windows_detection_does_not_treat_uhd_pci_id_as_arc() -> None:
    """An Intel UHD device ID beginning with A7 must not imply Arc support."""

    adapters = hardware_windows._parse_windows_adapter_json(
        json.dumps(
            {
                "Name": "Intel(R) UHD Graphics 770",
                "PNPDeviceID": (
                    "PCI\\VEN_8086&DEV_A780&SUBSYS_88821043&REV_04\\3&11583659&0&10"
                ),
                "AdapterCompatibility": "Intel Corporation",
            }
        )
    )

    assert adapters[0].accelerator_class is AcceleratorClass.CPU


def test_windows_detection_recognizes_arc_by_adapter_identity() -> None:
    """An adapter explicitly identified as Intel Arc should select XPU."""

    adapters = hardware_windows._parse_windows_adapter_json(
        json.dumps(
            {
                "Name": "Intel(R) Arc(TM) A770 Graphics",
                "PNPDeviceID": "PCI\\VEN_8086&DEV_56A0",
                "AdapterCompatibility": "Intel Corporation",
            }
        )
    )

    assert adapters[0].accelerator_class is AcceleratorClass.INTEL_XPU
    assert adapters[0].generation_hint == "intel_xpu"


def test_windows_detection_recovers_nvidia_when_cim_has_no_nvidia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vendor tooling should recover NVIDIA when CIM omits the adapter."""

    expected = HardwareAdapterInfo(
        name="NVIDIA GeForce RTX 5090",
        accelerator_class=AcceleratorClass.NVIDIA,
        generation_hint="blackwell",
        is_discrete=True,
    )
    monkeypatch.setattr(hardware_windows, "_read_windows_cim_adapters", lambda: [])
    monkeypatch.setattr(
        hardware_windows,
        "read_nvidia_smi_adapters",
        lambda: [expected],
    )

    assert hardware_windows._read_windows_adapters() == [expected]


def test_detect_linux_hardware_falls_back_to_cpu_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux detection should select CPU when no adapters are discovered."""

    monkeypatch.setattr(hardware_linux, "_parse_lspci_output", lambda: [])
    monkeypatch.setattr(hardware_linux, "_parse_sysfs_drm", lambda: [])
    monkeypatch.setattr(hardware_linux, "_parse_nvidia_smi_output", lambda: [])
    monkeypatch.setattr(hardware_linux, "read_intel_xpu_adapters", lambda: [])

    result = hardware_linux.detect_linux_hardware()

    assert result.platform is ManagedPlatform.LINUX
    assert result.preferred_accelerator is AcceleratorClass.CPU


def test_detect_linux_hardware_uses_nvidia_smi_without_pci_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WSL should detect NVIDIA hardware even without lspci or DRM adapters."""

    monkeypatch.setattr(hardware_linux, "_parse_lspci_output", lambda: [])
    monkeypatch.setattr(hardware_linux, "_parse_sysfs_drm", lambda: [])
    monkeypatch.setattr(
        shutil,
        "which",
        lambda command: (
            "/usr/lib/wsl/lib/nvidia-smi" if command == "nvidia-smi" else None
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=0,
            stdout="NVIDIA GeForce RTX 5090\n",
            stderr="",
        ),
    )

    result = hardware_linux.detect_linux_hardware()

    assert result.preferred_accelerator is AcceleratorClass.NVIDIA
    assert result.adapters[0].name == "NVIDIA GeForce RTX 5090"
    assert result.adapters[0].generation_hint == "blackwell"
    assert result.tooling.nvidia_smi is True


def test_linux_sysfs_does_not_assume_every_intel_gpu_supports_xpu() -> None:
    """A generic Intel PCI vendor ID must not claim an XPU-capable GPU."""

    assert hardware_linux._accelerator_for_vendor_id("8086") is AcceleratorClass.CPU


def test_linux_pci_recognizes_explicit_intel_arc_identity() -> None:
    """Linux PCI names that explicitly identify Arc should select XPU."""

    line = "Intel Corporation Arc A770 Graphics [8086:56a0]"

    assert (
        hardware_linux._accelerator_for_linux_line(line.lower())
        is AcceleratorClass.INTEL_XPU
    )


def test_intel_xpu_tooling_proves_compute_capability_from_json() -> None:
    """XPU Manager discovery should recover a supported Intel compute GPU."""

    adapters = _adapters_from_xpu_smi_output(
        json.dumps(
            {
                "device_list": [
                    {
                        "device_id": 0,
                        "device_name": "Intel(R) Arc(TM) A770 Graphics",
                    }
                ]
            }
        )
    )

    assert len(adapters) == 1
    assert adapters[0].accelerator_class is AcceleratorClass.INTEL_XPU
    assert adapters[0].name == "Intel(R) Arc(TM) A770 Graphics"


def test_detect_hardware_routes_by_current_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platform routing should delegate to the correct hardware detector."""

    monkeypatch.setattr(sys, "platform", "win32")
    expected = HardwareDetectionResult(
        platform=ManagedPlatform.WINDOWS,
        adapters=(
            HardwareAdapterInfo(
                name="NVIDIA GeForce RTX 5090",
                accelerator_class=AcceleratorClass.NVIDIA,
                is_discrete=True,
            ),
        ),
        tooling=HardwareToolingAvailability(
            nvidia_smi=True,
            amd_tooling=False,
            intel_xpu_tooling=False,
        ),
    )
    monkeypatch.setattr(
        hardware_detection,
        "detect_windows_hardware",
        lambda: expected,
    )

    result = hardware_detection.detect_hardware()

    assert result == expected


def test_detect_macos_hardware_selects_apple_silicon_mps() -> None:
    """Apple ARM hardware should normalize to the MPS accelerator class."""

    result = hardware_macos.detect_macos_hardware(machine="arm64", processor="arm")

    assert result.platform is ManagedPlatform.MACOS
    assert result.preferred_accelerator is AcceleratorClass.APPLE_MPS
    assert result.adapters[0].name == "Apple Silicon"


def test_detect_macos_hardware_fails_closed_on_intel() -> None:
    """Intel Macs should be rejected because the packaged target is Apple Silicon."""

    with pytest.raises(hardware_macos.UnsupportedMacHardwareError):
        hardware_macos.detect_macos_hardware(machine="x86_64", processor="i386")
