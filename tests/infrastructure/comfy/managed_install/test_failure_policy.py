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

"""Verify installation cleanup and storage failure policy."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import pytest
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_install_failures
from substitute.infrastructure.comfy import managed_workspace_provisioning
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from sugarsubstitute_shared.external_scratch import ExternalScratchWorkspace

from .orchestration_support import (
    configure_managed_install,
)


def test_ensure_managed_comfy_setup_cleans_scratch_after_clone_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed setup should delete scratch files even when provisioning fails."""

    configure_managed_install(monkeypatch, tmp_path)

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")
    scratch_root = tmp_path / "runtime" / "installer-temp" / "managed-comfy" / "tx-2"
    scratch_root.parent.mkdir(parents=True)
    monkeypatch.setattr(
        managed_install,
        "allocate_managed_install_scratch",
        lambda _workspace: ExternalScratchWorkspace.reserve(scratch_root),
    )

    with pytest.raises(RuntimeError, match="download ComfyUI"):
        managed_install.ensure_managed_comfy_setup(workspace=tmp_path / "comfyui")

    assert not scratch_root.exists()


def test_ensure_managed_comfy_setup_keeps_original_failure_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Scratch cleanup warnings should not replace the real provisioning error."""

    configure_managed_install(monkeypatch, tmp_path)

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")

    def _raise_cleanup_error(self: ExternalScratchWorkspace) -> None:
        _ = self
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(
        ExternalScratchWorkspace,
        "cleanup",
        _raise_cleanup_error,
    )

    with pytest.raises(RuntimeError, match="download ComfyUI"):
        managed_install.ensure_managed_comfy_setup(workspace=tmp_path / "comfyui")


def test_ensure_managed_comfy_setup_does_not_fallback_after_storage_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Torch fallback should not run when preferred install exhausts storage."""

    configure_managed_install(monkeypatch, tmp_path)

    workspace = tmp_path / "comfyui"
    workspace_python = workspace_python_path(workspace)
    install_attempts: list[tuple[str, ...]] = []

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")

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

    def _raise_storage_error(
        python_executable: Path,
        *,
        install_arguments: tuple[str, ...],
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = python_executable, on_log, env
        install_attempts.append(tuple(install_arguments))
        raise managed_install_failures.ManagedInstallStorageError(
            "No space left on device"
        )

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
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
        _raise_storage_error,
    )

    with pytest.raises(managed_install_failures.ManagedInstallStorageError):
        managed_install.ensure_managed_comfy_setup(workspace=workspace)

    assert install_attempts == [("torch-nightly",)]
