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

"""Tests for Manager dependency transaction ownership."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from substitute.infrastructure.comfy import manager_requirements_installer
from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)
from sugarsubstitute_shared.startup_remote_access import StartupConnectivityError


def test_manager_requirements_install_uses_checkout_file_exactly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The checkout requirements transaction should not inject app packages."""

    python = tmp_path / "python.exe"
    requirements = tmp_path / "manager_requirements.txt"
    observed: list[list[str]] = []
    observed_working_directories: list[str] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed.append(command)
        observed_working_directories.append(str(kwargs["cwd"]))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_requirements_installer.subprocess.run",
        fake_run,
    )

    manager_requirements_installer.ComfyManagerRequirementsInstaller().install_requirements(
        workspace=tmp_path,
        python_executable=python,
        requirements_path=requirements,
    )

    assert observed == [
        [
            subprocess_path(python),
            "-m",
            "pip",
            "install",
            "-r",
            subprocess_path(requirements),
        ]
    ]
    assert observed_working_directories == [subprocess_working_directory(tmp_path)]


def test_pygit2_backend_is_an_explicit_separate_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The app backend pin should install only after capability validation."""

    python = tmp_path / "python.exe"
    observed: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Record the standalone backend transaction."""

        observed.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_requirements_installer.subprocess.run",
        fake_run,
    )

    manager_requirements_installer.ComfyManagerRequirementsInstaller().install_pygit2_backend(
        workspace=tmp_path,
        python_executable=python,
    )

    assert observed == [
        [subprocess_path(python), "-m", "pip", "install", "pygit2==1.19.3"]
    ]


def test_manager_requirements_promote_connectivity_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager pip transport evidence must activate startup degradation."""

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Return one deterministic pip connection failure."""

        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="NewConnectionError: network is unreachable",
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_requirements_installer.subprocess.run",
        fake_run,
    )

    with pytest.raises(StartupConnectivityError):
        manager_requirements_installer.ComfyManagerRequirementsInstaller().install_requirements(
            workspace=tmp_path,
            python_executable=tmp_path / "python.exe",
            requirements_path=tmp_path / "requirements.txt",
        )


@pytest.mark.platforms("windows")
def test_manager_requirements_translate_pip_long_path_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager dependency failures should retain pip's overlong output path."""

    failing_path = (
        "E:\\managed\\temp\\pip-ephem-wheel-cache-pmo9xg0b\\wheels\\59\\1d\\00"
        "\\729d4b9dcecc8342dac49bcf6ab1415de9f48be12e466feb73"
        "\\tmpzx280yzl\\.tmp-by7a27ea\\nested-path-component-that-keeps-growing"
        "\\another-long-component\\one-more-wheel-build-layer-that-exceeds-max-path"
        "\\sugarcubes-0.11.0-py3-none-any.whl"
    )
    detail = f"error: [Errno 2] No such file or directory: '{failing_path}'"

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Return the misleading missing-file failure emitted by pip."""

        return subprocess.CompletedProcess(command, 1, stdout="", stderr=detail)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_requirements_installer.subprocess.run",
        fake_run,
    )

    with pytest.raises(ExternalLongPathCompatibilityError) as error:
        manager_requirements_installer.ComfyManagerRequirementsInstaller().install_requirements(
            workspace=tmp_path,
            python_executable=tmp_path / "python.exe",
            requirements_path=tmp_path / "requirements.txt",
        )

    assert error.value.path == Path(failing_path)
