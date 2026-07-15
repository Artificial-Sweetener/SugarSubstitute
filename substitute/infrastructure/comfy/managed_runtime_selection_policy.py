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

"""Select one managed runtime configuration from detected platform hardware."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionPolicy,
    ManagedRuntimeSelectionUnavailableError,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)
from substitute.infrastructure.comfy.hardware_detection import detect_hardware
from substitute.infrastructure.comfy.install_strategy import (
    select_install_strategy,
)


@dataclass(frozen=True)
class HardwareAwareManagedRuntimeSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Build managed runtime configuration from normalized hardware detection."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the managed runtime configuration selected for this machine."""

        detection = detect_hardware()
        try:
            strategy = select_install_strategy(
                detection=detection,
                force_cpu=force_cpu_mode,
                prefer_edge_torch=prefer_edge_torch,
                prefer_edge_comfy=prefer_edge_comfy_channel,
            )
        except ValueError as error:
            raise ManagedRuntimeSelectionUnavailableError(str(error)) from error
        adapter_name = detection.adapters[0].name if detection.adapters else None
        return ManagedRuntimeConfiguration(
            detected_platform=detection.platform.value,
            detected_accelerator=detection.preferred_accelerator.value,
            detected_adapter_name=adapter_name,
            install_target=strategy.target.value,
            python_version=strategy.python_runtime.selected_version,
            python_fallback_used=strategy.python_runtime.used_fallback,
            comfy_channel=strategy.comfy_channel.value,
            backend_policy=strategy.torch_policy.backend_key,
            torch_release_channel=strategy.torch_policy.release_channel.value,
            torch_selection_reason=strategy.torch_policy.selection_reason,
            torch_fallback_used=False,
            stability=(
                ManagedRuntimeStability.EXPERIMENTAL
                if strategy.stability == "experimental"
                else ManagedRuntimeStability.STABLE
            ),
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
            force_cpu_mode=force_cpu_mode,
            validation_status=ManagedRuntimeValidationStatus.UNKNOWN,
            launch_status=ManagedRuntimeLaunchStatus.UNKNOWN,
        )


__all__ = ["HardwareAwareManagedRuntimeSelectionPolicy"]
