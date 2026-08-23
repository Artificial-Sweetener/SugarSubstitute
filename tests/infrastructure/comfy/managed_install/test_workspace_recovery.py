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

"""Verify managed workspace ownership checks and legacy recovery."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import pytest
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_existing_setup_operations
from substitute.infrastructure.comfy import managed_workspace_provisioning
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_nested_main_path,
    workspace_python_path,
)

from .orchestration_support import (
    configure_managed_install,
)


def test_ensure_managed_comfy_setup_removes_incomplete_workspace_before_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Leftover bootstrap artifacts should be cleared before explicit install steps."""

    configure_managed_install(monkeypatch, tmp_path)

    stale_python = workspace_python_path(tmp_path)
    stale_python.parent.mkdir(parents=True, exist_ok=True)
    stale_python.write_text("", encoding="utf-8")

    new_python = workspace_python_path(tmp_path)
    repo_sync_calls: list[Path] = []

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")
        repo_sync_calls.append(workspace)

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
    )

    def _fake_ensure_workspace_virtualenv(
        workspace: Path,
        *,
        python_runtime: str | None = None,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = workspace, python_runtime, on_log, env
        new_python.parent.mkdir(parents=True, exist_ok=True)
        new_python.write_text("", encoding="utf-8")
        return new_python

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
        lambda python_executable, *, install_arguments, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == new_python
    assert repo_sync_calls == [tmp_path]


def test_ensure_managed_comfy_setup_rejects_nonempty_unmanaged_workspace(
    tmp_path: Path,
) -> None:
    """Managed install should fail closed when the selected folder already has unrelated files."""

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "notes.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already contains files"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path,
        )


def test_ensure_managed_comfy_setup_migrates_legacy_nested_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Legacy nested managed installs should migrate into the canonical workspace root."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / ".comfy_installed").write_text("ok", encoding="utf-8")
    nested_main = workspace_nested_main_path(tmp_path)
    nested_main.parent.mkdir(parents=True, exist_ok=True)
    nested_main.write_text("main", encoding="utf-8")

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == python_path
    assert workspace_main_path(tmp_path).exists()
    assert not (tmp_path / "ComfyUI").exists()
