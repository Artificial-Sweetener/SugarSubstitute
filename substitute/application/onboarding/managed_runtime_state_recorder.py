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

"""Record managed runtime install state into active or pending storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding.setup_transaction_models import SetupTransaction
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.onboarding.managed_runtime_state_recorder")


class ManagedRuntimeStateRecorder(Protocol):
    """Record managed runtime setup progress without defining where it is stored."""

    def record_selection(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Record selected managed runtime configuration."""

    def record_torch_resolution(
        self,
        *,
        backend_policy: str,
        torch_release_channel: str,
        torch_selection_reason: str,
        torch_fallback_used: bool,
    ) -> ManagedRuntimeConfiguration:
        """Record the selected torch backend details."""

    def record_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Record one managed runtime validation result."""

    def record_failure(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Record one managed runtime provisioning failure."""


class SetupTransactionRecorderService(Protocol):
    """Describe the transaction operations needed by pending runtime recorders."""

    def load(self) -> SetupTransaction | None:
        """Load the current pending setup transaction."""

    def record_managed_runtime(
        self,
        transaction_id: str,
        managed_runtime: ManagedRuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending managed runtime configuration."""


@dataclass
class NoOpManagedRuntimeStateRecorder(ManagedRuntimeStateRecorder):
    """Ignore managed runtime state updates for call sites without persistence."""

    configuration: ManagedRuntimeConfiguration = ManagedRuntimeConfiguration()

    def record_selection(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Return the selected configuration without saving it."""

        self.configuration = configuration
        return self.configuration

    def record_torch_resolution(
        self,
        *,
        backend_policy: str,
        torch_release_channel: str,
        torch_selection_reason: str,
        torch_fallback_used: bool,
    ) -> ManagedRuntimeConfiguration:
        """Return an in-memory copy with torch resolution details."""

        self.configuration = _with_torch_resolution(
            self.configuration,
            backend_policy=backend_policy,
            torch_release_channel=torch_release_channel,
            torch_selection_reason=torch_selection_reason,
            torch_fallback_used=torch_fallback_used,
        )
        return self.configuration

    def record_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Return an in-memory copy with validation details."""

        self.configuration = _with_validation(
            self.configuration,
            status=status,
            detail=detail,
        )
        return self.configuration

    def record_failure(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Return an in-memory copy with failure details."""

        return self.record_validation(status=status, detail=detail)


@dataclass
class PendingManagedRuntimeStateRecorder(ManagedRuntimeStateRecorder):
    """Record managed runtime setup progress into one setup transaction."""

    transaction_service: SetupTransactionRecorderService
    transaction_id: str

    def record_selection(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Record selected managed runtime configuration in pending state."""

        self.transaction_service.record_managed_runtime(
            self.transaction_id,
            configuration,
        )
        return configuration

    def record_torch_resolution(
        self,
        *,
        backend_policy: str,
        torch_release_channel: str,
        torch_selection_reason: str,
        torch_fallback_used: bool,
    ) -> ManagedRuntimeConfiguration:
        """Record selected torch backend details in pending state."""

        configuration = _with_torch_resolution(
            self._current(),
            backend_policy=backend_policy,
            torch_release_channel=torch_release_channel,
            torch_selection_reason=torch_selection_reason,
            torch_fallback_used=torch_fallback_used,
        )
        self.transaction_service.record_managed_runtime(
            self.transaction_id,
            configuration,
        )
        return configuration

    def record_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Record validation details in pending state."""

        configuration = _with_validation(
            self._current(),
            status=status,
            detail=detail,
        )
        self.transaction_service.record_managed_runtime(
            self.transaction_id,
            configuration,
        )
        return configuration

    def record_failure(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Record failure details in pending state."""

        return self.record_validation(status=status, detail=detail)

    def _current(self) -> ManagedRuntimeConfiguration:
        """Return the latest pending managed runtime configuration."""

        transaction = self.transaction_service.load()
        if transaction is None or transaction.managed_runtime is None:
            return ManagedRuntimeConfiguration()
        return transaction.managed_runtime


@dataclass
class ActiveSafeManagedRuntimeStateRecorder(ManagedRuntimeStateRecorder):
    """Record active launch state without downgrading a valid runtime on failure."""

    runtime_service: ManagedRuntimeService

    def record_selection(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Persist selection only when no valid active selection exists."""

        current = self.runtime_service.load_persisted()
        if (
            current is not None
            and current.validation_status is ManagedRuntimeValidationStatus.VALID
        ):
            return current
        return self.runtime_service.save_active_configuration(configuration)

    def record_torch_resolution(
        self,
        *,
        backend_policy: str,
        torch_release_channel: str,
        torch_selection_reason: str,
        torch_fallback_used: bool,
    ) -> ManagedRuntimeConfiguration:
        """Persist selected torch backend details into active state."""

        return self.runtime_service.record_torch_resolution(
            backend_policy=backend_policy,
            torch_release_channel=torch_release_channel,
            torch_selection_reason=torch_selection_reason,
            torch_fallback_used=torch_fallback_used,
        )

    def record_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Persist validation unless it would downgrade known-good active state."""

        current = self.runtime_service.load_persisted()
        if (
            current is not None
            and current.validation_status is ManagedRuntimeValidationStatus.VALID
            and status is not ManagedRuntimeValidationStatus.VALID
        ):
            log_info(
                _LOGGER,
                "Preserving valid active managed runtime during failed launch validation.",
                validation_status=status.value,
                detail=detail,
            )
            return current
        return self.runtime_service.record_active_validation(
            status=status,
            detail=detail,
        )

    def record_failure(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Record failure without downgrading a valid active runtime."""

        return self.record_validation(status=status, detail=detail)


def _with_torch_resolution(
    configuration: ManagedRuntimeConfiguration,
    *,
    backend_policy: str,
    torch_release_channel: str,
    torch_selection_reason: str,
    torch_fallback_used: bool,
) -> ManagedRuntimeConfiguration:
    """Return a copy with torch selection details updated."""

    return ManagedRuntimeConfiguration(
        workspace_path=configuration.workspace_path,
        detected_platform=configuration.detected_platform,
        detected_accelerator=configuration.detected_accelerator,
        detected_adapter_name=configuration.detected_adapter_name,
        install_target=configuration.install_target,
        python_version=configuration.python_version,
        python_fallback_used=configuration.python_fallback_used,
        comfy_channel=configuration.comfy_channel,
        backend_policy=backend_policy,
        torch_release_channel=torch_release_channel,
        torch_selection_reason=torch_selection_reason,
        torch_fallback_used=torch_fallback_used,
        stability=configuration.stability,
        prefer_edge_torch=configuration.prefer_edge_torch,
        prefer_edge_comfy_channel=configuration.prefer_edge_comfy_channel,
        force_cpu_mode=configuration.force_cpu_mode,
        validation_status=configuration.validation_status,
        validation_detail=configuration.validation_detail,
        last_validation_at=configuration.last_validation_at,
        launch_status=configuration.launch_status,
        launch_detail=configuration.launch_detail,
        last_launch_at=configuration.last_launch_at,
    )


def _with_validation(
    configuration: ManagedRuntimeConfiguration,
    *,
    status: ManagedRuntimeValidationStatus,
    detail: str | None,
) -> ManagedRuntimeConfiguration:
    """Return a copy with validation details updated."""

    return ManagedRuntimeConfiguration(
        workspace_path=configuration.workspace_path,
        detected_platform=configuration.detected_platform,
        detected_accelerator=configuration.detected_accelerator,
        detected_adapter_name=configuration.detected_adapter_name,
        install_target=configuration.install_target,
        python_version=configuration.python_version,
        python_fallback_used=configuration.python_fallback_used,
        comfy_channel=configuration.comfy_channel,
        backend_policy=configuration.backend_policy,
        torch_release_channel=configuration.torch_release_channel,
        torch_selection_reason=configuration.torch_selection_reason,
        torch_fallback_used=configuration.torch_fallback_used,
        stability=configuration.stability,
        prefer_edge_torch=configuration.prefer_edge_torch,
        prefer_edge_comfy_channel=configuration.prefer_edge_comfy_channel,
        force_cpu_mode=configuration.force_cpu_mode,
        validation_status=status,
        validation_detail=detail,
        last_validation_at=datetime.now(UTC).isoformat(),
        launch_status=configuration.launch_status,
        launch_detail=configuration.launch_detail,
        last_launch_at=configuration.last_launch_at,
    )


__all__ = [
    "ActiveSafeManagedRuntimeStateRecorder",
    "ManagedRuntimeStateRecorder",
    "NoOpManagedRuntimeStateRecorder",
    "PendingManagedRuntimeStateRecorder",
]
