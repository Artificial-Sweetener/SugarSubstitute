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

from datetime import UTC, datetime
from pathlib import Path

import pytest

from substitute.application.onboarding import (
    ComfyTargetService,
    InstallationService,
    ManagedRuntimeService,
    RuntimeService,
    SetupTransactionOptions,
    SetupTransactionService,
)
from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepositoryError,
)
from substitute.domain.onboarding import (
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeValidationStatus,
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.infrastructure.onboarding import (
    FileComfyTargetConfigurationRepository,
    FileInstallationConfigurationRepository,
    FileManagedRuntimeConfigurationRepository,
    FileRuntimeConfigurationRepository,
    FileSetupTransactionRepository,
)


from tests.support.onboarding.setup_transaction_state import (
    _StaticSelectionPolicy,
    _managed_target,
    _ready_runtime,
    _valid_managed_runtime,
)


def test_setup_transaction_repository_round_trips_pending_state(
    tmp_path: Path,
) -> None:
    """Pending setup transactions should survive JSON persistence."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _ready_runtime(installation)
    target = _managed_target(installation)
    managed_runtime = _valid_managed_runtime()
    repository = FileSetupTransactionRepository(installation.runtime_state_dir)
    transaction = SetupTransaction(
        schema_version=1,
        transaction_id="transaction-id",
        mode=SetupTransactionMode.REPAIR,
        status=SetupTransactionStatus.READY_TO_COMMIT,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        installation=installation,
        runtime=runtime,
        target=target,
        managed_runtime=managed_runtime,
        workspace_path=target.workspace_path,
        endpoint_host=target.endpoint.host,
        endpoint_port=target.endpoint.port,
        force_cpu_mode=True,
        failure=SetupTransactionFailure(
            code="example",
            message="example failure",
            recoverable=True,
            diagnostic_detail="detail",
        ),
    )

    repository.save(transaction)
    loaded = repository.load()

    assert loaded == transaction


def test_setup_transaction_repository_reports_corrupt_payload(
    tmp_path: Path,
) -> None:
    """Corrupt pending setup state should not be interpreted as active state."""

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "setup_transaction.json").write_text("{", encoding="utf-8")
    repository = FileSetupTransactionRepository(state_dir)

    with pytest.raises(SetupTransactionRepositoryError):
        repository.load()


def test_setup_transaction_service_commits_managed_transaction(
    tmp_path: Path,
) -> None:
    """Committing a valid managed transaction should write active files and clear pending."""

    installation = InstallationConfiguration.create_default(tmp_path)
    transaction_repository = FileSetupTransactionRepository(
        installation.runtime_state_dir
    )
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    runtime_service = RuntimeService(FileRuntimeConfigurationRepository(installation))
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    service = SetupTransactionService(
        repository=transaction_repository,
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    transaction = service.begin(
        mode=SetupTransactionMode.REPAIR,
        options=SetupTransactionOptions(
            workspace_path=installation.default_managed_comfy_dir,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
        ),
    )

    service.record_installation(transaction.transaction_id, installation)
    service.record_runtime(transaction.transaction_id, _ready_runtime(installation))
    service.record_target(transaction.transaction_id, _managed_target(installation))
    service.record_managed_runtime(
        transaction.transaction_id,
        _valid_managed_runtime(),
    )
    service.update_status(
        transaction.transaction_id,
        SetupTransactionStatus.READY_TO_COMMIT,
    )
    context = service.commit(transaction.transaction_id)

    assert context.comfy_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert transaction_repository.exists() is False
    assert (
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir)
        .load()
        .validation_status
        is ManagedRuntimeValidationStatus.VALID
    )
    assert (installation.user_settings_dir / "comfy_target.json").exists()
