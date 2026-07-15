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

"""Load, validate, test, and save Comfy connection settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.comfy_connection_settings")
_MIN_PORT = 1
_MAX_PORT = 65535
_CONNECTION_RESTART_KEY = "comfy.connection"
_MODEL_ROOT_RESTART_KEY = "comfy.model_root"


class ComfyConnectionReadinessChecks(Protocol):
    """Describe target checks needed by the Settings connection editor."""

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return whether an attached-local workspace path exists."""

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the target endpoint accepts a connection."""


class ManagedModelRootConfigProtocol(Protocol):
    """Describe managed model-root state loaded for Settings display."""

    @property
    def workspace(self) -> Path:
        """Return the managed ComfyUI workspace path."""

    @property
    def default_model_root(self) -> Path:
        """Return the workspace-local default models folder."""

    @property
    def effective_model_root(self) -> Path:
        """Return the active or saved effective model root."""

    @property
    def override_model_root(self) -> Path | None:
        """Return the explicit override model root, when configured."""


class ManagedModelRootStoreProtocol(Protocol):
    """Describe managed model-root persistence used by Settings."""

    def load(self, workspace: Path) -> ManagedModelRootConfigProtocol:
        """Return the effective managed model root for one workspace."""

    def save(
        self,
        workspace: Path,
        model_root: Path | None,
    ) -> ManagedModelRootConfigProtocol:
        """Persist and return the managed model root for one workspace."""


@dataclass(frozen=True)
class ComfyConnectionSettingsSnapshot:
    """Capture the persisted Comfy target displayed in Settings."""

    target: ComfyTargetConfiguration
    persisted_exists: bool
    status_message: str
    can_test_endpoint: bool
    managed_model_root: Path | None = None
    managed_model_root_uses_default: bool = True
    active_managed_model_root: Path | None = None


@dataclass(frozen=True)
class ComfyConnectionSettingsDraft:
    """Capture one edited Comfy target submitted from Settings."""

    mode: ComfyTargetMode
    host: str
    port: int
    managed_workspace_path: Path | None
    attached_workspace_path: Path | None
    managed_model_root: Path | None = None
    managed_model_root_uses_default: bool = True


@dataclass(frozen=True)
class ComfyConnectionSaveResult:
    """Describe the result of saving or testing one Comfy connection draft."""

    target: ComfyTargetConfiguration | None
    succeeded: bool
    message: str
    restart_required: bool
    restart_snapshot: RestartRequirementSnapshot | None = None


@dataclass
class ComfyConnectionSettingsService:
    """Coordinate Comfy target edits made from the integrated Settings surface."""

    target_service: ComfyTargetService
    checks: ComfyConnectionReadinessChecks
    model_root_store: ManagedModelRootStoreProtocol | None = None
    restart_requirements: RestartRequirementService | None = None

    def __post_init__(self) -> None:
        """Initialize process-local active baselines for restart comparisons."""

        self._active_target_baseline: ComfyTargetConfiguration | None = None
        self._active_model_root_baselines: dict[Path, Path] = {}

    def load_snapshot(self) -> ComfyConnectionSettingsSnapshot:
        """Load the persisted target or default target for display."""

        persisted = self.target_service.load_persisted()
        target = persisted or self.target_service.create_default()
        if self._active_target_baseline is None:
            self._active_target_baseline = target
        model_root_config = self._load_model_root_config(target)
        return ComfyConnectionSettingsSnapshot(
            target=target,
            persisted_exists=persisted is not None,
            status_message=_status_message(
                target, persisted_exists=persisted is not None
            ),
            can_test_endpoint=True,
            managed_model_root=(
                model_root_config.effective_model_root
                if model_root_config is not None
                else None
            ),
            managed_model_root_uses_default=(
                model_root_config.override_model_root is None
                if model_root_config is not None
                else True
            ),
            active_managed_model_root=(
                self._model_root_baseline(model_root_config.workspace)
                if model_root_config is not None
                else None
            ),
        )

    def save_draft(
        self,
        draft: ComfyConnectionSettingsDraft,
    ) -> ComfyConnectionSaveResult:
        """Validate and persist one edited Comfy target."""

        active_target = self._active_target()
        try:
            target = self._target_from_draft(draft)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Comfy connection settings validation failed",
                mode=draft.mode.value,
                host=draft.host,
                port=draft.port,
                has_managed_workspace=draft.managed_workspace_path is not None,
                has_attached_workspace=draft.attached_workspace_path is not None,
                reason=str(error),
            )
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message=str(error),
                restart_required=False,
            )

        reachability_result = self._validate_save_reachability(target)
        if reachability_result is not None:
            return reachability_result

        try:
            model_root_config = self._save_model_root(target, draft)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Comfy connection model-root settings validation failed",
                mode=draft.mode.value,
                has_managed_workspace=draft.managed_workspace_path is not None,
                has_managed_model_root=draft.managed_model_root is not None,
                reason=str(error),
            )
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message=str(error),
                restart_required=False,
            )

        saved = self.target_service.configure(target)
        restart_snapshot = self._register_restart_requirements(
            active_target=active_target,
            saved_target=saved,
            model_root_config=model_root_config,
        )
        restart_required = (
            restart_snapshot.count > 0
            if restart_snapshot is not None
            else active_target != saved
        )
        log_info(
            _LOGGER,
            "Comfy connection settings saved",
            mode=saved.mode.value,
            host=saved.endpoint.host,
            port=saved.endpoint.port,
            has_workspace=saved.workspace_path is not None,
        )
        return ComfyConnectionSaveResult(
            target=saved,
            succeeded=True,
            message="Saved. Restart Substitute to use the new ComfyUI connection."
            if restart_required
            else "Connection settings are already saved.",
            restart_required=restart_required,
            restart_snapshot=restart_snapshot,
        )

    def test_endpoint(self, host: str, port: int) -> ComfyConnectionSaveResult:
        """Probe one endpoint without persisting it."""

        normalized_host = host.strip()
        validation_message = _endpoint_validation_message(normalized_host, port)
        if validation_message is not None:
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message=validation_message,
                restart_required=False,
            )
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode.REMOTE,
            endpoint=ComfyEndpoint(host=normalized_host, port=port),
            workspace_path=None,
            install_owned=False,
            launch_owned=False,
        )
        if self.checks.is_target_endpoint_reachable(target):
            return ComfyConnectionSaveResult(
                target=target,
                succeeded=True,
                message=f"ComfyUI responded at {normalized_host}:{port}.",
                restart_required=False,
            )
        return ComfyConnectionSaveResult(
            target=target,
            succeeded=False,
            message=f"ComfyUI did not respond at {normalized_host}:{port}.",
            restart_required=False,
        )

    def _target_from_draft(
        self,
        draft: ComfyConnectionSettingsDraft,
    ) -> ComfyTargetConfiguration:
        """Build a validated target configuration from a Settings draft."""

        host = draft.host.strip()
        validation_message = _endpoint_validation_message(host, draft.port)
        if validation_message is not None:
            raise ValueError(validation_message)
        endpoint = ComfyEndpoint(host=host, port=draft.port)
        if draft.mode is ComfyTargetMode.MANAGED_LOCAL:
            if draft.managed_workspace_path is None:
                raise ValueError("Managed local setup requires a ComfyUI folder.")
            return ComfyTargetConfiguration(
                mode=ComfyTargetMode.MANAGED_LOCAL,
                endpoint=endpoint,
                workspace_path=draft.managed_workspace_path.resolve(),
                install_owned=True,
                launch_owned=True,
            )
        if draft.mode is ComfyTargetMode.ATTACHED_LOCAL:
            if draft.attached_workspace_path is None:
                raise ValueError("Existing local setup requires a ComfyUI folder.")
            workspace = draft.attached_workspace_path.resolve()
            if not self.checks.attached_workspace_exists(workspace):
                raise ValueError(f"Existing ComfyUI folder does not exist: {workspace}")
            return ComfyTargetConfiguration(
                mode=ComfyTargetMode.ATTACHED_LOCAL,
                endpoint=endpoint,
                workspace_path=workspace,
                install_owned=False,
                launch_owned=True,
            )
        return ComfyTargetConfiguration(
            mode=ComfyTargetMode.REMOTE,
            endpoint=endpoint,
            workspace_path=None,
            install_owned=False,
            launch_owned=False,
        )

    def _validate_save_reachability(
        self,
        target: ComfyTargetConfiguration,
    ) -> ComfyConnectionSaveResult | None:
        """Return a failed save result when target reachability blocks saving."""

        if target.mode in {
            ComfyTargetMode.MANAGED_LOCAL,
            ComfyTargetMode.ATTACHED_LOCAL,
        }:
            return None
        if self.checks.is_target_endpoint_reachable(target):
            return None
        message = (
            f"ComfyUI did not respond at {target.endpoint.host}:{target.endpoint.port}."
        )
        log_warning(
            _LOGGER,
            "Comfy connection settings save blocked by unreachable endpoint",
            mode=target.mode.value,
            host=target.endpoint.host,
            port=target.endpoint.port,
            has_workspace=target.workspace_path is not None,
            reason=message,
        )
        return ComfyConnectionSaveResult(
            target=target,
            succeeded=False,
            message=message,
            restart_required=False,
        )

    def _active_target(self) -> ComfyTargetConfiguration:
        """Return the target baseline active in this process."""

        if self._active_target_baseline is None:
            persisted = self.target_service.load_persisted()
            self._active_target_baseline = (
                persisted or self.target_service.create_default()
            )
        return self._active_target_baseline

    def _load_model_root_config(
        self,
        target: ComfyTargetConfiguration,
    ) -> ManagedModelRootConfigProtocol | None:
        """Load managed model-root state and capture its active baseline."""

        if (
            self.model_root_store is None
            or target.mode is not ComfyTargetMode.MANAGED_LOCAL
            or target.workspace_path is None
        ):
            return None
        config = self.model_root_store.load(target.workspace_path)
        self._active_model_root_baselines.setdefault(
            config.workspace,
            config.effective_model_root,
        )
        return config

    def _model_root_baseline(self, workspace: Path) -> Path:
        """Return the process-local model-root baseline for one workspace."""

        baseline = self._active_model_root_baselines.get(workspace)
        if baseline is not None:
            return baseline
        if self.model_root_store is None:
            return workspace / "models"
        config = self.model_root_store.load(workspace)
        self._active_model_root_baselines[config.workspace] = (
            config.effective_model_root
        )
        return config.effective_model_root

    def _save_model_root(
        self,
        target: ComfyTargetConfiguration,
        draft: ComfyConnectionSettingsDraft,
    ) -> ManagedModelRootConfigProtocol | None:
        """Persist managed model-root state when the target is managed local."""

        if (
            self.model_root_store is None
            or target.mode is not ComfyTargetMode.MANAGED_LOCAL
            or target.workspace_path is None
        ):
            return None
        requested_root = (
            None if draft.managed_model_root_uses_default else draft.managed_model_root
        )
        return self.model_root_store.save(target.workspace_path, requested_root)

    def _register_restart_requirements(
        self,
        *,
        active_target: ComfyTargetConfiguration,
        saved_target: ComfyTargetConfiguration,
        model_root_config: ManagedModelRootConfigProtocol | None,
    ) -> RestartRequirementSnapshot | None:
        """Register restart deltas after a successful settings save."""

        if self.restart_requirements is None:
            return None
        snapshot = self.restart_requirements.register_delta(
            key=_CONNECTION_RESTART_KEY,
            label="ComfyUI connection",
            active_value=_target_restart_value(active_target),
            saved_value=_target_restart_value(saved_target),
            scope=RestartScope.FULL_APP,
            detail="Substitute will use the saved ComfyUI connection after restart.",
        )
        if model_root_config is None:
            snapshot = self.restart_requirements.clear(_MODEL_ROOT_RESTART_KEY)
            return snapshot
        active_model_root = self._model_root_baseline(model_root_config.workspace)
        return self.restart_requirements.register_delta(
            key=_MODEL_ROOT_RESTART_KEY,
            label="Model folder",
            active_value=_path_restart_value(active_model_root),
            saved_value=_path_restart_value(model_root_config.effective_model_root),
            scope=RestartScope.FULL_APP,
            detail="ComfyUI will use the selected model folder after restart.",
        )


def _endpoint_validation_message(host: str, port: int) -> str | None:
    """Return a user-facing endpoint validation error when input is invalid."""

    if not host:
        return "Host cannot be blank."
    if port < _MIN_PORT or port > _MAX_PORT:
        return "Port must be between 1 and 65535."
    return None


def _status_message(
    target: ComfyTargetConfiguration,
    *,
    persisted_exists: bool,
) -> str:
    """Return the summary shown before the user tests the endpoint."""

    if not persisted_exists:
        return (
            "Substitute is showing the default managed ComfyUI connection because "
            "no saved connection exists yet."
        )
    return (
        f"Substitute is configured to use {_target_mode_label(target.mode)} at "
        f"{target.endpoint.host}:{target.endpoint.port}."
    )


def _target_mode_label(mode: ComfyTargetMode) -> str:
    """Return a compact user-facing label for one target mode."""

    if mode is ComfyTargetMode.MANAGED_LOCAL:
        return "managed ComfyUI"
    if mode is ComfyTargetMode.ATTACHED_LOCAL:
        return "existing local ComfyUI"
    return "remote ComfyUI"


def _target_restart_value(target: ComfyTargetConfiguration) -> str:
    """Return a stable comparison string for Comfy target restart deltas."""

    workspace = (
        _path_restart_value(target.workspace_path)
        if target.workspace_path is not None
        else ""
    )
    return "|".join(
        (
            target.mode.value,
            target.endpoint.host,
            str(target.endpoint.port),
            workspace,
            str(target.install_owned),
            str(target.launch_owned),
        )
    )


def _path_restart_value(path: Path) -> str:
    """Return a normalized path string for restart delta comparison."""

    return str(path.resolve())


__all__ = [
    "ComfyConnectionReadinessChecks",
    "ComfyConnectionSaveResult",
    "ComfyConnectionSettingsDraft",
    "ComfyConnectionSettingsService",
    "ComfyConnectionSettingsSnapshot",
    "ManagedModelRootConfigProtocol",
    "ManagedModelRootStoreProtocol",
]
