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

"""Tests for Comfy connection Settings application service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.onboarding import (
    ComfyConnectionSettingsDraft,
    ComfyConnectionSettingsService,
    ComfyTargetService,
)
from substitute.application.restart_requirements import RestartRequirementService
from substitute.application.restart_requirements import RestartScope
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
)


class _TargetRepository:
    """Persist target settings in memory for service tests."""

    def __init__(self, installation: InstallationConfiguration) -> None:
        """Store the installation used for default target construction."""

        self.installation = installation
        self.saved: ComfyTargetConfiguration | None = None

    def exists(self) -> bool:
        """Return whether a target has been saved."""

        return self.saved is not None

    def build_default(self) -> ComfyTargetConfiguration:
        """Return the default managed-local target."""

        return ComfyTargetConfiguration.create_default(self.installation)

    def load(self) -> ComfyTargetConfiguration:
        """Return the saved target or default target."""

        return self.saved or self.build_default()

    def save(self, configuration: ComfyTargetConfiguration) -> None:
        """Record one saved target."""

        self.saved = configuration


class _Checks:
    """Expose controllable readiness checks for service tests."""

    def __init__(self) -> None:
        """Initialize fake checks with permissive defaults."""

        self.existing_workspaces: set[Path] = set()
        self.endpoint_reachable = True
        self.endpoint_probe_count = 0

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return whether the workspace is listed as existing."""

        return workspace in self.existing_workspaces

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Record endpoint probes and return the configured result."""

        _ = configuration
        self.endpoint_probe_count += 1
        return self.endpoint_reachable


@dataclass(frozen=True)
class _ModelRootConfig:
    """Capture fake managed model-root state."""

    workspace: Path
    default_model_root: Path
    effective_model_root: Path
    override_model_root: Path | None


class _ModelRootStore:
    """Persist fake managed model-root settings in memory."""

    def __init__(self) -> None:
        """Initialize an empty fake model-root store."""

        self.saved: dict[Path, Path | None] = {}

    def load(self, workspace: Path) -> _ModelRootConfig:
        """Load fake model-root state for one workspace."""

        resolved_workspace = workspace.resolve()
        default_root = resolved_workspace / "models"
        override = self.saved.get(resolved_workspace)
        return _ModelRootConfig(
            workspace=resolved_workspace,
            default_model_root=default_root,
            effective_model_root=override or default_root,
            override_model_root=override,
        )

    def save(self, workspace: Path, model_root: Path | None) -> _ModelRootConfig:
        """Persist fake model-root state for one workspace."""

        resolved_workspace = workspace.resolve()
        self.saved[resolved_workspace] = (
            model_root.resolve() if model_root is not None else None
        )
        return self.load(resolved_workspace)


def test_connection_settings_loads_persisted_target(tmp_path: Path) -> None:
    """Loading should prefer the persisted target over the default."""

    service, repository, _checks = _build_service(tmp_path)
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="remote-box", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )

    snapshot = service.load_snapshot()

    assert snapshot.persisted_exists is True
    assert snapshot.target == repository.saved
    assert "remote-box:8190" in snapshot.status_message


def test_connection_settings_uses_default_when_target_is_missing(
    tmp_path: Path,
) -> None:
    """Loading should show default managed-local settings without saving them."""

    service, repository, _checks = _build_service(tmp_path)

    snapshot = service.load_snapshot()

    assert snapshot.persisted_exists is False
    assert snapshot.target == repository.build_default()
    assert repository.saved is None


def test_connection_settings_saves_managed_local_target(tmp_path: Path) -> None:
    """Managed-local saves should set managed ownership flags."""

    service, repository, checks = _build_service(tmp_path)
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


def test_connection_settings_loads_managed_model_root(tmp_path: Path) -> None:
    """Managed-local snapshots should expose the effective model root."""

    service, repository, _checks = _build_service(tmp_path, with_model_root=True)
    workspace = tmp_path / "ComfyUI"
    model_root = tmp_path / "Models"
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    assert isinstance(service.model_root_store, _ModelRootStore)
    service.model_root_store.save(workspace, model_root)

    snapshot = service.load_snapshot()

    assert snapshot.managed_model_root == model_root.resolve()
    assert snapshot.active_managed_model_root == model_root.resolve()
    assert snapshot.managed_model_root_uses_default is False


def test_connection_settings_saves_model_root_and_registers_restart_delta(
    tmp_path: Path,
) -> None:
    """Saving a changed model root should persist it and add a restart item."""

    restart_requirements = RestartRequirementService()
    service, repository, _checks = _build_service(
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
    service.load_snapshot()
    model_root = tmp_path / "Models"

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            host="127.0.0.1",
            port=8188,
            managed_workspace_path=workspace,
            attached_workspace_path=None,
            managed_model_root=model_root,
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
    service, repository, _checks = _build_service(
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
            managed_model_root=active_model_root,
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
    service, repository, _checks = _build_service(
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
    assert isinstance(service.model_root_store, _ModelRootStore)
    service.model_root_store.save(workspace, model_root)

    snapshot = service.load_snapshot()

    assert snapshot.managed_model_root == model_root.resolve()
    assert restart_requirements.snapshot().count == 0


def test_connection_settings_rejects_managed_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Managed-local saves should require a workspace path."""

    service, repository, _checks = _build_service(tmp_path)

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

    service, repository, checks = _build_service(tmp_path)
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

    service, repository, _checks = _build_service(tmp_path)

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

    service, repository, _checks = _build_service(tmp_path)
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

    service, repository, _checks = _build_service(tmp_path)

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


def test_connection_settings_rejects_invalid_endpoint(tmp_path: Path) -> None:
    """Saving should reject blank hosts and invalid ports before persistence."""

    service, repository, _checks = _build_service(tmp_path)

    blank_host = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host=" ",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )
    invalid_port = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="127.0.0.1",
            port=70000,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert blank_host.succeeded is False
    assert blank_host.message == "Host cannot be blank."
    assert invalid_port.succeeded is False
    assert invalid_port.message == "Port must be between 1 and 65535."
    assert repository.saved is None


def test_connection_settings_blocks_unreachable_remote_save(tmp_path: Path) -> None:
    """Remote saves should reject unreachable endpoints."""

    service, repository, checks = _build_service(tmp_path)
    checks.endpoint_reachable = False

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="remote-box",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert result.succeeded is False
    assert "did not respond" in result.message
    assert repository.saved is None


def test_connection_settings_tests_endpoint_without_saving(tmp_path: Path) -> None:
    """Endpoint testing should report reachability without persisting."""

    service, repository, checks = _build_service(tmp_path)

    success = service.test_endpoint("127.0.0.1", 8188)
    checks.endpoint_reachable = False
    failure = service.test_endpoint("127.0.0.1", 8188)

    assert success.succeeded is True
    assert "responded" in success.message
    assert failure.succeeded is False
    assert "did not respond" in failure.message
    assert repository.saved is None


def _build_service(
    tmp_path: Path,
    *,
    with_model_root: bool = False,
    restart_requirements: RestartRequirementService | None = None,
) -> tuple[ComfyConnectionSettingsService, _TargetRepository, _Checks]:
    """Create a service and fakes rooted under the temp directory."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = _TargetRepository(installation)
    checks = _Checks()
    service = ComfyConnectionSettingsService(
        target_service=ComfyTargetService(repository),
        checks=checks,
        model_root_store=_ModelRootStore() if with_model_root else None,
        restart_requirements=restart_requirements,
    )
    return service, repository, checks
