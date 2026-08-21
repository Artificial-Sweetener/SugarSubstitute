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

"""Install exact core nodepack versions through the selected Comfy CLI."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.comfy_manager_runtime import (
    ComfyManagerCommandRunner,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CLI_INSTALL_TIMEOUT_SECONDS,
    CoreComfyNodepack,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.nodepack_registry_installer")


@dataclass(frozen=True, slots=True)
class RegistryInstallResult:
    """Return a classified Comfy CLI outcome with its diagnostic evidence."""

    outcome: RegistryInstallOutcome
    output: tuple[str, ...]


class ComfyNodepackRegistryInstaller:
    """Execute exact-version Registry installation through Comfy-owned tooling."""

    def install_exact(
        self,
        *,
        manager_runtime: ComfyManagerRuntime,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> RegistryInstallResult:
        """Ask Comfy Manager to install one exact Registry nodepack release."""

        command_runner = ComfyManagerCommandRunner(
            runtime=manager_runtime,
            env=env,
        )
        self._emit(
            on_log,
            (
                f"[ComfyNodepacks] Asking Comfy Registry for "
                f"{nodepack.registry_id}@{nodepack.required_version}."
            ),
        )
        process_result = command_runner.install_registry_nodepack(
            node_spec=f"{nodepack.registry_id}@{nodepack.required_version}",
            on_line=on_log,
            timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
        )
        if process_result is None:
            output: tuple[str, ...] = (
                "The selected Comfy environment exposes no supported Manager CLI.",
            )
            self._emit(on_log, output[0])
            return RegistryInstallResult(
                RegistryInstallOutcome.REGISTRY_UNREACHABLE,
                output,
            )
        exit_code, output = process_result
        return RegistryInstallResult(
            _classify_registry_result(exit_code=exit_code, output=output),
            output,
        )

    @staticmethod
    def _emit(callback: LogCallback | None, message: str) -> None:
        """Emit Registry activity to structured and setup logs."""

        log_info(_LOGGER, message)
        if callback is not None:
            callback(message)


def _classify_registry_result(
    *,
    exit_code: int,
    output: tuple[str, ...],
) -> RegistryInstallOutcome:
    """Classify known Comfy CLI outcomes without treating arbitrary errors as absence."""

    combined = "\n".join(output).casefold()
    if exit_code == 0 and "installation reserved:" in combined:
        return RegistryInstallOutcome.PENDING_STARTUP
    if "already installed" in combined or "[   skip" in combined:
        return RegistryInstallOutcome.ALREADY_INSTALLED
    if exit_code == 0 and "[installed]" in combined:
        return RegistryInstallOutcome.INSTALLED
    unavailable_markers = (
        "not available node:",
        "available version of",
        "node version not found",
        "version does not exist",
    )
    if any(marker in combined for marker in unavailable_markers):
        return RegistryInstallOutcome.VERSION_UNAVAILABLE
    unreachable_markers = (
        "cannot connect to comfyregistry",
        "failed to fetch",
        "connection refused",
        "connection timed out",
        "read timed out",
        "name resolution",
    )
    if any(marker in combined for marker in unreachable_markers):
        return RegistryInstallOutcome.REGISTRY_UNREACHABLE
    return RegistryInstallOutcome.FAILED


__all__ = ["ComfyNodepackRegistryInstaller", "RegistryInstallResult"]
