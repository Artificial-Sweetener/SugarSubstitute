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

"""Prove normal installed-application shutdown without manufacturing a crash."""

from __future__ import annotations

from typing import Protocol
from pathlib import Path
import time

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore
from sugarsubstitute_shared.application_readiness import ApplicationReadinessReceipt
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


class QualificationCandidateProcess(Protocol):
    """Expose child identity and nonblocking reaping for shutdown proof."""

    @property
    def pid(self) -> int:
        """Return the launched candidate process identity."""

    def poll(self) -> int | None:
        """Reap and return process status when the candidate has exited."""


def crash_incident_ids(install_root: Path) -> frozenset[str]:
    """Capture crash incidents that existed before this qualification run."""

    layout = InstallLayout.from_root(install_root)
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    return frozenset(incident.incident_id for incident in store.pending())


def request_clean_qualification_shutdown(plan: InstallerQualificationPlan) -> None:
    """Ask the qualified application to run its normal window-close path."""

    plan.request_main_shell_shutdown()


def wait_for_clean_qualification_shutdown(
    *,
    install_root: Path,
    receipt: ApplicationReadinessReceipt,
    candidate_process: QualificationCandidateProcess | None,
    timeout_seconds: float,
) -> None:
    """Require every packaged process to exit after normal shell closure."""

    if timeout_seconds <= 0:
        raise InstallerLifecycleError(
            "Installer qualification exhausted its timeout before clean shutdown."
        )
    deadline = time.monotonic() + timeout_seconds
    tracked_processes = _tracked_processes(
        install_root=install_root,
        receipt=receipt,
        candidate_process_id=(candidate_process.pid if candidate_process else None),
    )
    while time.monotonic() < deadline:
        if candidate_process is not None:
            candidate_process.poll()
        running = [process.pid for process in tracked_processes if process.is_running()]
        installed = _installed_process_ids(install_root)
        if not running and not installed:
            return
        time.sleep(0.1)
    unresolved = sorted(
        set(process.pid for process in tracked_processes if process.is_running())
        | set(_installed_process_ids(install_root))
    )
    raise InstallerLifecycleError(
        "SugarSubstitute did not complete normal qualified shutdown. "
        f"Remaining process IDs: {unresolved}."
    )


def assert_no_new_crash_incidents(
    *,
    install_root: Path,
    baseline: frozenset[str],
) -> None:
    """Reject a qualification run that generated any crash-report incident."""

    new_incidents = sorted(crash_incident_ids(install_root) - baseline)
    if new_incidents:
        raise InstallerLifecycleError(
            "Clean installer qualification generated crash incidents: "
            + ", ".join(new_incidents)
            + "."
        )


def _tracked_processes(
    *,
    install_root: Path,
    receipt: ApplicationReadinessReceipt,
    candidate_process_id: int | None,
) -> tuple[psutil.Process, ...]:
    """Capture stable identities for processes owned by the installed launch."""

    directly_owned_process_ids = {receipt.pid}
    if candidate_process_id is not None:
        directly_owned_process_ids.add(candidate_process_id)
    chain_process_ids: set[int] = set(receipt.attester_pids)
    if receipt.parent_pid is not None:
        chain_process_ids.add(receipt.parent_pid)

    resolved_root = install_root.resolve()
    tracked: list[psutil.Process] = []
    for process_id in directly_owned_process_ids | chain_process_ids:
        try:
            process = psutil.Process(process_id)
        except psutil.NoSuchProcess:
            continue
        if process_id in directly_owned_process_ids or _process_is_within_install(
            process,
            resolved_root,
        ):
            tracked.append(process)
    return tuple(tracked)


def _process_is_within_install(process: psutil.Process, install_root: Path) -> bool:
    """Return whether a receipt-chain process belongs to the installed tree."""

    try:
        paths = (process.exe(), process.cwd())
    except (OSError, psutil.AccessDenied, psutil.NoSuchProcess):
        return False
    return any(
        isinstance(path, str) and _path_is_within(Path(path), install_root)
        for path in paths
    )


def _installed_process_ids(install_root: Path) -> tuple[int, ...]:
    """Return live processes whose executable or working directory is installed."""

    resolved_root = install_root.resolve()
    matches: list[int] = []
    for process in psutil.process_iter(("pid", "exe", "cwd")):
        try:
            paths = (process.info.get("exe"), process.info.get("cwd"))
            if any(
                isinstance(path, str) and _path_is_within(Path(path), resolved_root)
                for path in paths
            ):
                matches.append(process.pid)
        except (OSError, psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return tuple(sorted(matches))


def _path_is_within(path: Path, root: Path) -> bool:
    """Return whether one process-owned path belongs to the install root."""

    try:
        path.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


__all__ = [
    "QualificationCandidateProcess",
    "assert_no_new_crash_incidents",
    "crash_incident_ids",
    "request_clean_qualification_shutdown",
    "wait_for_clean_qualification_shutdown",
]
