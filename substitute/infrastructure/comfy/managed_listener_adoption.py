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

"""Resolve verified listener ownership before admitting a managed launch."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
)
from substitute.domain.onboarding import ManagedRuntimeLaunchStatus
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerStatus,
    probe_managed_listener,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_termination_result import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    kill_managed_comfy_metadata,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
)


_LOGGER = get_logger("infrastructure.comfy.managed_listener_adoption")


def resolve_managed_listener(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    registry: ManagedProcessRegistry,
    runtime_service: ManagedRuntimeService,
) -> ManagedProcessMetadata | None:
    """Resolve the endpoint ownership state before launching a managed process."""

    metadata = registry.load()
    probe = probe_managed_listener(
        host=endpoint.host,
        port=endpoint.port,
        workspace=workspace,
        metadata=metadata,
    )
    if probe.status is ManagedListenerStatus.ABSENT:
        if metadata is not None:
            registry.clear()
        return None
    if probe.status is ManagedListenerStatus.OWNED_HEALTHY:
        log_info(
            _LOGGER,
            "Reusing healthy owned managed ComfyUI listener",
            pid=probe.metadata.pid if probe.metadata is not None else None,
            host=endpoint.host,
            port=endpoint.port,
        )
        return probe.metadata
    if probe.status is ManagedListenerStatus.OWNED_STALE:
        stale_pid = probe.metadata.pid if probe.metadata is not None else None
        assert probe.metadata is not None
        termination = kill_managed_comfy_metadata(probe.metadata)
        runtime_service.record_launch(
            status=ManagedRuntimeLaunchStatus.STALE_REAPED,
            detail=probe.reason,
        )
        if (
            termination.status
            is not ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
        ):
            raise RuntimeError(
                "Native cleanup of the owned managed ComfyUI resource could not "
                "be confirmed."
            )
        registry.clear_if_pid_matches(stale_pid)
        return None
    if probe.status is ManagedListenerStatus.UNKNOWN:
        runtime_service.record_launch(
            status=ManagedRuntimeLaunchStatus.UNKNOWN,
            detail=probe.reason,
        )
        raise RuntimeError(
            "Substitute could not verify ownership of the process using the managed "
            f"ComfyUI address {endpoint.host}:{endpoint.port}."
        )
    runtime_service.record_launch(
        status=ManagedRuntimeLaunchStatus.FOREIGN_LISTENER_BLOCKED,
        detail=probe.reason,
    )
    raise RuntimeError(
        "Another process is already using the managed ComfyUI address "
        f"{endpoint.host}:{endpoint.port}. Substitute will not start over a "
        "foreign listener."
    )
