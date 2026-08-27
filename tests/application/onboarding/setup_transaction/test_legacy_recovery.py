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

"""Regression tests for interruption-safe setup transaction state."""

from __future__ import annotations

from pathlib import Path
from typing import cast


from substitute.application.onboarding import (
    ComfyTargetService,
    InstallationService,
    ManagedRuntimeService,
    RuntimeService,
    SetupTransactionOptions,
    SetupTransactionService,
)
from substitute.application.onboarding.legacy_attached_target_recovery_service import (
    discard_stale_attached_pending_for_active_managed_target,
    recover_legacy_attached_managed_target,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    SetupTransactionFailure,
    SetupTransactionMode,
)
from substitute.infrastructure.onboarding import (
    FileComfyTargetConfigurationRepository,
    FileInstallationConfigurationRepository,
    FileManagedRuntimeConfigurationRepository,
    FileRuntimeConfigurationRepository,
    FileSetupTransactionRepository,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    FileSystemReadinessChecks,
)


from tests.support.onboarding.setup_transaction_state import (
    _LegacyRecoveryChecks,
    _StaticSelectionPolicy,
    _managed_target,
    _valid_managed_runtime,
)


def test_legacy_attached_managed_target_recovery_restores_managed_mode(
    tmp_path: Path,
) -> None:
    """Old corrupted attached-local managed state should recover to managed-local."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=RuntimeService(
            FileRuntimeConfigurationRepository(installation)
        ),
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    stale_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=False,
        launch_owned=False,
    )
    installation_service.save(installation)
    assert stale_target.workspace_path is not None
    stale_target.workspace_path.mkdir(parents=True, exist_ok=True)
    target_service.configure(stale_target)
    managed_runtime_service.save_active_configuration(_valid_managed_runtime())
    transaction = setup_transaction_service.begin(
        mode=SetupTransactionMode.REPAIR,
        options=SetupTransactionOptions(
            workspace_path=stale_target.workspace_path,
            endpoint_host=stale_target.endpoint.host,
            endpoint_port=stale_target.endpoint.port,
        ),
    )
    setup_transaction_service.record_target(
        transaction.transaction_id,
        stale_target,
    )
    setup_transaction_service.record_failure(
        transaction.transaction_id,
        SetupTransactionFailure(
            code="endpoint_unreachable",
            message="ComfyUI did not respond.",
            recoverable=True,
        ),
    )

    recover_legacy_attached_managed_target(
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
        setup_transaction_service=setup_transaction_service,
        checks=cast(FileSystemReadinessChecks, _LegacyRecoveryChecks()),
    )

    recovered_target = target_service.load_persisted()
    recovered_runtime = managed_runtime_service.load_persisted()
    assert recovered_target is not None
    assert recovered_runtime is not None
    assert recovered_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert recovered_target.launch_owned is True
    assert recovered_runtime.workspace_path == str(
        stale_target.workspace_path.resolve()
    )
    assert not (stale_target.workspace_path / ".comfy_installed").exists()
    assert setup_transaction_service.load() is None


def test_legacy_recovery_preserves_completed_attached_local_target(
    tmp_path: Path,
) -> None:
    """Completed attached-local setup must remain attached while Comfy is offline."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=RuntimeService(
            FileRuntimeConfigurationRepository(installation)
        ),
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    attached_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=False,
        launch_owned=True,
    )
    installation_service.save(installation)
    assert attached_target.workspace_path is not None
    attached_target.workspace_path.mkdir(parents=True, exist_ok=True)
    target_service.configure(attached_target)
    managed_runtime_service.save_active_configuration(_valid_managed_runtime())

    recover_legacy_attached_managed_target(
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
        setup_transaction_service=setup_transaction_service,
        checks=cast(FileSystemReadinessChecks, _LegacyRecoveryChecks()),
    )

    assert target_service.load_persisted() == attached_target


def test_stale_attached_pending_is_discarded_when_active_target_is_managed(
    tmp_path: Path,
) -> None:
    """Failed attached pending state should not survive after active target recovery."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=RuntimeService(
            FileRuntimeConfigurationRepository(installation)
        ),
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    active_target = _managed_target(installation)
    stale_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=active_target.endpoint,
        workspace_path=active_target.workspace_path,
        install_owned=False,
        launch_owned=False,
    )
    installation_service.save(installation)
    target_service.configure(active_target)
    transaction = setup_transaction_service.begin(mode=SetupTransactionMode.REPAIR)
    setup_transaction_service.record_target(transaction.transaction_id, stale_target)
    setup_transaction_service.record_failure(
        transaction.transaction_id,
        SetupTransactionFailure(
            code="endpoint_unreachable",
            message="ComfyUI did not respond.",
            recoverable=True,
        ),
    )

    discard_stale_attached_pending_for_active_managed_target(
        comfy_target_service=target_service,
        setup_transaction_service=setup_transaction_service,
    )

    assert setup_transaction_service.load() is None
