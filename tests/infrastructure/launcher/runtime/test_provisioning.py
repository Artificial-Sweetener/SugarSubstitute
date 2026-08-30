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

"""Qualify managed launcher runtime provisioning and platform policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import LINUX_X64, WINDOWS_X64
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.runtime_policy import (
    DEFAULT_PYTHON_VERSION,
    runtime_environment,
    runtime_requirements_command,
)
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider
from sugarsubstitute_shared.windows_long_paths import subprocess_path

from tests.infrastructure.launcher.runtime.support import (
    RecordingRuntimeRunner,
    write_file,
)


def test_uv_runtime_provisioner_builds_managed_runtime_commands(tmp_path: Path) -> None:
    """Runtime provisioning uses uv-managed Python under the install root."""

    layout = InstallLayout.from_root(tmp_path / "install")
    write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / layout.target.uv_executable_name
    bundled_uv.write_bytes(b"uv")
    runner = RecordingRuntimeRunner()

    result = UvManagedRuntimeInstaller(
        uv_provider=VerifiedUvExecutableProvider(bundled_uv_path=bundled_uv),
        runner=runner,
    ).provision(layout=layout)

    uv_executable = layout.uv_executable
    assert uv_executable.read_bytes() == b"uv"
    assert result.python_executable == layout.runtime_python
    assert result.requirements_path == layout.app_dir / "requirements.txt"
    python_install_command = [
        subprocess_path(uv_executable),
        "python",
        "install",
        DEFAULT_PYTHON_VERSION,
        "--install-dir",
        subprocess_path(layout.runtime_dir / "python"),
        "--managed-python",
        "--no-bin",
    ]
    if layout.target.operating_system is WINDOWS_X64.operating_system:
        python_install_command.append("--no-registry")
    python_install_command.append("--no-config")
    assert runner.commands == [
        python_install_command,
        [
            subprocess_path(uv_executable),
            "venv",
            subprocess_path(layout.runtime_dir / ".venv"),
            "--python",
            DEFAULT_PYTHON_VERSION,
            "--managed-python",
            "--no-config",
        ],
        runtime_requirements_command(
            uv_executable=uv_executable,
            layout=layout,
            requirements_path=layout.app_dir / "requirements.txt",
        ),
        [
            subprocess_path(layout.runtime_python),
            "-c",
            "import PySide6; import qfluentwidgets; import cutecanvas; import substitute",
        ],
    ]
    assert all(
        environment["UV_PYTHON_INSTALL_DIR"]
        == subprocess_path(layout.runtime_dir / "python")
        for environment in runner.environments
    )
    assert all(
        environment["UV_NO_MODIFY_PATH"] == "1" for environment in runner.environments
    )
    assert all(
        environment["PYTHONPATH"] == subprocess_path(layout.app_dir)
        for environment in runner.environments
    )
    assert all(environment["PYTHONUTF8"] == "1" for environment in runner.environments)
    assert all(
        environment["PYTHONIOENCODING"] == "utf-8:replace"
        for environment in runner.environments
    )


def test_uv_runtime_provisioner_preserves_matching_existing_venv(
    tmp_path: Path,
) -> None:
    """Runtime reconciliation should synchronize rather than recreate a valid venv."""

    layout = InstallLayout.from_root(tmp_path / "install")
    write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")
    write_file(layout.runtime_python, "python")
    write_file(
        layout.runtime_dir / ".venv" / "pyvenv.cfg",
        (f"implementation = CPython\nversion_info = {DEFAULT_PYTHON_VERSION}\n"),
    )
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        uv_provider=VerifiedUvExecutableProvider(bundled_uv_path=bundled_uv),
        runner=runner,
    ).provision(layout=layout)

    assert all(command[1] != "venv" for command in runner.commands)
    assert any(command[1:3] == ["pip", "install"] for command in runner.commands)


def test_uv_runtime_provisioner_rebuilds_invalid_existing_venv(
    tmp_path: Path,
) -> None:
    """Runtime reconciliation should clear an incompatible managed venv."""

    layout = InstallLayout.from_root(tmp_path / "install")
    write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")
    write_file(layout.runtime_dir / ".venv" / "stale.txt", "stale")
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        uv_provider=VerifiedUvExecutableProvider(bundled_uv_path=bundled_uv),
        runner=runner,
    ).provision(layout=layout)

    venv_command = next(command for command in runner.commands if command[1] == "venv")
    assert "--clear" in venv_command


def test_linux_uv_install_disables_global_bin_without_windows_registry_flag(
    tmp_path: Path,
) -> None:
    """Linux suppresses global shims without passing a Windows-only option."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv"
    bundled_uv.write_bytes(b"uv")
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        uv_provider=VerifiedUvExecutableProvider(bundled_uv_path=bundled_uv),
        runner=runner,
    ).provision(layout=layout)

    assert "--no-bin" in runner.commands[0]
    assert "--no-registry" not in runner.commands[0]


def test_runtime_environment_keeps_uv_state_inside_install_root(tmp_path: Path) -> None:
    """uv cache, managed Python, and venv state stay under the install root."""

    layout = InstallLayout.from_root(tmp_path / "install")

    env = runtime_environment(layout=layout)

    assert env["UV_CACHE_DIR"] == subprocess_path(layout.cache_dir / "uv")
    assert env["UV_PYTHON_INSTALL_DIR"] == subprocess_path(
        layout.runtime_dir / "python"
    )
    assert env["VIRTUAL_ENV"] == subprocess_path(layout.runtime_dir / ".venv")
    assert env["UV_NO_MODIFY_PATH"] == "1"
    assert env["PYTHONPATH"] == subprocess_path(layout.app_dir)
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"


def test_runtime_environment_ignores_parent_historical_resolver_cutoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Candidate requirements must not inherit a prior release's index cutoff."""

    monkeypatch.setenv("UV_EXCLUDE_NEWER", "2026-08-12T00:27:36Z")

    env = runtime_environment(layout=InstallLayout.from_root(tmp_path / "install"))

    assert "UV_EXCLUDE_NEWER" not in env


def test_linux_runtime_installs_cpu_pytorch_distributions(tmp_path: Path) -> None:
    """Linux app support avoids downloading CUDA toolkits into the managed runtime."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)

    command = runtime_requirements_command(
        uv_executable=tmp_path / "uv",
        layout=layout,
        requirements_path=layout.app_dir / "requirements.txt",
    )

    assert command[-4:] == [
        "--torch-backend",
        "cpu",
        "-r",
        subprocess_path(layout.app_dir / "requirements.txt"),
    ]


def test_windows_runtime_uses_default_pytorch_distribution_policy(
    tmp_path: Path,
) -> None:
    """Windows retains uv's platform-native PyTorch distribution selection."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)

    command = runtime_requirements_command(
        uv_executable=tmp_path / "uv.exe",
        layout=layout,
        requirements_path=layout.app_dir / "requirements.txt",
    )

    assert "--torch-backend" not in command
