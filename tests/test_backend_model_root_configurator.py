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

"""Tests for BackEnd-owned offline model-root provisioning."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from substitute.infrastructure.comfy import backend_model_root_configurator


def test_configurator_selects_backend_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default provisioning should invoke the installed BackEnd contract."""

    workspace, python_executable, backend_root = _workspace(tmp_path)
    calls: list[tuple[tuple[str, ...], Path, bool]] = []

    def _run_command(
        command: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
    ) -> CompletedProcess[str]:
        calls.append((command, cwd, check))
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backend_model_root_configurator, "run_command", _run_command)

    backend_model_root_configurator.configure_backend_model_root(
        workspace=workspace,
        python_executable=python_executable,
        model_root=None,
    )

    assert calls == [
        (
            (
                str(python_executable),
                str(backend_root / "configure_model_root.py"),
                "--comfy-root",
                str(workspace),
                "--default",
            ),
            backend_root,
            True,
        )
    ]


def test_configurator_preserves_custom_path_as_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Custom provisioning should pass the selected local path to BackEnd."""

    workspace, python_executable, backend_root = _workspace(tmp_path)
    custom_root = tmp_path / "Shared Models"
    commands: list[tuple[str, ...]] = []

    def _run_command(
        command: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
    ) -> CompletedProcess[str]:
        assert cwd == backend_root
        assert check is True
        commands.append(command)
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backend_model_root_configurator, "run_command", _run_command)

    backend_model_root_configurator.configure_backend_model_root(
        workspace=workspace,
        python_executable=python_executable,
        model_root=custom_root,
    )

    assert commands[0][-2:] == ("--path", str(custom_root))


def test_configurator_requires_backend_support(tmp_path: Path) -> None:
    """Provisioning should fail clearly when an old BackEnd lacks the contract."""

    workspace = tmp_path / "ComfyUI"

    with pytest.raises(RuntimeError, match="does not support model-root"):
        backend_model_root_configurator.configure_backend_model_root(
            workspace=workspace,
            python_executable=workspace / ".venv" / "Scripts" / "python.exe",
            model_root=None,
        )


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the minimum installed BackEnd layout used by configurator tests."""

    workspace = tmp_path / "ComfyUI"
    python_executable = workspace / ".venv" / "Scripts" / "python.exe"
    backend_root = workspace / "custom_nodes" / "Substitute-BackEnd"
    backend_root.mkdir(parents=True)
    (backend_root / "configure_model_root.py").write_text("", encoding="utf-8")
    return workspace, python_executable, backend_root
