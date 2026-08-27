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

"""Qualify bounded historical managed-Comfy materialization."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_setup_cache_storage import (
    prepare_managed_setup_cache,
)
from tools.ci.historical_managed_configuration import (
    _materialize_historical_managed_configuration,
    materialize_historical_managed_configuration,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_timeout_preserves_last_phase_and_owned_process_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stalled nested installer must fail with its final durable phase evidence."""

    observed: dict[str, object] = {}

    def _timeout(command: list[str], **arguments: object) -> object:
        """Capture the child boundary and model an exhausted shared budget."""

        observed["command"] = command
        observed.update(arguments)
        raise subprocess.TimeoutExpired(
            command,
            cast(float, arguments["timeout_seconds"]),
            output=(
                "HISTORICAL_MATERIALIZATION phase=python_environment state=started"
            ),
            stderr="uv child remained active",
        )

    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.run_owned_process",
        _timeout,
    )

    with pytest.raises(InstallerLifecycleError) as captured:
        materialize_historical_managed_configuration(
            repository_root=tmp_path,
            install_root=tmp_path / "installed",
            endpoint_port=48188,
            managed_workspace=tmp_path / "managed-comfy",
            managed_model_root=tmp_path / "models",
            source_repository=tmp_path / "source.git",
            timeout_seconds=55.0,
        )

    command = cast(list[str], observed["command"])
    assert command[:3] == [
        sys.executable,
        "-m",
        "tools.ci.historical_managed_configuration",
    ]
    assert observed["timeout_seconds"] == 55.0
    assert "phase=python_environment state=started" in str(captured.value)
    assert "uv child remained active" in str(captured.value)


def test_existing_runtime_is_converged_before_readiness_is_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical qualification should prove one real existing runtime in order."""

    workspace = tmp_path / "comfyui"
    model_root = tmp_path / "models"
    workspace.mkdir()
    operations: list[str] = []

    def _manager_runtime(*_args: object, **_kwargs: object) -> ComfyManagerRuntime:
        """Record provisioning and return the runtime qualified downstream."""

        operations.append("manager")
        executable = workspace / ("python.exe" if sys.platform == "win32" else "python")
        return ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=executable,
            version="4.1",
        )

    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.ensure_managed_workspace_manager",
        _manager_runtime,
    )
    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.ensure_core_comfy_nodepacks",
        lambda *_args, **_kwargs: operations.append("nodepacks"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.run_sugarcubes_baseline_maintenance",
        lambda *_args, **_kwargs: operations.append("sugarcubes"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.configure_backend_model_root",
        lambda **_kwargs: operations.append("model_root"),
    )

    def _validate(**_kwargs: object) -> ManagedEnvironmentValidationResult:
        """Return real-runtime evidence at the validation boundary."""

        operations.append("validation")
        return ManagedEnvironmentValidationResult(
            success=True,
            detail="Managed workspace validation succeeded.",
            detected_backend="cpu",
            detected_torch_channel="stable",
            torch_version="2.13.0",
            device_name="cpu",
        )

    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.validate_managed_environment",
        _validate,
    )
    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.prepare_checkout",
        lambda *_args, **_kwargs: operations.append("checkout"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_managed_configuration.prepare_environment",
        lambda *_args, **_kwargs: operations.append("environment"),
    )

    install_root = tmp_path / "installed"
    _materialize_historical_managed_configuration(
        repository_root=tmp_path,
        install_root=install_root,
        endpoint_port=48188,
        managed_workspace=workspace,
        managed_model_root=model_root,
        source_repository=tmp_path / "source.git",
    )

    cache = prepare_managed_setup_cache(workspace)
    try:
        payload = json.loads(cache.record_path.read_text(encoding="utf-8"))
    finally:
        cache.close()
    assert payload["success"] is True
    assert payload["key"]["strategy"]["source"] == ("existing_qualification_runtime")
    expected_force_cpu_mode = sys.platform != "darwin"
    assert payload["request"]["force_cpu_mode"] is expected_force_cpu_mode
    assert payload["runtime_configuration"]["force_cpu_mode"] is expected_force_cpu_mode
    assert payload["runtime_configuration"]["validation_status"] == "valid"
    persisted_runtime = json.loads(
        (install_root / "appdata" / "runtime_state" / "managed_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted_runtime["force_cpu_mode"] is expected_force_cpu_mode
    assert (
        persisted_runtime["install_target"].endswith("_cpu") or sys.platform == "darwin"
    )
    assert operations == [
        "checkout",
        "environment",
        "manager",
        "nodepacks",
        "sugarcubes",
        "model_root",
        "validation",
    ]
    assert (install_root / "user" / "settings" / "installation.json").is_file()
    assert (install_root / "user" / "settings" / "runtime.json").is_file()
    target = json.loads(
        (install_root / "user" / "settings" / "comfy_target.json").read_text(
            encoding="utf-8"
        )
    )
    assert target["mode"] == "managed_local"
    assert target["workspace_path"] == str(workspace)
    assert (
        install_root / "launcher" / "logs" / "historical-materialization.log"
    ).read_text(encoding="utf-8").splitlines() == [
        "HISTORICAL_MATERIALIZATION phase=configuration state=started",
        "HISTORICAL_MATERIALIZATION phase=source_checkout state=started",
        "HISTORICAL_MATERIALIZATION phase=source_checkout state=completed",
        "HISTORICAL_MATERIALIZATION phase=python_environment state=started",
        "HISTORICAL_MATERIALIZATION phase=python_environment state=completed",
        "HISTORICAL_MATERIALIZATION phase=manager state=started",
        "HISTORICAL_MATERIALIZATION phase=manager state=completed",
        "HISTORICAL_MATERIALIZATION phase=core_nodepacks state=started",
        "HISTORICAL_MATERIALIZATION phase=core_nodepacks state=completed",
        "HISTORICAL_MATERIALIZATION phase=sugarcubes state=started",
        "HISTORICAL_MATERIALIZATION phase=sugarcubes state=completed",
        "HISTORICAL_MATERIALIZATION phase=model_root state=started",
        "HISTORICAL_MATERIALIZATION phase=model_root state=completed",
        "HISTORICAL_MATERIALIZATION phase=validation state=started",
        "HISTORICAL_MATERIALIZATION phase=validation state=completed",
        "HISTORICAL_MATERIALIZATION phase=configuration state=completed",
    ]
