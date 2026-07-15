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

"""Coordinate persisted managed Comfy runtime selection and health state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from substitute.application.ports.managed_runtime_repository import (
    ManagedRuntimeConfigurationRepository,
)
from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionPolicy,
    ManagedRuntimeSelectionUnavailableError,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeValidationStatus,
)
from substitute.shared.logging.logger import get_logger, log_info


_LOGGER = get_logger("application.onboarding.managed_runtime_service")


@dataclass
class ManagedRuntimeService:
    """Own the selected managed install strategy and latest runtime health record."""

    repository: ManagedRuntimeConfigurationRepository
    selection_policy: ManagedRuntimeSelectionPolicy

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Load persisted managed runtime state when it exists."""

        if not self.repository.exists():
            return None
        return self.repository.load()

    def create_default(self) -> ManagedRuntimeConfiguration:
        """Create the default managed runtime configuration without persisting it."""

        return self.repository.build_default()

    def load_draft_configuration(self) -> ManagedRuntimeConfiguration:
        """Load an onboarding-safe configuration without requiring managed support."""

        persisted = self.load_persisted()
        if persisted is not None:
            return persisted
        try:
            return self.select_configuration()
        except ManagedRuntimeSelectionUnavailableError as error:
            log_info(
                _LOGGER,
                "Managed runtime selection deferred while opening onboarding.",
                reason=str(error),
            )
            return self.create_default()

    def save(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Persist the supplied managed runtime configuration."""

        return self.save_active_configuration(configuration)

    def save_active_configuration(
        self,
        configuration: ManagedRuntimeConfiguration,
    ) -> ManagedRuntimeConfiguration:
        """Persist the supplied managed runtime configuration as active state."""

        self.repository.save(configuration)
        return configuration

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Detect hardware and return a managed install strategy without saving."""

        return self.selection_policy.select_configuration(
            force_cpu_mode=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
        )

    def detect_and_select(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Detect hardware and persist the selected managed install strategy."""

        configuration = self.select_configuration(
            force_cpu_mode=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
        )
        return self.save_active_configuration(configuration)

    def record_active_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Persist the latest active managed runtime validation outcome."""

        return self.record_validation(status=status, detail=detail)

    def record_active_launch(
        self,
        *,
        status: ManagedRuntimeLaunchStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Persist the latest active launch or listener ownership outcome."""

        return self.record_launch(status=status, detail=detail)

    def record_validation(
        self,
        *,
        status: ManagedRuntimeValidationStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Persist the latest managed runtime validation outcome."""

        current = self.load_persisted() or self.create_default()
        updated = ManagedRuntimeConfiguration(
            workspace_path=current.workspace_path,
            detected_platform=current.detected_platform,
            detected_accelerator=current.detected_accelerator,
            detected_adapter_name=current.detected_adapter_name,
            install_target=current.install_target,
            python_version=current.python_version,
            python_fallback_used=current.python_fallback_used,
            comfy_channel=current.comfy_channel,
            backend_policy=current.backend_policy,
            torch_release_channel=current.torch_release_channel,
            torch_selection_reason=current.torch_selection_reason,
            torch_fallback_used=current.torch_fallback_used,
            stability=current.stability,
            prefer_edge_torch=current.prefer_edge_torch,
            prefer_edge_comfy_channel=current.prefer_edge_comfy_channel,
            force_cpu_mode=current.force_cpu_mode,
            validation_status=status,
            validation_detail=detail,
            last_validation_at=_timestamp_now(),
            launch_status=current.launch_status,
            launch_detail=current.launch_detail,
            last_launch_at=current.last_launch_at,
        )
        return self.save(updated)

    def record_launch(
        self,
        *,
        status: ManagedRuntimeLaunchStatus,
        detail: str | None,
    ) -> ManagedRuntimeConfiguration:
        """Persist the latest managed runtime launch or listener ownership outcome."""

        current = self.load_persisted() or self.create_default()
        updated = ManagedRuntimeConfiguration(
            workspace_path=current.workspace_path,
            detected_platform=current.detected_platform,
            detected_accelerator=current.detected_accelerator,
            detected_adapter_name=current.detected_adapter_name,
            install_target=current.install_target,
            python_version=current.python_version,
            python_fallback_used=current.python_fallback_used,
            comfy_channel=current.comfy_channel,
            backend_policy=current.backend_policy,
            torch_release_channel=current.torch_release_channel,
            torch_selection_reason=current.torch_selection_reason,
            torch_fallback_used=current.torch_fallback_used,
            stability=current.stability,
            prefer_edge_torch=current.prefer_edge_torch,
            prefer_edge_comfy_channel=current.prefer_edge_comfy_channel,
            force_cpu_mode=current.force_cpu_mode,
            validation_status=current.validation_status,
            validation_detail=current.validation_detail,
            last_validation_at=current.last_validation_at,
            launch_status=status,
            launch_detail=detail,
            last_launch_at=_timestamp_now(),
        )
        return self.save(updated)

    def record_torch_resolution(
        self,
        *,
        backend_policy: str,
        torch_release_channel: str,
        torch_selection_reason: str,
        torch_fallback_used: bool,
    ) -> ManagedRuntimeConfiguration:
        """Persist the resolved torch backend/channel selected for this runtime."""

        current = self.load_persisted() or self.create_default()
        updated = ManagedRuntimeConfiguration(
            workspace_path=current.workspace_path,
            detected_platform=current.detected_platform,
            detected_accelerator=current.detected_accelerator,
            detected_adapter_name=current.detected_adapter_name,
            install_target=current.install_target,
            python_version=current.python_version,
            python_fallback_used=current.python_fallback_used,
            comfy_channel=current.comfy_channel,
            backend_policy=backend_policy,
            torch_release_channel=torch_release_channel,
            torch_selection_reason=torch_selection_reason,
            torch_fallback_used=torch_fallback_used,
            stability=current.stability,
            prefer_edge_torch=current.prefer_edge_torch,
            prefer_edge_comfy_channel=current.prefer_edge_comfy_channel,
            force_cpu_mode=current.force_cpu_mode,
            validation_status=current.validation_status,
            validation_detail=current.validation_detail,
            last_validation_at=current.last_validation_at,
            launch_status=current.launch_status,
            launch_detail=current.launch_detail,
            last_launch_at=current.last_launch_at,
        )
        return self.save(updated)


def _timestamp_now() -> str:
    """Return one UTC ISO timestamp for managed runtime persistence."""

    return datetime.now(UTC).isoformat()


__all__ = ["ManagedRuntimeService"]
