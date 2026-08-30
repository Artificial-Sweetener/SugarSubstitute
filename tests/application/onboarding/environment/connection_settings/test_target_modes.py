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

"""Verify managed, attached, and remote connection target persistence."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding import ComfyConnectionSettingsDraft
from substitute.domain.onboarding import ComfyTargetMode
from tests.application.onboarding.environment.connection_settings.support import (
    build_service,
)


def test_connection_settings_saves_managed_local_target(tmp_path: Path) -> None:
    """Managed-local saves should set managed ownership flags."""

    service, repository, checks = build_service(tmp_path)
    workspace = tmp_path / "ComfyUI"

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            host=" 127.0.0.1 ",
            port=8188,
            managed_workspace_path=workspace,
            attached_workspace_path=None,
        )
    )

    assert result.succeeded is True
    assert repository.saved is not None
    assert repository.saved.mode is ComfyTargetMode.MANAGED_LOCAL
    assert repository.saved.endpoint.host == "127.0.0.1"
    assert repository.saved.workspace_path == workspace.resolve()
    assert repository.saved.install_owned is True
    assert repository.saved.launch_owned is True
    assert checks.endpoint_probe_count == 0


def test_connection_settings_rejects_managed_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Managed-local saves should require a workspace path."""

    service, repository, _checks = build_service(tmp_path)

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert result.succeeded is False
    assert "requires a ComfyUI folder" in result.message
    assert repository.saved is None


def test_connection_settings_saves_existing_local_launch_target(tmp_path: Path) -> None:
    """Existing-local saves should require and launch the supplied workspace."""

    service, repository, checks = build_service(tmp_path)
    workspace = tmp_path / "ExternalComfy"
    checks.existing_workspaces.add(workspace.resolve())

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.ATTACHED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=workspace,
        )
    )

    assert result.succeeded is True
    assert repository.saved is not None
    assert repository.saved.mode is ComfyTargetMode.ATTACHED_LOCAL
    assert repository.saved.workspace_path == workspace.resolve()
    assert repository.saved.install_owned is False
    assert repository.saved.launch_owned is True
    assert checks.endpoint_probe_count == 0


def test_connection_settings_rejects_existing_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Existing-local saves should require a workspace path."""

    service, repository, _checks = build_service(tmp_path)

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.ATTACHED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert result.succeeded is False
    assert "requires a ComfyUI folder" in result.message
    assert repository.saved is None


def test_connection_settings_rejects_missing_existing_local_workspace(
    tmp_path: Path,
) -> None:
    """Existing-local saves should block a provided missing workspace."""

    service, repository, _checks = build_service(tmp_path)
    workspace = tmp_path / "MissingComfy"

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.ATTACHED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=workspace,
        )
    )

    assert result.succeeded is False
    assert "does not exist" in result.message
    assert repository.saved is None


def test_connection_settings_saves_remote_without_workspace(tmp_path: Path) -> None:
    """Remote saves should drop workspace paths and keep ownership flags false."""

    service, repository, _checks = build_service(tmp_path)

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="192.168.1.20",
            port=8188,
            managed_workspace_path=tmp_path / "ignored",
            attached_workspace_path=tmp_path / "also-ignored",
        )
    )

    assert result.succeeded is True
    assert repository.saved is not None
    assert repository.saved.mode is ComfyTargetMode.REMOTE
    assert repository.saved.workspace_path is None
    assert repository.saved.install_owned is False
    assert repository.saved.launch_owned is False
