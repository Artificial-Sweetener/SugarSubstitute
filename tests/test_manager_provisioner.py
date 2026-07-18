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

"""Tests for authoritative ComfyUI Manager selection and provisioning."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import stat
import subprocess
from typing import cast

import pytest

from substitute.domain.comfy_manager import (
    ComfyManagerCapabilities,
    ComfyManagerKind,
    ComfyManagerProvisioningAction,
    select_attached_manager_action,
)
from substitute.infrastructure.comfy import manager_provisioner
from tests.repository_service_test_double import RecordingRepositoryService


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    (
        (
            ComfyManagerCapabilities(True, True, True),
            ComfyManagerProvisioningAction.USE_INTEGRATED,
        ),
        (
            ComfyManagerCapabilities(True, False, True),
            ComfyManagerProvisioningAction.USE_LEGACY,
        ),
        (
            ComfyManagerCapabilities(True, False, False),
            ComfyManagerProvisioningAction.INSTALL_INTEGRATED,
        ),
        (
            ComfyManagerCapabilities(False, False, False),
            ComfyManagerProvisioningAction.INSTALL_LEGACY,
        ),
    ),
)
def test_attached_manager_policy_matrix(
    capabilities: ComfyManagerCapabilities,
    expected: ComfyManagerProvisioningAction,
) -> None:
    """Attached policy should prefer healthy existing routes before installing."""

    assert select_attached_manager_action(capabilities) is expected


def test_managed_manager_installs_integrated_package_then_removes_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed setup should validate integrated Manager before deleting legacy code."""

    python = _prepare_modern_workspace(tmp_path)
    legacy = manager_provisioner.workspace_manager_directory(tmp_path)
    legacy.mkdir(parents=True)
    (legacy / "user-data.json").write_text("owned fixture", encoding="utf-8")
    commands: list[list[str]] = []
    environments: list[dict[str, str]] = []
    probe_count = 0

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal probe_count
        environments.append(dict(cast(Mapping[str, str], kwargs["env"])))
        commands.append(command)
        if command[1:2] == ["-c"]:
            probe_count += 1
            if probe_count == 1:
                return subprocess.CompletedProcess(
                    command, 1, stdout="", stderr="ModuleNotFoundError: comfyui_manager"
                )
            return subprocess.CompletedProcess(command, 0, stdout="4.2.2\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="installed", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run", fake_run
    )

    runtime = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path, python_executable=python
    )

    assert runtime.kind is ComfyManagerKind.INTEGRATED
    assert runtime.version == "4.2.2"
    assert not legacy.exists()
    assert commands[1] == [
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        str(tmp_path / "manager_requirements.txt"),
        "pygit2==1.19.3",
    ]
    assert "cm_cli" not in commands[0][2]
    assert "git_compat.USE_PYGIT2" in commands[0][2]
    assert all(environment["CM_USE_PYGIT2"] == "1" for environment in environments)


@pytest.mark.platforms("windows")
def test_managed_manager_removes_legacy_checkout_with_readonly_git_packs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed migration should remove real Windows read-only Git pack files."""

    python = _prepare_modern_workspace(tmp_path)
    legacy = manager_provisioner.workspace_manager_directory(tmp_path)
    pack_root = legacy / ".git" / "objects" / "pack"
    pack_root.mkdir(parents=True)
    pack_file = pack_root / "pack-fixture.idx"
    pack_file.write_bytes(b"pack fixture")
    pack_file.chmod(stat.S_IREAD)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout="4.2.2\n",
            stderr="",
        ),
    )

    runtime = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert runtime.kind is ComfyManagerKind.INTEGRATED
    assert not legacy.exists()


def test_managed_manager_preserves_legacy_when_integrated_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed migration must retain the old checkout until replacement validates."""

    python = _prepare_modern_workspace(tmp_path)
    legacy = manager_provisioner.workspace_manager_directory(tmp_path)
    legacy.mkdir(parents=True)

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        if command[1:2] == ["-c"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="probe stdout",
                stderr="ModuleNotFoundError: No module named 'aiohttp'",
            )
        return subprocess.CompletedProcess(command, 0, stdout="installed", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run", fake_run
    )

    with pytest.raises(RuntimeError, match="No module named 'aiohttp'"):
        manager_provisioner.ensure_managed_workspace_manager(
            tmp_path, python_executable=python
        )

    assert legacy.is_dir()


def test_attached_manager_prefers_integrated_and_keeps_user_legacy_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached setup should prefer integrated Manager without deleting user files."""

    python = _prepare_modern_workspace(tmp_path)
    legacy_cli = manager_provisioner.workspace_manager_cli_path(tmp_path)
    legacy_cli.parent.mkdir(parents=True)
    legacy_cli.write_text("# fixture", encoding="utf-8")

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="4.2.2\n", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run", fake_run
    )

    runtime = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path, python_executable=python
    )

    assert runtime.kind is ComfyManagerKind.INTEGRATED
    assert legacy_cli.is_file()


def test_attached_old_comfy_installs_required_legacy_custom_node(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Older attached ComfyUI should receive legacy Manager when none exists."""

    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    def materialize(_url: str, destination: Path) -> None:
        """Create the files produced by one legacy Manager clone."""

        destination.mkdir(parents=True)
        (destination / "cm-cli.py").write_text("# fixture", encoding="utf-8")
        (destination / "requirements.txt").write_text("typer", encoding="utf-8")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run", fake_run
    )
    repositories = RecordingRepositoryService(clone_callback=materialize)

    runtime = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path,
        python_executable=python,
        repositories=repositories,
    )

    assert runtime.kind is ComfyManagerKind.LEGACY_CUSTOM_NODE
    assert runtime.legacy_cli_path == manager_provisioner.workspace_manager_cli_path(
        tmp_path
    )
    assert commands == [
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-r",
            str(
                manager_provisioner.workspace_manager_directory(tmp_path)
                / "requirements.txt"
            ),
        ],
        [
            str(python),
            str(manager_provisioner.workspace_manager_cli_path(tmp_path)),
            "--help",
        ],
    ]


def test_legacy_manager_probe_does_not_force_integrated_git_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Legacy Manager should retain its own GitPython compatibility contract."""

    python = _prepare_modern_workspace(tmp_path)
    legacy_cli = manager_provisioner.workspace_manager_cli_path(tmp_path)
    legacy_cli.parent.mkdir(parents=True)
    legacy_cli.write_text("# fixture", encoding="utf-8")
    environments: list[dict[str, str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        environments.append(dict(cast(Mapping[str, str], kwargs["env"])))
        if command[1:2] == ["-c"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="missing")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_provisioner.subprocess.run", fake_run
    )

    runtime = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path,
        python_executable=python,
        env={"PATH": ""},
    )

    assert runtime.kind is ComfyManagerKind.LEGACY_CUSTOM_NODE
    assert environments[0]["CM_USE_PYGIT2"] == "1"
    assert "CM_USE_PYGIT2" not in environments[1]


def _prepare_modern_workspace(workspace: Path) -> Path:
    """Create the static integrated Manager contract and a Python fixture."""

    (workspace / "comfy").mkdir(parents=True)
    (workspace / "comfy" / "cli_args.py").write_text(
        'parser.add_argument("--enable-manager")', encoding="utf-8"
    )
    (workspace / "manager_requirements.txt").write_text(
        "comfyui_manager==4.2.2", encoding="utf-8"
    )
    python = workspace / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python
