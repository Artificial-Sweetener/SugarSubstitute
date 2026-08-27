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

"""Verify managed and remote model-root connection settings."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding import ComfyConnectionSettingsDraft
from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartScope,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from tests.application.onboarding.environment.connection_settings.support import (
    build_service,
    environment_client,
    model_root_status,
)


def test_connection_settings_loads_managed_model_root(tmp_path: Path) -> None:
    """Managed-local snapshots should expose the effective model root."""

    service, repository, _checks = build_service(tmp_path, with_model_root=True)
    workspace = tmp_path / "ComfyUI"
    model_root = tmp_path / "Models"
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    environment_client(service).status = model_root_status(
        workspace=workspace,
        configured=model_root,
        active=model_root,
    )

    snapshot = service.load_snapshot()

    assert snapshot.managed_model_root == str(model_root.resolve())
    assert snapshot.active_managed_model_root == str(model_root.resolve())
    assert snapshot.managed_model_root_uses_default is False


def test_connection_settings_saves_model_root_and_registers_restart_delta(
    tmp_path: Path,
) -> None:
    """Saving a changed model root should persist it and add a restart item."""

    restart_requirements = RestartRequirementService()
    service, repository, _checks = build_service(
        tmp_path,
        with_model_root=True,
        restart_requirements=restart_requirements,
    )
    workspace = tmp_path / "ComfyUI"
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    environment_client(service).status = model_root_status(
        workspace=workspace,
        configured=None,
        active=workspace / "models",
    )
    service.load_snapshot()
    model_root = tmp_path / "Models"

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=workspace,
            attached_workspace_path=None,
            managed_model_root=str(model_root),
            managed_model_root_uses_default=False,
        )
    )

    assert result.succeeded is True
    assert result.restart_required is True
    assert restart_requirements.snapshot().count == 1
    item = restart_requirements.snapshot().items[0]
    assert item.key == "comfy.model_root"
    assert item.label == "Model folder"
    assert item.saved_value == str(model_root.resolve())


def test_connection_settings_clears_model_root_restart_delta_when_reset_to_active(
    tmp_path: Path,
) -> None:
    """Saving the active model root should clear the pending restart item."""

    restart_requirements = RestartRequirementService()
    service, repository, _checks = build_service(
        tmp_path,
        with_model_root=True,
        restart_requirements=restart_requirements,
    )
    workspace = tmp_path / "ComfyUI"
    active_model_root = workspace.resolve() / "models"
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    environment_client(service).status = model_root_status(
        workspace=workspace,
        configured=None,
        active=active_model_root,
    )
    service.load_snapshot()
    restart_requirements.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value=str(active_model_root),
        saved_value=str(tmp_path / "OtherModels"),
        scope=RestartScope.FULL_APP,
    )

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=workspace,
            attached_workspace_path=None,
            managed_model_root=str(active_model_root),
            managed_model_root_uses_default=True,
        )
    )

    assert result.succeeded is True
    assert restart_requirements.snapshot().count == 0


def test_connection_settings_cold_start_does_not_create_stale_restart_delta(
    tmp_path: Path,
) -> None:
    """Loading a saved model root in a fresh service should not mark it pending."""

    restart_requirements = RestartRequirementService()
    service, repository, _checks = build_service(
        tmp_path,
        with_model_root=True,
        restart_requirements=restart_requirements,
    )
    workspace = tmp_path / "ComfyUI"
    model_root = tmp_path / "Models"
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    environment_client(service).status = model_root_status(
        workspace=workspace,
        configured=model_root,
        active=model_root,
    )

    snapshot = service.load_snapshot()

    assert snapshot.managed_model_root == str(model_root.resolve())
    assert restart_requirements.snapshot().count == 0


def test_connection_settings_preserves_remote_host_model_path(tmp_path: Path) -> None:
    """Remote model paths should cross the Windows client without rewriting."""

    service, repository, _checks = build_service(tmp_path, with_model_root=True)
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="linux-box", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    service.load_snapshot()

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="linux-box",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
            managed_model_root="/srv/comfy/models",
            managed_model_root_uses_default=False,
        )
    )

    assert result.succeeded is True
    assert environment_client(service).last_update_path == "/srv/comfy/models"
