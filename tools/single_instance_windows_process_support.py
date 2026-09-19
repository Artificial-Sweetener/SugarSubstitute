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

"""Own process observation, cleanup, and evidence for Windows instance qualification."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import TypeVar

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_cold_start_evidence import (
    qualification_app_pids,
    splash_host_pids,
)
from tools.single_instance_qualification_app import (
    invocation_evidence_path,
    restart_evidence_path,
)


_TIMEOUT_SECONDS = 30.0
_T = TypeVar("_T")


def _wait_for_invocation_count(layout: InstallLayout, expected_count: int) -> None:
    """Require every acknowledged secondary launch to be handled exactly once."""

    evidence_path = invocation_evidence_path(layout.root)

    def observed_count() -> int | None:
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        count = payload.get("count") if isinstance(payload, dict) else None
        return count if count == expected_count else None

    _wait_for_value(
        observed_count,
        description=f"{expected_count} exactly-once forwarded invocations",
    )


def _wait_for_presented_surface(
    layout: InstallLayout,
    *,
    expected_invocation_count: int = 1,
) -> dict[str, object]:
    """Require the last forwarded request to reveal an accessible normal window."""

    evidence_path = invocation_evidence_path(layout.root)

    def presented_surface() -> dict[str, object] | None:
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("count") != expected_invocation_count
        ):
            return None
        surface = payload.get("surface")
        if not isinstance(surface, dict):
            return None
        if (
            surface.get("visible") is not True
            or surface.get("minimized") is not False
            or surface.get("accessible") is not True
        ):
            return None
        return surface

    return _wait_for_value(
        presented_surface,
        description="visible accessible application surface",
    )


def _wait_for_splash_host_pid(layout: InstallLayout) -> int:
    """Read the painted splash identity and require its process to remain live."""

    def single_host_pid() -> int | None:
        records = tuple(
            (layout.user_dir / "qualification-splash-surfaces").glob("*.json")
        )
        if len(records) != 1:
            return None
        try:
            payload = json.loads(records[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        host_pid = payload.get("host_pid") if isinstance(payload, dict) else None
        if not isinstance(host_pid, int) or not psutil.pid_exists(host_pid):
            return None
        return host_pid

    return _wait_for_value(single_host_pid, description="one live splash host")


def _wait_for_forwarder_acceptance(layout: InstallLayout, requester_pid: int) -> None:
    """Synchronize on the broker retaining one exact secondary request."""

    expected = f"requester_pid={requester_pid}"

    def accepted() -> bool | None:
        try:
            log_text = (layout.logs_dir / "launcher.log").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return None
        return True if expected in log_text else None

    _wait_for_value(
        accepted,
        description=f"broker acceptance for forwarder {requester_pid}",
    )


def _wait_for_replacement_broker_child(
    layout: InstallLayout,
    *,
    owner_pid: int,
    previous_child_pid: int,
) -> int:
    """Require the painted launcher UI to replace a failed app broker child."""

    pattern = re.compile(
        rf"Registered supervised application child \| owner_pid={owner_pid} \| "
        r"child_pid=(\d+)"
    )

    def replacement_pid() -> int | None:
        try:
            log_text = (layout.logs_dir / "launcher.log").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return None
        candidates = tuple(int(value) for value in pattern.findall(log_text))
        for candidate in reversed(candidates):
            if candidate != previous_child_pid and psutil.pid_exists(candidate):
                return candidate
        return None

    return _wait_for_value(
        replacement_pid,
        description="launcher repair UI broker registration",
    )


def _wait_for_forwarder_surface(
    layout: InstallLayout,
    *,
    requester_pid: int,
    expected_surface: str,
) -> str:
    """Require one secondary launcher to receive a painted-surface receipt."""

    expected = f"requester_pid={requester_pid} | owner_pid="
    surface_suffix = f"| surface={expected_surface}"

    def presented_surface() -> str | None:
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
        if any(expected in line and surface_suffix in line for line in lines):
            return expected_surface
        return None

    return _wait_for_value(
        presented_surface,
        description=f"{expected_surface} receipt for forwarder {requester_pid}",
    )


def _wait_for_restart_evidence(
    layout: InstallLayout,
    *,
    expected_pid: int,
    expected_invocation_count: int,
) -> dict[str, object]:
    """Require a real child-to-supervisor restart request at the exact count."""

    evidence_path = restart_evidence_path(layout.root)

    def accepted_evidence() -> dict[str, object] | None:
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if payload != {
            "accepted": True,
            "invocation_count": expected_invocation_count,
            "pid": expected_pid,
        }:
            return None
        return payload

    return _wait_for_value(
        accepted_evidence,
        description="authenticated supervised application restart",
    )


def _assert_single_child(layout: InstallLayout, expected_pid: int) -> None:
    """Prove exactly one registered application child remains live."""

    observed = tuple(sorted(qualification_app_pids(layout)))
    if observed != (expected_pid,):
        raise AssertionError(f"Expected one child {expected_pid}, observed {observed}.")


def _assert_no_live_ownership_files(layout: InstallLayout) -> None:
    """Prove the packaged run created none of the removed ownership artifacts."""

    forbidden = (
        "application-instance.lease",
        "launcher-invocation.lease",
        "application-launch.mutex",
        "application-launch.lock",
        "app-update.lock",
    )
    historical_lock_directory = layout.launcher_dir / "locks"
    created = [
        name for name in forbidden if (historical_lock_directory / name).exists()
    ]
    if created:
        raise AssertionError(f"Removed ownership files were recreated: {created}")


def _wait_for_clean_exits(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Require every forwarded launcher invocation to acknowledge and exit cleanly."""

    for process in processes:
        process.wait(timeout=_TIMEOUT_SECONDS)
        if process.returncode != 0:
            raise AssertionError(
                f"Forwarding launcher {process.pid} exited with {process.returncode}."
            )


def _wait_for_splash_hosts_exit(layout: InstallLayout) -> None:
    """Prove every launcher splash host exits after child adoption."""

    _wait_for_value(
        lambda: True if not splash_host_pids(layout) else None,
        description="launcher splash host exit",
    )


def _wait_for_process_exit(pid: int) -> None:
    """Wait until one supervisor or child process is gone."""

    _wait_for_value(
        lambda: True if not psutil.pid_exists(pid) else None,
        description=f"process {pid} exit",
    )


def _terminate_supervisor_and_child(
    supervisor: subprocess.Popen[bytes],
    child_pid: int,
) -> None:
    """Crash one qualification supervisor and require its child to follow."""

    if supervisor.poll() is None:
        psutil.Process(supervisor.pid).kill()
    _wait_for_process_exit(supervisor.pid)
    _wait_for_process_exit(child_pid)


def _wait_for_value(
    value_factory: Callable[[], _T | None],
    *,
    description: str,
) -> _T:
    """Return the first non-None value produced within the global timeout."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        value = value_factory()
        if value is not None:
            return value
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {description}.")


def _terminate_launchers(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Stop only still-running launchers created by this qualification."""

    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


def _terminate_qualification_apps(layout: InstallLayout) -> None:
    """Stop remaining children belonging to the disposable installation."""

    for pid in qualification_app_pids(layout):
        try:
            process = psutil.Process(pid)
            process.kill()
            process.wait(timeout=5.0)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            continue


def _terminate_installation_processes(layout: InstallLayout) -> None:
    """Stop remaining helpers rooted in the disposable installation."""

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
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(owned, timeout=3.0)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def _capture_failure_diagnostics(
    layout: InstallLayout,
    artifact_dir: Path,
) -> None:
    """Retain bounded launcher and crash evidence before disposal."""

    diagnostics_dir = artifact_dir / "failure-diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    for source in (
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "app-startup.log",
    ):
        if source.is_file():
            shutil.copy2(source, diagnostics_dir / source.name)
    crash_diagnostics = layout.appdata_dir / "diagnostics"
    if crash_diagnostics.is_dir():
        shutil.copytree(
            crash_diagnostics,
            diagnostics_dir / "app-diagnostics",
            dirs_exist_ok=True,
        )


def _capture_success_diagnostics(
    layout: InstallLayout,
    artifact_dir: Path,
) -> None:
    """Preserve the qualified launcher log beside the structured report."""

    source = layout.logs_dir / "launcher.log"
    if source.is_file():
        shutil.copy2(source, artifact_dir / "launcher.log")
