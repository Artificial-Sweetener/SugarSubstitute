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

"""Inspect and conservatively terminate user-launched local ComfyUI processes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import psutil  # type: ignore[import-untyped]  # psutil does not publish type metadata.

from substitute.domain.onboarding import (
    LocalComfyProcess,
    LocalComfyTerminationResult,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("infrastructure.comfy.local_process_gateway")
_PROCESS_EXIT_TIMEOUT_SECONDS = 5.0


class PsutilLocalComfyProcessGateway:
    """Discover exact Comfy Python processes through cross-platform process facts."""

    def scan(self) -> tuple[LocalComfyProcess, ...]:
        """Return confidently identified local ComfyUI Python processes."""

        discovered: dict[tuple[int, float], LocalComfyProcess] = {}
        parent_pids: dict[int, int] = {}
        for process in psutil.process_iter():
            identity = _identify_comfy_process(process)
            if identity is not None:
                discovered[(identity.pid, identity.create_time)] = identity
                try:
                    parent_pids[identity.pid] = process.ppid()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    parent_pids[identity.pid] = 0
        roots = _collapse_nested_launchers(tuple(discovered.values()), parent_pids)
        return tuple(sorted(roots, key=lambda item: (item.pid, item.create_time)))

    def terminate(
        self,
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Terminate only processes whose current identity still matches the scan."""

        requested = tuple(item.pid for item in processes)
        rejected: list[int] = []
        verified_roots: list[psutil.Process] = []
        for identity in processes:
            current = _reopen_matching_process(identity)
            if current is None:
                rejected.append(identity.pid)
                continue
            verified_roots.append(current)

        termination_targets = _termination_targets(verified_roots)
        for process in reversed(termination_targets):
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                continue
            except (psutil.AccessDenied, OSError) as error:
                log_exception(
                    _LOGGER,
                    "Could not terminate identified ComfyUI process",
                    error=error,
                    pid=process.pid,
                )

        gone, alive = psutil.wait_procs(
            termination_targets,
            timeout=_PROCESS_EXIT_TIMEOUT_SECONDS,
        )
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                continue
            except (psutil.AccessDenied, OSError) as error:
                log_exception(
                    _LOGGER,
                    "Could not force-stop identified ComfyUI process",
                    error=error,
                    pid=process.pid,
                )
        killed, remaining = psutil.wait_procs(
            alive,
            timeout=_PROCESS_EXIT_TIMEOUT_SECONDS,
        )
        terminated = tuple(sorted({item.pid for item in (*gone, *killed)}))
        remaining_pids = tuple(sorted(item.pid for item in remaining))
        log_info(
            _LOGGER,
            "Explicit local ComfyUI shutdown finished",
            requested_pids=requested,
            terminated_pids=terminated,
            rejected_pids=tuple(rejected),
            remaining_pids=remaining_pids,
        )
        return LocalComfyTerminationResult(
            requested_pids=requested,
            terminated_pids=terminated,
            rejected_pids=tuple(sorted(rejected)),
            remaining_pids=remaining_pids,
        )


def _identify_comfy_process(process: psutil.Process) -> LocalComfyProcess | None:
    """Return a Comfy identity only when executable, command, and workspace agree."""

    try:
        command = tuple(process.cmdline())
        working_directory_text = process.cwd()
        executable_text = process.exe()
        create_time = process.create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
        return None
    if not command or not executable_text:
        return None
    working_directory = (
        Path(working_directory_text).resolve() if working_directory_text else None
    )
    workspace = _workspace_from_command(command, working_directory)
    if workspace is None:
        return None
    executable = Path(executable_text).resolve()
    if not executable.is_file():
        return None
    return LocalComfyProcess(
        pid=process.pid,
        create_time=create_time,
        python_executable=executable,
        workspace=workspace,
    )


def _workspace_from_command(
    command: tuple[str, ...],
    working_directory: Path | None,
) -> Path | None:
    """Resolve the Comfy workspace named by a process command line."""

    for raw_argument in command[1:]:
        argument = raw_argument.strip().strip('"')
        if not argument or Path(argument).name.casefold() != "main.py":
            continue
        main_path = Path(argument)
        if not main_path.is_absolute():
            if working_directory is None:
                continue
            main_path = working_directory / main_path
        resolved_main = main_path.resolve()
        workspace = resolved_main.parent
        if _is_comfy_workspace(workspace, resolved_main):
            return workspace
    return None


def _is_comfy_workspace(workspace: Path, main_path: Path) -> bool:
    """Return whether process evidence points to a complete Comfy source root."""

    return (
        main_path.is_file()
        and main_path == (workspace / "main.py").resolve()
        and (workspace / "comfy").is_dir()
    )


def _reopen_matching_process(identity: LocalComfyProcess) -> psutil.Process | None:
    """Reopen a process only when its immutable and derived identity still match."""

    try:
        process = psutil.Process(identity.pid)
        if abs(process.create_time() - identity.create_time) > 0.001:
            return None
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
        return None
    current = _identify_comfy_process(process)
    if current is None:
        return None
    if _path_key(current.workspace) != _path_key(identity.workspace):
        return None
    if _path_key(current.python_executable) != _path_key(identity.python_executable):
        return None
    return process


def _termination_targets(roots: Iterable[psutil.Process]) -> list[psutil.Process]:
    """Return unique descendants followed by their verified Comfy root processes."""

    targets: dict[int, psutil.Process] = {}
    for root in roots:
        try:
            for child in root.children(recursive=True):
                targets[child.pid] = child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        targets[root.pid] = root
    return list(targets.values())


def _collapse_nested_launchers(
    processes: tuple[LocalComfyProcess, ...],
    parent_pids: dict[int, int],
) -> tuple[LocalComfyProcess, ...]:
    """Represent a nested virtual-environment launcher chain as one instance."""

    by_pid = {item.pid: item for item in processes}
    nested_pids: set[int] = set()
    for process in processes:
        parent = by_pid.get(parent_pids.get(process.pid, 0))
        if parent is not None and _path_key(parent.workspace) == _path_key(
            process.workspace
        ):
            nested_pids.add(process.pid)
    return tuple(item for item in processes if item.pid not in nested_pids)


def _path_key(path: Path) -> str:
    """Return a platform-normalized path identity key."""

    return os.path.normcase(str(path.resolve()))


__all__ = ["PsutilLocalComfyProcessGateway"]
