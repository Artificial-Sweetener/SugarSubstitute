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

"""Qualify first-run and repair surfaces under real packaged supervision."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import TypeVar

import psutil

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_log_evidence import audit_launcher_log
from tools.single_instance_qualification_installation import (
    prepare_launcher_surface_qualification_installation,
)


_TIMEOUT_SECONDS = 30.0
_SETUP_BURST_SIZE = 8
_T = TypeVar("_T")


def qualify_launcher_surfaces(
    *,
    launcher_bundle: Path,
    temporary_root: Path,
    artifact_dir: Path,
) -> dict[str, object]:
    """Prove first-run and repair launches retain one painted surface owner."""

    layout = prepare_launcher_surface_qualification_installation(
        launcher_bundle=launcher_bundle,
        install_root=temporary_root / "LauncherSurface",
    )
    processes: list[subprocess.Popen[bytes]] = []
    try:
        setup_launches = [
            _launch_launcher(layout, repair=False)
            for _index in range(_SETUP_BURST_SIZE)
        ]
        processes.extend(setup_launches)
        setup_owner = _wait_for_single_owner(setup_launches)
        setup_child_pid = _wait_for_registered_child(
            layout,
            owner_pid=setup_owner.pid,
        )
        _require_successful_forwarders(setup_launches, owner=setup_owner)
        setup_forwarder = _launch_launcher(layout, repair=False)
        processes.append(setup_forwarder)
        _wait_for_successful_exit(setup_forwarder)
        setup_surface = _wait_for_forwarder_surface(
            layout,
            requester_pid=setup_forwarder.pid,
        )
        setup_evidence = {
            "burst_size": len(setup_launches),
            "child_pid": setup_child_pid,
            "forwarder_exit_code": setup_forwarder.returncode,
            "owner_pid": setup_owner.pid,
            "presented_surface": setup_surface,
        }
        _crash_owner_and_require_child_exit(
            owner=setup_owner,
            child_pid=setup_child_pid,
        )

        repair_owner = _launch_launcher(layout, repair=True)
        processes.append(repair_owner)
        repair_child_pid = _wait_for_registered_child(
            layout,
            owner_pid=repair_owner.pid,
        )
        repair_forwarder = _launch_launcher(layout, repair=True)
        processes.append(repair_forwarder)
        _wait_for_successful_exit(repair_forwarder)
        repair_surface = _wait_for_forwarder_surface(
            layout,
            requester_pid=repair_forwarder.pid,
        )
        repair_evidence = {
            "child_pid": repair_child_pid,
            "forwarder_exit_code": repair_forwarder.returncode,
            "owner_pid": repair_owner.pid,
            "presented_surface": repair_surface,
        }
        _crash_owner_and_require_child_exit(
            owner=repair_owner,
            child_pid=repair_child_pid,
        )

        replacement_owner = _launch_launcher(layout, repair=True)
        processes.append(replacement_owner)
        replacement_child_pid = _wait_for_registered_child(
            layout,
            owner_pid=replacement_owner.pid,
        )
        replacement_forwarder = _launch_launcher(layout, repair=True)
        processes.append(replacement_forwarder)
        _wait_for_successful_exit(replacement_forwarder)
        replacement_surface = _wait_for_forwarder_surface(
            layout,
            requester_pid=replacement_forwarder.pid,
        )
        replacement_evidence = {
            "child_pid": replacement_child_pid,
            "forwarder_exit_code": replacement_forwarder.returncode,
            "owner_pid": replacement_owner.pid,
            "presented_surface": replacement_surface,
        }
        _crash_owner_and_require_child_exit(
            owner=replacement_owner,
            child_pid=replacement_child_pid,
        )
        launcher_log = layout.logs_dir / "launcher.log"
        if launcher_log.is_file():
            shutil.copy2(launcher_log, artifact_dir / "launcher-surfaces.log")
        return {
            "first_run_setup": setup_evidence,
            "repair": repair_evidence,
            "repair_after_owner_crash": replacement_evidence,
            "launcher_log": audit_launcher_log(
                layout,
                required_events=(
                    "Elected application supervisor through native IPC",
                    "Forwarding secondary invocation",
                    "Registered supervised application child",
                    "Secondary invocation produced a visible surface",
                    "Application lost its authoritative supervisor",
                ),
            ),
        }
    finally:
        _terminate_processes(processes)
        _terminate_installation_processes(layout)


def _launch_launcher(
    layout: InstallLayout,
    *,
    repair: bool,
) -> subprocess.Popen[bytes]:
    """Start one real packaged setup or repair parent."""

    command = [
        str(layout.executable_path),
        f"--install-root={layout.root}",
        "--no-update-check",
        "--locale=en",
    ]
    if repair:
        command.append("--repair")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.Popen(  # noqa: S603
        command,
        cwd=layout.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        shell=False,
    )


def _wait_for_single_owner(
    processes: list[subprocess.Popen[bytes]],
) -> subprocess.Popen[bytes]:
    """Return the sole live supervisor after every secondary has forwarded."""

    def sole_owner() -> subprocess.Popen[bytes] | None:
        failures = [
            process.returncode
            for process in processes
            if process.poll() not in {None, 0}
        ]
        if failures:
            raise AssertionError(f"Setup forwarders failed: {failures}")
        live = [process for process in processes if process.poll() is None]
        return live[0] if len(live) == 1 else None

    return _wait_for_value(sole_owner, description="one first-run setup owner")


def _wait_for_registered_child(layout: InstallLayout, *, owner_pid: int) -> int:
    """Require one live Qt child registered with the exact supervisor."""

    pattern = re.compile(
        rf"Registered supervised application child \| owner_pid={owner_pid} \| "
        r"child_pid=(\d+)"
    )

    def child_pid() -> int | None:
        try:
            text = (layout.logs_dir / "launcher.log").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return None
        for value in reversed(pattern.findall(text)):
            candidate = int(value)
            if psutil.pid_exists(candidate):
                return candidate
        return None

    return _wait_for_value(
        child_pid,
        description=f"registered launcher UI child for owner {owner_pid}",
    )


def _wait_for_forwarder_surface(
    layout: InstallLayout,
    *,
    requester_pid: int,
) -> str:
    """Require a secondary receipt from the painted launcher window."""

    requester = f"requester_pid={requester_pid} | owner_pid="
    expected_surface = "LauncherMainWindow"
    suffix = f"| surface={expected_surface}"

    def surface() -> str | None:
        try:
            lines = (
                (layout.logs_dir / "launcher.log")
                .read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                .splitlines()
            )
        except OSError:
            return None
        if any(requester in line and suffix in line for line in lines):
            return expected_surface
        return None

    return _wait_for_value(
        surface,
        description=f"painted launcher receipt for forwarder {requester_pid}",
    )


def _require_successful_forwarders(
    processes: list[subprocess.Popen[bytes]],
    *,
    owner: subprocess.Popen[bytes],
) -> None:
    """Require every losing setup launch to finish successfully."""

    for process in processes:
        if process is not owner:
            _wait_for_successful_exit(process)


def _wait_for_successful_exit(process: subprocess.Popen[bytes]) -> None:
    """Require one forwarded launcher to terminate successfully within a bound."""

    try:
        return_code = process.wait(timeout=_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise AssertionError(f"Forwarder {process.pid} did not exit.") from error
    if return_code != 0:
        raise AssertionError(
            f"Forwarder {process.pid} exited with status {return_code}."
        )


def _crash_owner_and_require_child_exit(
    *,
    owner: subprocess.Popen[bytes],
    child_pid: int,
) -> None:
    """Prove losing the supervisor cannot leave its Qt surface orphaned."""

    psutil.Process(owner.pid).kill()
    owner.wait(timeout=5.0)
    try:
        psutil.Process(child_pid).wait(timeout=10.0)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired as error:
        raise AssertionError(
            f"Launcher child {child_pid} survived owner {owner.pid}."
        ) from error


def _wait_for_value(
    operation: Callable[[], _T | None],
    *,
    description: str,
) -> _T:
    """Poll an observable process state until its fixed qualification bound."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        value = operation()
        if value is not None:
            return value
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {description}.")


def _terminate_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    """Stop only parent processes created by this qualification."""

    for process in processes:
        if process.poll() is None:
            process.kill()
    for process in processes:
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            continue


def _terminate_installation_processes(layout: InstallLayout) -> None:
    """Stop remaining helpers whose executable is inside the disposable root."""

    root_key = os.path.normcase(str(layout.root))
    owned: list[psutil.Process] = []
    for process in psutil.process_iter(["exe", "cmdline"]):
        try:
            executable = os.path.normcase(str(process.info.get("exe") or ""))
            command = process.info.get("cmdline") or []
            invoked = os.path.normcase(str(command[0])) if command else ""
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if executable.startswith(root_key) or invoked.startswith(root_key):
            owned.append(process)
    for process in owned:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


__all__ = ["qualify_launcher_surfaces"]
