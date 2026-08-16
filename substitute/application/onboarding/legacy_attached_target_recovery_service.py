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

"""Recover the legacy interrupted target state without changing valid setups."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.setup_transaction_service import (
    SetupTransactionService,
)
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionMode,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.legacy_attached_target_recovery_service")


class LegacyAttachedTargetRecoveryChecks(Protocol):
    """Describe filesystem and endpoint checks used by legacy recovery."""

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the configured Comfy endpoint responds."""

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return whether the workspace satisfies managed launch requirements."""


def recover_legacy_attached_managed_target(
    *,
    comfy_target_service: ComfyTargetService,
    managed_runtime_service: ManagedRuntimeService,
    setup_transaction_service: SetupTransactionService,
    checks: LegacyAttachedTargetRecoveryChecks,
) -> None:
    """Recover an interrupted repair that saved managed Comfy as attached-local."""

    target = comfy_target_service.load_persisted()
    if target is None or target.mode is not ComfyTargetMode.ATTACHED_LOCAL:
        return
    if not _has_matching_repair_transaction(
        setup_transaction_service=setup_transaction_service,
        target=target,
    ):
        return
    workspace = target.workspace_path
    if workspace is None or not _is_localhost(target.endpoint.host):
        return
    managed_runtime = managed_runtime_service.load_persisted()
    if managed_runtime is None or checks.is_target_endpoint_reachable(target):
        return
    if not checks.is_managed_workspace_launchable(workspace):
        return
    managed_runtime_service.save_active_configuration(
        managed_runtime.for_workspace(workspace)
    )
    recovered_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=target.endpoint,
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    comfy_target_service.configure(recovered_target)
    _discard_matching_attached_pending_transaction(
        setup_transaction_service=setup_transaction_service,
        recovered_target=recovered_target,
    )
    log_warning(
        _LOGGER,
        "Recovered stale attached-local target as managed-local.",
        workspace=workspace,
        host=target.endpoint.host,
        port=target.endpoint.port,
    )


def discard_stale_attached_pending_for_active_managed_target(
    *,
    comfy_target_service: ComfyTargetService,
    setup_transaction_service: SetupTransactionService,
) -> None:
    """Discard stale attached-local pending state after active target recovery."""

    recovered_target = comfy_target_service.load_persisted()
    if (
        recovered_target is None
        or recovered_target.mode is not ComfyTargetMode.MANAGED_LOCAL
    ):
        return
    _discard_matching_attached_pending_transaction(
        setup_transaction_service=setup_transaction_service,
        recovered_target=recovered_target,
    )


def _has_matching_repair_transaction(
    *,
    setup_transaction_service: SetupTransactionService,
    target: ComfyTargetConfiguration,
) -> bool:
    """Return whether durable repair state proves this is the legacy failure."""

    try:
        transaction = setup_transaction_service.load()
    except Exception as error:
        log_info(
            _LOGGER,
            "Could not load setup transaction during target recovery.",
            error=error,
        )
        return False
    return (
        transaction is not None
        and transaction.mode is SetupTransactionMode.REPAIR
        and _pending_matches_recovered_target(
            transaction=transaction,
            recovered_target=target,
        )
    )


def _discard_matching_attached_pending_transaction(
    *,
    setup_transaction_service: SetupTransactionService,
    recovered_target: ComfyTargetConfiguration,
) -> None:
    """Discard stale pending attached-local state superseded by target recovery."""

    try:
        transaction = setup_transaction_service.load()
    except Exception as error:
        log_info(
            _LOGGER,
            "Could not load pending setup transaction during target recovery.",
            error=error,
        )
        return
    if transaction is None or not _pending_matches_recovered_target(
        transaction=transaction,
        recovered_target=recovered_target,
    ):
        return
    setup_transaction_service.discard(transaction.transaction_id)


def _pending_matches_recovered_target(
    *,
    transaction: SetupTransaction,
    recovered_target: ComfyTargetConfiguration,
) -> bool:
    """Return whether pending state repeats the stale attached-local target."""

    pending_target = transaction.target
    if pending_target is None:
        return False
    return (
        pending_target.mode is ComfyTargetMode.ATTACHED_LOCAL
        and pending_target.workspace_path == recovered_target.workspace_path
        and pending_target.endpoint == recovered_target.endpoint
    )


def _is_localhost(host: str) -> bool:
    """Return whether one host string points at this machine."""

    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


__all__ = [
    "LegacyAttachedTargetRecoveryChecks",
    "discard_stale_attached_pending_for_active_managed_target",
    "recover_legacy_attached_managed_target",
]
