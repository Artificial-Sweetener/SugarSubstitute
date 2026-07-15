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

"""Tests for managed workspace ComfyUI-Manager provisioning."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.infrastructure.comfy import manager_provisioner
from tests.repository_service_test_double import RecordingRepositoryService


def test_ensure_workspace_manager_custom_node_clones_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioner should clone Manager and install its workspace Python package."""

    commands: list[list[str]] = []
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    manager_provisioner.workspace_manager_requirements_path(tmp_path).write_text(
        "comfyui_manager==4.2.2",
        encoding="utf-8",
    )

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        _ = kwargs
        commands.append(command)
        if command == [str(python_path), "-c", "import cm_cli"]:
            import_checks = sum(1 for seen in commands if seen == command)
            return SimpleNamespace(
                returncode=0 if import_checks > 1 else 1,
                stdout="",
                stderr="",
            )
        if command == [str(python_path), "-c", "import cm_cli.__main__"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[:4] == [str(python_path), "-m", "pip", "install"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run",
        _fake_run,
    )

    def materialize_manager(_repository_url: str, target_path: Path) -> None:
        """Materialize the file expected from the cloned Manager fixture."""

        cli_path = target_path / "cm-cli.py"
        cli_path.parent.mkdir(parents=True, exist_ok=True)
        cli_path.write_text("# cm-cli", encoding="utf-8")

    repositories = RecordingRepositoryService(clone_callback=materialize_manager)
    result = manager_provisioner.ensure_workspace_manager_custom_node(
        tmp_path,
        repositories=repositories,
    )

    assert result == manager_provisioner.workspace_manager_cli_path(tmp_path)
    assert commands == [
        [str(python_path), "-c", "import cm_cli"],
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "-r",
            str(manager_provisioner.workspace_manager_requirements_path(tmp_path)),
        ],
        [str(python_path), "-c", "import cm_cli"],
        [str(python_path), "-c", "import cm_cli.__main__"],
    ]
    assert repositories.calls == [
        (
            "clone",
            (
                manager_provisioner.DEFAULT_MANAGER_REPOSITORY_URL,
                manager_provisioner.workspace_manager_directory(tmp_path),
            ),
        )
    ]


def test_ensure_workspace_manager_custom_node_short_circuits_when_present_and_importable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioner should not re-clone or pip install when Manager is already usable."""

    cli_path = manager_provisioner.workspace_manager_cli_path(tmp_path)
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_text("# cm-cli", encoding="utf-8")
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    commands: list[list[str]] = []

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        _ = kwargs
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run",
        _fake_run,
    )

    result = manager_provisioner.ensure_workspace_manager_custom_node(tmp_path)

    assert result == cli_path
    assert commands == [
        [str(python_path), "-c", "import cm_cli"],
        [str(python_path), "-c", "import cm_cli.__main__"],
    ]


def test_ensure_workspace_manager_custom_node_repairs_existing_checkout_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing Manager checkouts should install cm_cli when the package is missing."""

    cli_path = manager_provisioner.workspace_manager_cli_path(tmp_path)
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_text("# cm-cli", encoding="utf-8")
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    requirements_path = manager_provisioner.workspace_manager_requirements_path(
        tmp_path
    )
    requirements_path.write_text("comfyui_manager==4.2.2", encoding="utf-8")
    commands: list[list[str]] = []

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        _ = kwargs
        commands.append(command)
        if command == [str(python_path), "-c", "import cm_cli"]:
            import_checks = sum(1 for seen in commands if seen == command)
            return SimpleNamespace(
                returncode=0 if import_checks > 1 else 1,
                stdout="",
                stderr="",
            )
        if command == [str(python_path), "-c", "import cm_cli.__main__"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run",
        _fake_run,
    )

    result = manager_provisioner.ensure_workspace_manager_custom_node(tmp_path)

    assert result == cli_path
    assert commands == [
        [str(python_path), "-c", "import cm_cli"],
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
        ],
        [str(python_path), "-c", "import cm_cli"],
        [str(python_path), "-c", "import cm_cli.__main__"],
    ]


def test_ensure_workspace_manager_custom_node_repairs_missing_comfy_requirements(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager repair should install ComfyUI requirements when cm_cli cannot start."""

    cli_path = manager_provisioner.workspace_manager_cli_path(tmp_path)
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_text("# cm-cli", encoding="utf-8")
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    commands: list[list[str]] = []

    def _fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        _ = kwargs
        commands.append(command)
        if command == [str(python_path), "-c", "import cm_cli.__main__"]:
            entrypoint_checks = sum(1 for seen in commands if seen == command)
            return SimpleNamespace(
                returncode=0 if entrypoint_checks > 1 else 1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'aiohttp'",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run",
        _fake_run,
    )

    result = manager_provisioner.ensure_workspace_manager_custom_node(tmp_path)

    assert result == cli_path
    assert commands == [
        [str(python_path), "-c", "import cm_cli"],
        [str(python_path), "-c", "import cm_cli.__main__"],
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "aiohttp>=3.11.8",
        ],
        [str(python_path), "-c", "import cm_cli.__main__"],
    ]
