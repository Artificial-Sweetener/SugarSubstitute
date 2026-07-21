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


def test_manager_requirements_install_uses_checkout_file_exactly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The checkout requirements transaction should not inject app packages."""

    python = tmp_path / "python.exe"
    requirements = tmp_path / "manager_requirements.txt"
    observed: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed.append(command)
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

    assert observed == [[str(python), "-m", "pip", "install", "-r", str(requirements)]]


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

    assert observed == [[str(python), "-m", "pip", "install", "pygit2==1.19.3"]]
