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

"""Settle Comfy-Manager's intentional startup-deferred Registry updates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import tempfile

from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.comfy_manager_runtime import (
    ComfyManagerCommandRunner,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CLI_INSTALL_TIMEOUT_SECONDS,
    CoreComfyNodepack,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.nodepack_registry_update_settler")


@dataclass(frozen=True, slots=True)
class RegistryUpdateSettlement:
    """Describe whether Manager completed its own queued startup work."""

    succeeded: bool
    output: tuple[str, ...]


class ComfyNodepackRegistryUpdateSettler:
    """Run Manager's pre-startup owner after it defers an exact update."""

    def settle(
        self,
        *,
        manager_runtime: ComfyManagerRuntime,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> RegistryUpdateSettlement:
        """Execute Manager's queued switch before Comfy imports custom nodes."""

        message = (
            f"[ComfyNodepacks] Applying Comfy-Manager's queued update for "
            f"{nodepack.registry_id}@{nodepack.required_version}."
        )
        self._emit_info(on_log, message, nodepack=nodepack)
        command_runner = ComfyManagerCommandRunner(
            runtime=manager_runtime,
            env=env,
        )
        with tempfile.TemporaryDirectory(prefix="substitute-comfy-manager-") as temp:
            session_path = Path(temp) / "session"
            process_result = command_runner.settle_registry_updates(
                session_path=session_path,
                on_line=on_log,
                timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
            )
            reboot_requested = session_path.with_suffix(".reboot").is_file()
        if process_result is None:
            unavailable = (
                "Comfy-Manager deferred the Registry update, but its pre-startup "
                "executor is unavailable in the selected Python environment."
            )
            self._emit_warning(on_log, unavailable, nodepack=nodepack)
            return RegistryUpdateSettlement(False, (unavailable,))
        exit_code, output = process_result

        succeeded = exit_code == 0 and reboot_requested
        if not succeeded:
            self._emit_warning(
                on_log,
                "Comfy-Manager did not confirm execution of its queued update.",
                nodepack=nodepack,
            )
        return RegistryUpdateSettlement(succeeded, output)

    @staticmethod
    def _emit_info(
        callback: LogCallback | None,
        message: str,
        *,
        nodepack: CoreComfyNodepack,
    ) -> None:
        """Emit one structured settlement progress record."""

        log_info(_LOGGER, message, nodepack_id=nodepack.nodepack_id.value)
        if callback is not None:
            callback(message)

    @staticmethod
    def _emit_warning(
        callback: LogCallback | None,
        message: str,
        *,
        nodepack: CoreComfyNodepack,
    ) -> None:
        """Emit one actionable settlement failure record."""

        log_warning(_LOGGER, message, nodepack_id=nodepack.nodepack_id.value)
        if callback is not None:
            callback(message)


__all__ = [
    "ComfyNodepackRegistryUpdateSettler",
    "RegistryUpdateSettlement",
]
