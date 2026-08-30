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

"""Tests for settling Comfy-Manager's startup-deferred Registry updates."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_registry_update_settler import (
    ComfyNodepackRegistryUpdateSettler,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_settler_runs_manager_prestartup_in_selected_cli_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Use Manager's executor and suppress only its process-restart handoff."""

    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: True,
    )

    def fake_stream(
        command: list[str],
        **kwargs: Any,
    ) -> tuple[int, tuple[str, ...]]:
        """Confirm Manager's CLI-session acknowledgement contract."""

        observed["command"] = command
        observed.update(kwargs)
        process_env = kwargs["env"]
        assert isinstance(process_env, Mapping)
        session = Path(str(process_env["__COMFY_CLI_SESSION__"]))
        Path(f"{session}.reboot").touch()
        return 0, ("[ComfyUI-Manager] Startup script completed.",)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.stream_command_collecting_output",
        fake_stream,
    )

    result = ComfyNodepackRegistryUpdateSettler().settle(
        manager_runtime=_runtime(tmp_path, python),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={"CONDA_PREFIX": "wrong"},
    )

    assert result.succeeded
    assert observed["command"] == [
        subprocess_path(python),
        "-m",
        "comfyui_manager.prestartup_script",
    ]
    selected_env = observed["env"]
    assert isinstance(selected_env, Mapping)
    assert selected_env["VIRTUAL_ENV"] == str(python.parent.parent)
    assert selected_env["COMFYUI_PATH"] == str(tmp_path.resolve())
    assert selected_env["COMFYUI_FOLDERS_BASE_PATH"] == str(tmp_path.resolve())
    assert selected_env["GIT_PYTHON_REFRESH"] == "quiet"
    assert "CONDA_PREFIX" not in selected_env


def test_settler_rejects_missing_manager_prestartup_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Do not invent replacement update mechanics when Manager cannot settle work."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: False,
    )

    result = ComfyNodepackRegistryUpdateSettler().settle(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={},
    )

    assert not result.succeeded
    assert "pre-startup executor is unavailable" in result.output[0]


def _runtime(workspace: Path, python: Path) -> ComfyManagerRuntime:
    """Build one validated integrated Manager runtime fixture."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=python,
        version="4.1",
    )
