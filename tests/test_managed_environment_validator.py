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

"""Tests for managed Comfy environment validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.managed_environment_validator import (
    validate_managed_environment,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.torch_policy import TorchReleaseChannel


def test_validate_managed_environment_rejects_backend_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Validation should fail when the detected backend does not match the strategy."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.10.0",
                        "cuda": False,
                        "xpu": False,
                        "hip": "7.1",
                    }
                ),
            ),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.NVIDIA,
    )

    assert result.success is False
    assert result.detected_backend == "amd"
    assert result.detected_torch_channel == "stable"


def test_validate_managed_environment_accepts_matching_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Validation should succeed when torch details match the expected backend."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.10.0",
                        "cuda": True,
                        "xpu": False,
                        "hip": None,
                        "device_operation": True,
                        "device_name": "NVIDIA GeForce RTX 5090",
                    }
                ),
            ),
            SimpleNamespace(returncode=0, stdout="help"),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.NVIDIA,
    )

    assert result.success is True
    assert result.detected_backend == "nvidia"
    assert result.detected_torch_channel == "stable"
    assert result.device_name == "NVIDIA GeForce RTX 5090"


def test_validate_managed_environment_rejects_torch_channel_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Validation should fail when the installed torch channel differs from policy."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.11.0",
                        "cuda": True,
                        "xpu": False,
                        "hip": None,
                    }
                ),
            ),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.NVIDIA,
        expected_torch_channel=TorchReleaseChannel.NIGHTLY,
    )

    assert result.success is False
    assert "torch channel validation failed" in result.detail


def test_validate_managed_environment_accepts_apple_mps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Validation should recognize an available Apple Metal backend."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.11.0.dev20260713",
                        "cuda": False,
                        "xpu": False,
                        "mps": True,
                        "hip": None,
                        "device_operation": True,
                    }
                ),
            ),
            SimpleNamespace(returncode=0, stdout="help"),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.APPLE_MPS,
        expected_torch_channel=TorchReleaseChannel.NIGHTLY,
    )

    assert result.success is True
    assert result.detected_backend == "apple_mps"


def test_validate_managed_environment_identifies_rocm_before_cuda(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ROCm must win over its CUDA-compatible torch API surface."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.10.0+rocm7.1",
                        "cuda": True,
                        "xpu": False,
                        "mps": False,
                        "hip": "7.1",
                        "device_operation": True,
                    }
                ),
            ),
            SimpleNamespace(returncode=0, stdout="help"),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.AMD,
    )

    assert result.success is True
    assert result.detected_backend == "amd"


def test_validate_managed_environment_rejects_failed_device_operation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Backend availability alone must not pass when device execution fails."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    responses = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "torch_version": "2.10.0+cu130",
                        "cuda": True,
                        "xpu": False,
                        "mps": False,
                        "hip": None,
                        "device_operation": False,
                        "device_error": "CUDA driver is too old",
                    }
                ),
            ),
            SimpleNamespace(returncode=0, stdout="help"),
        )
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_environment_validator.run_command",
        lambda *args, **kwargs: next(responses),
    )

    result = validate_managed_environment(
        workspace=tmp_path,
        expected_accelerator=AcceleratorClass.NVIDIA,
    )

    assert result.success is False
    assert "device operation" in result.detail
