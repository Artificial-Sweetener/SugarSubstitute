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

"""Tests for onboarding Comfy process and Python recovery decisions."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoveryState,
    ComfyEnvironmentService,
)
from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonSelectionSource,
    LocalComfyProcess,
    LocalComfyTerminationResult,
)


class _ProcessGateway:
    """Return mutable deterministic process snapshots for service tests."""

    def __init__(self) -> None:
        """Start with no running Comfy processes."""

        self.processes: tuple[LocalComfyProcess, ...] = ()
        self.terminated: tuple[LocalComfyProcess, ...] = ()

    def scan(self) -> tuple[LocalComfyProcess, ...]:
        """Return the configured process snapshot."""

        return self.processes

    def terminate(
        self,
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Record and report a successful deterministic shutdown."""

        self.terminated = processes
        pids = tuple(item.pid for item in processes)
        return LocalComfyTerminationResult(pids, pids, (), ())


class _PythonGateway:
    """Return deterministic Python discovery and probe evidence."""

    def __init__(self, binding: ComfyPythonBinding | None = None) -> None:
        """Store the binding returned by discovery and probes."""

        self.binding = binding
        self.probe_source: ComfyPythonSelectionSource | None = None

    def discover(self, _workspace: Path) -> ComfyPythonDiscoveryResult:
        """Return the configured automatic binding."""

        return ComfyPythonDiscoveryResult(binding=self.binding, probes=())

    def probe(
        self,
        _workspace: Path,
        executable: Path,
        *,
        source: ComfyPythonSelectionSource,
    ) -> ComfyPythonProbeResult:
        """Return a binding for the supplied executable."""

        self.probe_source = source
        candidate = ComfyPythonCandidate(executable, "test", 0)
        binding = _binding(executable, source) if self.binding is not None else None
        return ComfyPythonProbeResult(
            candidate,
            binding,
            None if binding is not None else "probe failed",
        )


def test_preflight_blocks_until_all_comfy_processes_stop(tmp_path: Path) -> None:
    """Global preflight should derive button state directly from live processes."""

    processes = _ProcessGateway()
    service = ComfyEnvironmentService(
        process_gateway=processes,
        python_gateway=_PythonGateway(),
    )
    processes.processes = (_process(tmp_path, pid=101),)

    blocked = service.inspect_preflight()
    processes.processes = ()
    ready = service.inspect_preflight()

    assert blocked.can_continue is False
    assert blocked.can_close is True
    assert ready.can_continue is True
    assert ready.can_close is False


def test_recovery_ignores_running_python_from_another_workspace(
    tmp_path: Path,
) -> None:
    """A different Comfy instance must never supply the selected workspace binding."""

    selected = tmp_path / "selected" / "ComfyUI"
    processes = _ProcessGateway()
    processes.processes = (
        _process(tmp_path, pid=102, workspace=tmp_path / "other" / "ComfyUI"),
    )
    service = ComfyEnvironmentService(
        process_gateway=processes,
        python_gateway=_PythonGateway(_binding(tmp_path / "python.exe")),
    )

    snapshot = service.inspect_attached_recovery(
        workspace=selected,
        binding=None,
    )

    assert snapshot.state is AttachedPythonRecoveryState.OTHER_COMFY_RUNNING
    assert snapshot.binding is None


def test_recovery_captures_exact_python_from_matching_running_comfy(
    tmp_path: Path,
) -> None:
    """One matching process should produce a verified running-Comfy binding."""

    workspace = tmp_path / "selected" / "ComfyUI"
    process = _process(tmp_path, pid=103, workspace=workspace)
    processes = _ProcessGateway()
    processes.processes = (process,)
    python = _PythonGateway(_binding(process.python_executable))
    service = ComfyEnvironmentService(
        process_gateway=processes,
        python_gateway=python,
    )

    running = service.inspect_attached_recovery(workspace=workspace, binding=None)
    processes.processes = ()
    ready = service.inspect_attached_recovery(
        workspace=workspace,
        binding=running.binding,
    )

    assert running.state is AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN
    assert running.binding is not None
    assert running.binding.executable == process.python_executable
    assert python.probe_source is ComfyPythonSelectionSource.RUNNING_COMFY
    assert ready.state is AttachedPythonRecoveryState.READY
    assert ready.can_continue is True


def test_recovery_refuses_to_choose_between_matching_processes(
    tmp_path: Path,
) -> None:
    """Multiple matching Comfy instances should require the user to leave one."""

    workspace = tmp_path / "selected" / "ComfyUI"
    processes = _ProcessGateway()
    processes.processes = (
        _process(tmp_path, pid=104, workspace=workspace),
        _process(tmp_path, pid=105, workspace=workspace),
    )
    service = ComfyEnvironmentService(
        process_gateway=processes,
        python_gateway=_PythonGateway(_binding(tmp_path / "python.exe")),
    )

    snapshot = service.inspect_attached_recovery(workspace=workspace, binding=None)

    assert snapshot.state is AttachedPythonRecoveryState.MULTIPLE_MATCHING
    assert snapshot.binding is None


def _process(
    root: Path,
    *,
    pid: int,
    workspace: Path | None = None,
) -> LocalComfyProcess:
    """Build one deterministic local Comfy process identity."""

    return LocalComfyProcess(
        pid=pid,
        create_time=float(pid),
        python_executable=root / f"python-{pid}.exe",
        workspace=workspace or root / "ComfyUI",
    )


def _binding(
    executable: Path,
    source: ComfyPythonSelectionSource = ComfyPythonSelectionSource.DISCOVERED,
) -> ComfyPythonBinding:
    """Build one verified Python binding for service tests."""

    return ComfyPythonBinding(
        executable=executable,
        version="3.13",
        architecture="AMD64",
        prefix=executable.parent,
        base_prefix=executable.parent,
        source=source,
    )
