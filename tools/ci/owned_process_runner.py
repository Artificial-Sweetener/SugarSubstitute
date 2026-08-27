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

"""Run bounded CI subprocess trees and verify their complete cleanup."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess

import psutil  # type: ignore[import-untyped]

_PROCESS_TERMINATION_TIMEOUT_SECONDS = 10.0


def run_owned_process(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded process and remove its entire descendant tree on timeout."""

    if timeout_seconds <= 0:
        raise ValueError("Owned process timeout must be positive.")
    normalized_command = [str(argument) for argument in command]
    process = subprocess.Popen(  # noqa: S603
        normalized_command,
        cwd=cwd,
        env=(dict(environment) if environment is not None else None),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        close_fds=True,
        start_new_session=os.name != "nt",
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        terminate_owned_process_tree(process.pid)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            normalized_command,
            timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from error
    return subprocess.CompletedProcess(
        normalized_command,
        process.returncode,
        stdout,
        stderr,
    )


def terminate_owned_process_tree(pid: int) -> None:
    """Terminate one explicitly owned process tree and verify no member remains."""

    if os.name == "nt":
        _terminate_windows_process_tree(pid)
        return
    _terminate_posix_process_tree(pid)


def _terminate_windows_process_tree(pid: int) -> None:
    """Use the native Windows tree owner and verify the root is gone."""

    result = subprocess.run(  # noqa: S603
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_PROCESS_TERMINATION_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode not in {0, 128} and psutil.pid_exists(pid):
        raise RuntimeError(
            f"Could not terminate owned Windows process tree {pid}: {result.stderr}"
        )


def _terminate_posix_process_tree(pid: int) -> None:
    """Terminate descendants before their root and reap forced survivors."""

    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    try:
        processes = tuple(root.children(recursive=True)) + (root,)
    except psutil.NoSuchProcess:
        return
    inaccessible: list[int] = []
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(process.pid)
    _, alive = psutil.wait_procs(
        processes,
        timeout=_PROCESS_TERMINATION_TIMEOUT_SECONDS / 2,
    )
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(process.pid)
    _, remaining = psutil.wait_procs(
        alive,
        timeout=_PROCESS_TERMINATION_TIMEOUT_SECONDS / 2,
    )
    if inaccessible or remaining:
        unresolved = sorted(
            set(inaccessible).union(process.pid for process in remaining)
        )
        raise RuntimeError(
            "Could not terminate owned process tree: "
            + ", ".join(str(process_id) for process_id in unresolved)
            + "."
        )


__all__ = ["run_owned_process", "terminate_owned_process_tree"]
