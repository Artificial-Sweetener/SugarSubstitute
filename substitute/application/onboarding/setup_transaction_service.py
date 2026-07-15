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

"""Coordinate pending setup transactions and active-state commits."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepository,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding.models import (
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.onboarding.setup_transaction_service")
_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SetupTransactionOptions:
    """Capture setup flags that must survive an interrupted flow."""

    workspace_path: Path | None = None
    endpoint_host: str | None = None
    endpoint_port: int | None = None
    force_cpu_mode: bool = False
    prefer_edge_torch: bool = False
    prefer_edge_comfy_channel: bool = False


@dataclass
class SetupTransactionService:
    """Own pending setup state and promote it to active config on success."""

    repository: SetupTransactionRepository
    installation_service: InstallationService
    runtime_service: RuntimeService
    comfy_target_service: ComfyTargetService
    managed_runtime_service: ManagedRuntimeService

    def load(self) -> SetupTransaction | None:
        """Load the current pending setup transaction when one exists."""

        return self.repository.load()

    def begin(
        self,
        *,
        mode: SetupTransactionMode,
        options: SetupTransactionOptions | None = None,
    ) -> SetupTransaction:
        """Create and persist a new pending setup transaction."""

        now = _timestamp_now()
        effective_options = options or SetupTransactionOptions()
        transaction = SetupTransaction(
            schema_version=_SCHEMA_VERSION,
            transaction_id=str(uuid4()),
            mode=mode,
            status=SetupTransactionStatus.CREATED,
            created_at=now,
            updated_at=now,
            workspace_path=effective_options.workspace_path,
            endpoint_host=effective_options.endpoint_host,
            endpoint_port=effective_options.endpoint_port,
            force_cpu_mode=effective_options.force_cpu_mode,
            prefer_edge_torch=effective_options.prefer_edge_torch,
            prefer_edge_comfy_channel=(effective_options.prefer_edge_comfy_channel),
        )
        self.repository.save(transaction)
        log_info(
            _LOGGER,
            "Setup transaction created.",
            transaction_id=transaction.transaction_id,
            mode=transaction.mode.value,
            status=transaction.status.value,
        )
        return transaction

    def update_status(
        self,
        transaction_id: str,
        status: SetupTransactionStatus,
    ) -> SetupTransaction:
        """Persist one setup transaction status transition."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(transaction, status=status, updated_at=_timestamp_now())
        )

    def record_installation(
        self,
        transaction_id: str,
        installation: InstallationConfiguration,
    ) -> SetupTransaction:
        """Record pending installation configuration."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(
                transaction,
                installation=installation,
                updated_at=_timestamp_now(),
            )
        )

    def record_runtime(
        self,
        transaction_id: str,
        runtime: RuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending runtime configuration."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(transaction, runtime=runtime, updated_at=_timestamp_now())
        )

    def record_target(
        self,
        transaction_id: str,
        target: ComfyTargetConfiguration,
    ) -> SetupTransaction:
        """Record pending Comfy target configuration."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(
                transaction,
                target=target,
                workspace_path=target.workspace_path,
                endpoint_host=target.endpoint.host,
                endpoint_port=target.endpoint.port,
                updated_at=_timestamp_now(),
            )
        )

    def record_managed_runtime(
        self,
        transaction_id: str,
        managed_runtime: ManagedRuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending managed runtime configuration."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(
                transaction,
                managed_runtime=managed_runtime,
                updated_at=_timestamp_now(),
            )
        )

    def record_failure(
        self,
        transaction_id: str,
        failure: SetupTransactionFailure,
    ) -> SetupTransaction:
        """Mark one transaction failed without changing active configuration."""

        transaction = self._load_required(transaction_id)
        return self._save(
            replace(
                transaction,
                status=SetupTransactionStatus.FAILED,
                failure=failure,
                updated_at=_timestamp_now(),
            )
        )

    def commit(self, transaction_id: str) -> InstallationContext:
        """Promote one complete pending transaction into active configuration."""

        transaction = self._load_required(transaction_id)
        self._validate_committable(transaction)
        assert transaction.installation is not None
        assert transaction.runtime is not None
        assert transaction.target is not None
        log_info(
            _LOGGER,
            "Setup transaction commit started.",
            transaction_id=transaction.transaction_id,
            mode=transaction.mode.value,
            target_mode=transaction.target.mode.value,
        )
        installation = self.installation_service.save(transaction.installation)
        runtime = self.runtime_service.save(transaction.runtime)
        if transaction.managed_runtime is not None:
            self.managed_runtime_service.save_active_configuration(
                transaction.managed_runtime
            )
        target = self.comfy_target_service.configure(transaction.target)
        self.repository.delete()
        log_info(
            _LOGGER,
            "Setup transaction commit finished.",
            transaction_id=transaction.transaction_id,
            target_mode=target.mode.value,
        )
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=target,
        )

    def discard(self, transaction_id: str) -> None:
        """Discard one pending setup transaction."""

        transaction = self._load_required(transaction_id)
        self.repository.delete()
        log_info(
            _LOGGER,
            "Setup transaction discarded.",
            transaction_id=transaction.transaction_id,
            mode=transaction.mode.value,
            status=transaction.status.value,
        )

    def _load_required(self, transaction_id: str) -> SetupTransaction:
        """Load the active transaction and require the expected id."""

        transaction = self.repository.load()
        if transaction is None:
            raise RuntimeError("No pending setup transaction exists.")
        if transaction.transaction_id != transaction_id:
            raise RuntimeError("Pending setup transaction id mismatch.")
        return transaction

    def _save(self, transaction: SetupTransaction) -> SetupTransaction:
        """Persist a transaction and log its new phase."""

        self.repository.save(transaction)
        log_info(
            _LOGGER,
            "Setup transaction updated.",
            transaction_id=transaction.transaction_id,
            mode=transaction.mode.value,
            status=transaction.status.value,
        )
        return transaction

    @staticmethod
    def _validate_committable(transaction: SetupTransaction) -> None:
        """Raise if one transaction is not complete enough to become active."""

        if transaction.status is not SetupTransactionStatus.READY_TO_COMMIT:
            raise RuntimeError("Setup transaction is not ready to commit.")
        if transaction.installation is None:
            raise RuntimeError("Setup transaction has no installation configuration.")
        if transaction.runtime is None:
            raise RuntimeError("Setup transaction has no runtime configuration.")
        if transaction.target is None:
            raise RuntimeError("Setup transaction has no Comfy target configuration.")
        if transaction.target.mode is ComfyTargetMode.MANAGED_LOCAL:
            if transaction.managed_runtime is None:
                raise RuntimeError(
                    "Managed setup transaction has no managed runtime configuration."
                )
            if (
                transaction.managed_runtime.validation_status
                is not ManagedRuntimeValidationStatus.VALID
            ):
                raise RuntimeError(
                    "Managed setup transaction has not passed validation."
                )


def _timestamp_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(UTC)


__all__ = [
    "SetupTransactionOptions",
    "SetupTransactionService",
]
