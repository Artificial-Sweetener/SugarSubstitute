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

"""Tests for launcher-managed runtime provisioning."""

from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset
from launcher.sugarsubstitute_launcher.platforms import LINUX_X64, WINDOWS_X64
from launcher.sugarsubstitute_launcher.runtime import (
    DEFAULT_PYTHON_VERSION,
    RuntimeProvisioningError,
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
    runtime_environment,
    runtime_requirements_command,
)


class RecordingRuntimeRunner:
    """Record runtime provisioning commands without executing them."""

    def __init__(self) -> None:
        """Initialize empty command capture."""

        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Record one command invocation."""

        self.commands.append(list(command))
        self.environments.append(dict(env))


def test_uv_runtime_provisioner_builds_managed_runtime_commands(tmp_path: Path) -> None:
    """Runtime provisioning uses uv-managed Python under the install root."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / layout.target.uv_executable_name
    bundled_uv.write_bytes(b"uv")
    runner = RecordingRuntimeRunner()

    result = UvManagedRuntimeInstaller(
        bundled_uv_path=bundled_uv,
        runner=runner,
    ).provision(layout=layout)

    uv_executable = layout.uv_executable
    assert uv_executable.read_bytes() == b"uv"
    assert result.python_executable == layout.runtime_python
    assert result.requirements_path == layout.app_dir / "requirements.txt"
    python_install_command = [
        str(uv_executable),
        "python",
        "install",
        DEFAULT_PYTHON_VERSION,
        "--install-dir",
        str(layout.runtime_dir / "python"),
        "--managed-python",
        "--no-bin",
    ]
    if layout.target.operating_system is WINDOWS_X64.operating_system:
        python_install_command.append("--no-registry")
    python_install_command.append("--no-config")
    assert runner.commands == [
        python_install_command,
        [
            str(uv_executable),
            "venv",
            str(layout.runtime_dir / ".venv"),
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
            str(layout.runtime_python),
            "-c",
            "import PySide6; import qfluentwidgets; import qpane; import substitute",
        ],
    ]
    assert all(
        environment["UV_PYTHON_INSTALL_DIR"] == str(layout.runtime_dir / "python")
        for environment in runner.environments
    )
    assert all(
        environment["UV_NO_MODIFY_PATH"] == "1" for environment in runner.environments
    )
    assert all(
        environment["PYTHONPATH"] == str(layout.app_dir)
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
    _write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")
    _write_file(layout.runtime_python, "python")
    _write_file(
        layout.runtime_dir / ".venv" / "pyvenv.cfg",
        (f"implementation = CPython\nversion_info = {DEFAULT_PYTHON_VERSION}\n"),
    )
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        bundled_uv_path=bundled_uv,
        runner=runner,
    ).provision(layout=layout)

    assert all(command[1] != "venv" for command in runner.commands)
    assert any(command[1:3] == ["pip", "install"] for command in runner.commands)


def test_uv_runtime_provisioner_rebuilds_invalid_existing_venv(
    tmp_path: Path,
) -> None:
    """Runtime reconciliation should clear an incompatible managed venv."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")
    _write_file(layout.runtime_dir / ".venv" / "stale.txt", "stale")
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        bundled_uv_path=bundled_uv,
        runner=runner,
    ).provision(layout=layout)

    venv_command = next(command for command in runner.commands if command[1] == "venv")
    assert "--clear" in venv_command


def test_linux_uv_install_disables_global_bin_without_windows_registry_flag(
    tmp_path: Path,
) -> None:
    """Linux suppresses global shims without passing a Windows-only option."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    _write_file(layout.app_dir / "requirements.txt", "PySide6\n")
    bundled_uv = tmp_path / "uv"
    bundled_uv.write_bytes(b"uv")
    runner = RecordingRuntimeRunner()

    UvManagedRuntimeInstaller(
        bundled_uv_path=bundled_uv,
        runner=runner,
    ).provision(layout=layout)

    assert "--no-bin" in runner.commands[0]
    assert "--no-registry" not in runner.commands[0]


def test_runtime_environment_keeps_uv_state_inside_install_root(tmp_path: Path) -> None:
    """uv cache, managed Python, and venv state stay under the install root."""

    layout = InstallLayout.from_root(tmp_path / "install")

    env = runtime_environment(layout=layout)

    assert env["UV_CACHE_DIR"] == str(layout.cache_dir / "uv")
    assert env["UV_PYTHON_INSTALL_DIR"] == str(layout.runtime_dir / "python")
    assert env["VIRTUAL_ENV"] == str(layout.runtime_dir / ".venv")
    assert env["UV_NO_MODIFY_PATH"] == "1"
    assert env["PYTHONPATH"] == str(layout.app_dir)
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"


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
        str(layout.app_dir / "requirements.txt"),
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


def test_subprocess_runtime_runner_streams_output_without_shell(
    tmp_path: Path,
) -> None:
    """Runtime command output is capturable for the graphical installer log."""

    output_lines: list[str] = []

    SubprocessRuntimeCommandRunner(output_lines.append).run(
        [sys.executable, "-c", "print('runtime line')"],
        cwd=tmp_path,
        env=os.environ,
    )

    assert output_lines == ["runtime line"]


def test_subprocess_runtime_runner_replaces_invalid_output_bytes(
    tmp_path: Path,
) -> None:
    """Runtime command output decoding never depends on the Windows ANSI code page."""

    output_lines: list[str] = []

    SubprocessRuntimeCommandRunner(output_lines.append).run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'bad\\x90byte\\n')",
        ],
        cwd=tmp_path,
        env=os.environ,
    )

    assert output_lines == ["bad\ufffdbyte"]


def test_subprocess_runtime_runner_logs_captured_failure_output(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed runtime commands should preserve their output in launcher logs."""

    with caplog.at_level(
        logging.INFO,
        logger="launcher.sugarsubstitute_launcher.runtime",
    ):
        with pytest.raises(subprocess.CalledProcessError) as error_info:
            SubprocessRuntimeCommandRunner().run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "print('runtime failure detail token=private-value'); "
                        "raise SystemExit(7)"
                    ),
                ],
                cwd=tmp_path,
                env=os.environ,
            )

    assert error_info.value.returncode == 7
    assert error_info.value.output == "runtime failure detail token=private-value"
    assert "runtime failure detail" in caplog.text
    assert "private-value" not in caplog.text
    assert "token=<redacted>" in caplog.text
    assert "return_code=7" in caplog.text


def test_runtime_provisioner_requires_requirements_file(tmp_path: Path) -> None:
    """Runtime provisioning fails clearly before running uv without requirements."""

    layout = InstallLayout.from_root(tmp_path / "install")
    bundled_uv = tmp_path / "uv.exe"
    bundled_uv.write_bytes(b"uv")

    with pytest.raises(RuntimeProvisioningError, match="Requirements file is missing"):
        UvManagedRuntimeInstaller(bundled_uv_path=bundled_uv).provision(layout=layout)


def test_runtime_provisioner_requires_verified_uv_source(tmp_path: Path) -> None:
    """Missing uv fails closed unless a bundled or checksummed source exists."""

    layout = InstallLayout.from_root(tmp_path / "install")
    _write_file(layout.app_dir / "requirements.txt", "PySide6\n")

    expected_message = re.escape(f"{layout.target.uv_executable_name} is missing")
    with pytest.raises(RuntimeProvisioningError, match=expected_message):
        UvManagedRuntimeInstaller(runner=RecordingRuntimeRunner()).provision(
            layout=layout
        )


def test_runtime_provisioner_extracts_checksummed_uv_archive(tmp_path: Path) -> None:
    """A configured uv archive is verified before extraction."""

    layout = InstallLayout.from_root(tmp_path / "install")
    archive_path = _write_uv_archive(
        tmp_path / "uv.zip",
        executable_name=layout.target.uv_executable_name,
    )
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=_sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    uv_executable = UvManagedRuntimeInstaller(uv_archive_asset=asset).ensure_uv(
        layout=layout
    )

    assert uv_executable == layout.uv_executable
    assert uv_executable.read_bytes() == b"uv"
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_extracts_posix_uv_archive_as_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified POSIX uv tarball produces an executable managed tool."""

    layout = InstallLayout.from_root(tmp_path / "install", target=LINUX_X64)
    archive_path = _write_posix_uv_archive(tmp_path / "uv.tar.gz")
    chmod_calls: list[tuple[Path, int]] = []
    original_chmod = Path.chmod

    def record_chmod(path: Path, mode: int) -> None:
        """Record permission changes while retaining host filesystem behavior."""

        chmod_calls.append((path, mode))
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", record_chmod)
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256=_sha256(archive_path),
        size_bytes=archive_path.stat().st_size,
    )

    uv_executable = UvManagedRuntimeInstaller(uv_archive_asset=asset).ensure_uv(
        layout=layout
    )

    assert uv_executable == layout.runtime_dir / "uv" / "uv"
    assert uv_executable.read_bytes() == b"uv"
    assert any(path == uv_executable and mode & 0o111 for path, mode in chmod_calls)
    assert not (layout.runtime_dir / "uv_extract").exists()


def test_runtime_provisioner_rejects_bad_uv_archive_checksum(tmp_path: Path) -> None:
    """A configured uv archive with a mismatched checksum is not extracted."""

    layout = InstallLayout.from_root(tmp_path / "install")
    archive_path = _write_uv_archive(tmp_path / "uv.zip")
    asset = ReleaseAsset(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        sha256="0" * 64,
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(RuntimeProvisioningError, match="SHA256 mismatch"):
        UvManagedRuntimeInstaller(uv_archive_asset=asset).ensure_uv(layout=layout)


def _write_uv_archive(path: Path, *, executable_name: str = "uv.exe") -> Path:
    """Write a minimal uv release archive fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"uv-test-target/{executable_name}", b"uv")
    return path


def _write_posix_uv_archive(path: Path) -> Path:
    """Write a minimal official-style POSIX uv archive fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"uv"
    member = tarfile.TarInfo("uv-x86_64-unknown-linux-gnu/uv")
    member.size = len(payload)
    member.mode = 0o755
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(payload))
    return path


def _write_file(path: Path, content: str) -> None:
    """Write one fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    """Return the SHA256 hex digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
