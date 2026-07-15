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

"""Expose the final managed-local Comfy lifecycle facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_launcher import (
    ManagedComfyState,
    start_managed_comfy_background,
    start_managed_comfy_subprocess,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationResult,
    ManagedProcessTerminationStatus,
    kill_managed_comfy,
    kill_managed_comfy_metadata,
)
from substitute.shared.logging.logger import get_logger, log_info

ensure_comfyui_setup = ensure_managed_comfy_setup
start_comfyui_background_managed = start_managed_comfy_background
start_comfyui_subprocess = start_managed_comfy_subprocess
kill_comfyui = kill_managed_comfy
_LOGGER = get_logger("infrastructure.comfy.process_manager")


@dataclass(frozen=True)
class ManagedComfyStateCleanupResult:
    """Describe the observed result of cleaning one managed ComfyUI state."""

    pid: int | None
    host: str | None
    port: int | None
    workspace: Path | None
    managed_resource_present: bool
    live_process_present: bool
    metadata_present: bool
    used_persisted_metadata: bool
    termination_attempted: bool
    registry_cleared: bool
    termination: ManagedProcessTerminationResult | None
    termination_status: ManagedProcessTerminationStatus | None
    user_safe_detail: str
    diagnostic_detail: str


def kill_comfyui_state(
    state: ManagedComfyState | None,
) -> ManagedComfyStateCleanupResult:
    """Terminate the managed ComfyUI instance represented by one lifecycle state."""

    if state is None:
        return ManagedComfyStateCleanupResult(
            pid=None,
            host=None,
            port=None,
            workspace=None,
            managed_resource_present=False,
            live_process_present=False,
            metadata_present=False,
            used_persisted_metadata=False,
            termination_attempted=False,
            registry_cleared=False,
            termination=None,
            termination_status=None,
            user_safe_detail="No managed ComfyUI cleanup was required.",
            diagnostic_detail="No managed ComfyUI state was available for cleanup.",
        )
    process = state.proc
    metadata = state.metadata
    live_process_present = process is not None and process.poll() is None
    metadata_present = metadata is not None
    if process is None and metadata is None:
        return ManagedComfyStateCleanupResult(
            pid=None,
            host=None,
            port=None,
            workspace=None,
            managed_resource_present=False,
            live_process_present=False,
            metadata_present=False,
            used_persisted_metadata=False,
            termination_attempted=False,
            registry_cleared=False,
            termination=None,
            termination_status=None,
            user_safe_detail="No managed ComfyUI cleanup was required.",
            diagnostic_detail=(
                "Managed ComfyUI cleanup found no live process handle or ownership metadata."
            ),
        )
    host = metadata.host if metadata is not None else None
    port = metadata.port if metadata is not None else None
    workspace = metadata.workspace_path if metadata is not None else None
    if process is not None:
        termination = (
            kill_managed_comfy_metadata(
                metadata,
                containment_handle=state.containment_handle,
            )
            if metadata is not None
            else kill_managed_comfy(process)
        )
        registry_cleared = _clear_registry_if_terminated(
            state, termination.pid, termination
        )
        return ManagedComfyStateCleanupResult(
            pid=termination.pid,
            host=host,
            port=port,
            workspace=workspace,
            managed_resource_present=True,
            live_process_present=live_process_present,
            metadata_present=metadata_present,
            used_persisted_metadata=False,
            termination_attempted=termination.attempted,
            registry_cleared=registry_cleared,
            termination=termination,
            termination_status=termination.status,
            user_safe_detail=termination.user_safe_detail,
            diagnostic_detail=termination.diagnostic_detail,
        )
    assert metadata is not None
    termination = kill_managed_comfy_metadata(
        metadata,
        containment_handle=state.containment_handle,
    )
    registry_cleared = _clear_registry_if_terminated(state, metadata.pid, termination)
    return ManagedComfyStateCleanupResult(
        pid=metadata.pid,
        host=host,
        port=port,
        workspace=workspace,
        managed_resource_present=True,
        live_process_present=False,
        metadata_present=True,
        used_persisted_metadata=True,
        termination_attempted=termination.attempted,
        registry_cleared=registry_cleared,
        termination=termination,
        termination_status=termination.status,
        user_safe_detail=termination.user_safe_detail,
        diagnostic_detail=termination.diagnostic_detail,
    )


def _clear_registry_if_terminated(
    state: ManagedComfyState,
    pid: int | None,
    termination: ManagedProcessTerminationResult,
) -> bool:
    """Clear persisted ownership metadata only after verified termination."""

    if termination.status is not ManagedProcessTerminationStatus.TERMINATED_CONFIRMED:
        return False
    registry_before_clear = state.registry.load()
    matching_registry_pid = (
        registry_before_clear.pid if registry_before_clear is not None else None
    )
    state.registry.clear_if_pid_matches(pid)
    registry_after_clear = state.registry.load()
    registry_cleared = matching_registry_pid == pid and registry_after_clear is None
    if registry_cleared:
        log_info(_LOGGER, "Managed process registry metadata cleared", pid=pid)
    return registry_cleared


__all__ = [
    "ManagedComfyState",
    "ManagedComfyStateCleanupResult",
    "ensure_comfyui_setup",
    "kill_comfyui",
    "kill_comfyui_state",
    "start_comfyui_background_managed",
    "start_comfyui_subprocess",
]
