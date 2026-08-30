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

"""Verify deterministic managed-install failure-stage injection."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import pytest
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_install_failures
from substitute.infrastructure.comfy import managed_workspace_provisioning
from substitute.infrastructure.comfy import managed_workspace_operations
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)

from .orchestration_support import (
    configure_managed_install,
)


def test_clone_managed_workspace_honors_forced_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should support deterministic clone-failure injection."""

    configure_managed_install(monkeypatch, tmp_path)

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")

    with pytest.raises(RuntimeError, match="couldn't download ComfyUI"):
        managed_workspace_operations.clone_managed_workspace(tmp_path)


def test_ensure_managed_comfy_setup_honors_dependency_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should fail during the comfy-cli install stage when injected."""

    configure_managed_install(monkeypatch, tmp_path)

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "dependency_install")

    def _fake_clone_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")

    workspace_python = workspace_python_path(tmp_path)

    def _fake_ensure_workspace_virtualenv(
        workspace: Path,
        *,
        python_runtime: str | None = None,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = workspace, python_runtime, on_log, env
        workspace_python.parent.mkdir(parents=True, exist_ok=True)
        workspace_python.write_text("", encoding="utf-8")
        return workspace_python

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        lambda workspace, on_log=None, env=None: _fake_clone_workspace(
            workspace,
            on_log,
            env,
        ),
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            managed_install_failures.raise_forced_managed_failure("dependency_install")
        ),
    )

    with pytest.raises(RuntimeError, match="Python packages"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path,
        )
