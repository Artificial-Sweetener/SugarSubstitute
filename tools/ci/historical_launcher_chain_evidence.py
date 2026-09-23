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

"""Require the installed root to acknowledge a candidate's painted app."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.application_readiness import ApplicationReadinessReceipt
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


_ACCEPTANCE = re.compile(
    r"process=(?P<supervisor>\d+) .*?"
    r"application_readiness_supervisor Accepted painted application surface \| "
    r"candidate_pid=(?P<candidate>\d+) \| "
    r"surface_pid=(?P<surface>\d+) \| surface=main_shell \| "
    r"outer_contract=(?P<outer>True|False)"
)


class _LaunchBaseline(Protocol):
    """Expose the log offsets captured immediately before candidate launch."""

    @property
    def progress_baselines(
        self,
    ) -> tuple[tuple[Path, tuple[bool, int]], ...]:
        """Return pre-launch path existence and byte lengths."""


def assert_candidate_root_readiness(
    *,
    install_root: Path,
    candidate_launch: _LaunchBaseline,
    readiness_path: Path,
    token: str,
) -> None:
    """Bind the current painted process to the root's own acknowledgement."""

    try:
        receipt = ApplicationReadinessReceipt.from_json(
            json.loads(readiness_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            "Candidate main-shell receipt is unavailable after launch."
        ) from error
    if receipt.token != token:
        raise InstallerLifecycleError(
            "Candidate main-shell receipt is from another launch."
        )
    assert_root_main_shell_acknowledgement(
        install_root=install_root,
        candidate_launch=candidate_launch,
        surface_pid=receipt.pid,
    )


def assert_root_main_shell_acknowledgement(
    *, install_root: Path, candidate_launch: _LaunchBaseline, surface_pid: int
) -> None:
    """Reject a shell witnessed only by the selected launcher, not its root."""

    log_path = install_root / "launcher" / "logs" / "launcher.log"
    baseline = next(
        (
            signature[1]
            for path, signature in candidate_launch.progress_baselines
            if path.resolve() == log_path.resolve()
        ),
        None,
    )
    if baseline is None:
        raise InstallerLifecycleError("Launcher log baseline is missing.")
    try:
        raw_log = log_path.read_bytes()
    except OSError as error:
        raise InstallerLifecycleError(
            "Launcher readiness log is unreadable."
        ) from error
    if baseline > len(raw_log):
        raise InstallerLifecycleError("Launcher readiness log was truncated.")
    records = [
        match
        for line in raw_log[baseline:].decode("utf-8", errors="replace").splitlines()
        if (match := _ACCEPTANCE.search(line)) is not None
        and int(match.group("surface")) == surface_pid
    ]
    selected_supervisors = {
        int(record.group("supervisor"))
        for record in records
        if record.group("outer") == "True"
    }
    root_accepted = any(
        record.group("outer") == "False"
        and (
            not selected_supervisors
            or int(record.group("candidate")) in selected_supervisors
        )
        for record in records
    )
    if not root_accepted:
        raise InstallerLifecycleError(
            "Installed launcher root did not accept the candidate main shell."
        )


__all__ = [
    "assert_candidate_root_readiness",
    "assert_root_main_shell_acknowledgement",
]
