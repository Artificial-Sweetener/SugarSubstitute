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

"""Coordinate Comfy process preflight and attached-Python recovery decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonSelectionSource,
    LocalComfyProcess,
    LocalComfyTerminationResult,
)


class LocalComfyProcessGateway(Protocol):
    """Inspect and explicitly terminate confidently identified Comfy processes."""

    def scan(self) -> tuple[LocalComfyProcess, ...]:
        """Return all confidently identified local ComfyUI processes."""

    def terminate(
        self,
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Terminate the supplied processes after revalidating their identity."""


class AttachedPythonGateway(Protocol):
    """Discover and validate Python bindings for one attached Comfy workspace."""

    def discover(self, workspace: Path) -> ComfyPythonDiscoveryResult:
        """Return automatic discovery evidence for a stopped workspace."""

    def probe(
        self,
        workspace: Path,
        executable: Path,
        *,
        source: ComfyPythonSelectionSource,
    ) -> ComfyPythonProbeResult:
        """Validate one explicit executable against the selected workspace."""


class AttachedPythonRecoveryState(str, Enum):
    """Describe the live recovery state shown after automatic discovery fails."""

    WAITING_FOR_LAUNCH = "waiting_for_launch"
    OTHER_COMFY_RUNNING = "other_comfy_running"
    MULTIPLE_MATCHING = "multiple_matching"
    PYTHON_VALIDATION_FAILED = "python_validation_failed"
    WAITING_FOR_SHUTDOWN = "waiting_for_shutdown"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ComfyPreflightSnapshot:
    """Describe whether onboarding may safely proceed past process preflight."""

    processes: tuple[LocalComfyProcess, ...]

    @property
    def can_continue(self) -> bool:
        """Return whether no local Comfy process is currently active."""

        return not self.processes

    @property
    def can_close(self) -> bool:
        """Return whether every blocker has a verified process identity."""

        return bool(self.processes)


@dataclass(frozen=True, slots=True)
class AttachedPythonRecoverySnapshot:
    """Describe one responsive attached-Python recovery observation."""

    state: AttachedPythonRecoveryState
    binding: ComfyPythonBinding | None
    processes: tuple[LocalComfyProcess, ...]
    detail: ApplicationText

    @property
    def can_continue(self) -> bool:
        """Return whether Python is verified and every Comfy process is stopped."""

        return self.state is AttachedPythonRecoveryState.READY

    @property
    def can_close(self) -> bool:
        """Return whether an explicit shutdown can target verified processes."""

        return bool(self.processes)


class ComfyEnvironmentService:
    """Own onboarding decisions derived from process and Python infrastructure."""

    def __init__(
        self,
        *,
        process_gateway: LocalComfyProcessGateway,
        python_gateway: AttachedPythonGateway,
    ) -> None:
        """Store the process and Python gateways used by onboarding."""

        self._process_gateway = process_gateway
        self._python_gateway = python_gateway

    def inspect_preflight(self) -> ComfyPreflightSnapshot:
        """Return the current global local-Comfy preflight state."""

        return ComfyPreflightSnapshot(self._process_gateway.scan())

    def discover_attached_python(
        self,
        workspace: Path,
    ) -> ComfyPythonDiscoveryResult:
        """Run silent conventional Python discovery for one selected workspace."""

        return self._python_gateway.discover(workspace)

    def inspect_attached_recovery(
        self,
        *,
        workspace: Path,
        binding: ComfyPythonBinding | None,
    ) -> AttachedPythonRecoverySnapshot:
        """Observe a guided launch and capture its exact verified Python binding."""

        processes = self._process_gateway.scan()
        matching = tuple(
            item for item in processes if _same_path(item.workspace, workspace)
        )
        if binding is not None:
            if processes:
                return AttachedPythonRecoverySnapshot(
                    state=AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN,
                    binding=binding,
                    processes=processes,
                    detail=app_text(
                        "The Python environment is verified. Close ComfyUI to continue."
                    ),
                )
            return AttachedPythonRecoverySnapshot(
                state=AttachedPythonRecoveryState.READY,
                binding=binding,
                processes=(),
                detail=app_text(
                    "ComfyUI is closed and its Python environment is ready."
                ),
            )
        if not processes:
            return AttachedPythonRecoverySnapshot(
                state=AttachedPythonRecoveryState.WAITING_FOR_LAUNCH,
                binding=None,
                processes=(),
                detail=app_text(
                    "Open this ComfyUI installation yourself using your usual shortcut, "
                    "script, or launcher. Substitute will detect it automatically."
                ),
            )
        if not matching:
            return AttachedPythonRecoverySnapshot(
                state=AttachedPythonRecoveryState.OTHER_COMFY_RUNNING,
                binding=None,
                processes=processes,
                detail=app_text(
                    "A different ComfyUI installation is running. Start the selected "
                    "ComfyUI folder so Substitute can identify its Python environment."
                ),
            )
        if len(matching) > 1:
            return AttachedPythonRecoverySnapshot(
                state=AttachedPythonRecoveryState.MULTIPLE_MATCHING,
                binding=None,
                processes=processes,
                detail=app_text(
                    "More than one process is running this ComfyUI installation. "
                    "Close the extra instance and leave one running."
                ),
            )
        process = matching[0]
        probe = self._python_gateway.probe(
            workspace,
            process.python_executable,
            source=ComfyPythonSelectionSource.RUNNING_COMFY,
        )
        if probe.binding is None:
            return AttachedPythonRecoverySnapshot(
                state=AttachedPythonRecoveryState.PYTHON_VALIDATION_FAILED,
                binding=None,
                processes=processes,
                detail=probe.failure
                or app_text(
                    "The running ComfyUI Python environment could not be validated."
                ),
            )
        return AttachedPythonRecoverySnapshot(
            state=AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN,
            binding=probe.binding,
            processes=processes,
            detail=app_text(
                "Found the Python environment ComfyUI uses. Close ComfyUI to continue."
            ),
        )

    def validate_browsed_python(
        self,
        *,
        workspace: Path,
        executable: Path,
    ) -> ComfyPythonProbeResult:
        """Validate the user's recovery-only Python executable selection."""

        return self._python_gateway.probe(
            workspace,
            executable,
            source=ComfyPythonSelectionSource.USER_SELECTED,
        )

    def close_processes(
        self,
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Explicitly close the supplied processes after gateway revalidation."""

        return self._process_gateway.terminate(processes)


def _same_path(first: Path, second: Path) -> bool:
    """Return whether two workspace paths identify the same local directory."""

    return os.path.normcase(str(first.resolve())) == os.path.normcase(
        str(second.resolve())
    )


__all__ = [
    "AttachedPythonGateway",
    "AttachedPythonRecoverySnapshot",
    "AttachedPythonRecoveryState",
    "ComfyEnvironmentService",
    "ComfyPreflightSnapshot",
    "LocalComfyProcessGateway",
]
