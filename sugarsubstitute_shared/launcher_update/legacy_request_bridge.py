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

"""Upgrade PID-only launcher handoffs before any installation mutation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_expected_process_identity,
)


LegacyIdentityResolver = Callable[[int, Path], ProcessIdentity | None]


def renew_legacy_launcher_handoff(
    request_path: Path,
    *,
    identity_resolver: LegacyIdentityResolver | None = None,
) -> LauncherUpdateRequest:
    """Persist an exact identity for a live, validated legacy launcher.

    Schema-one producers could persist only a PID. The updater observes the
    process once, proves that it is the installation's launcher executable, and
    records its kernel creation time. If that process has already exited, no
    wait is required. No unrelated PID is ever accepted.
    """

    request = LauncherUpdateRequest.load(request_path)
    if request.schema_version != 1 or request.wait_pid is None:
        return request
    target = launcher_bundle_target_for_key(request.target_key)
    expected_executable = (
        request.install_root.resolve() / target.executable_relative_path
    )
    resolver = identity_resolver or _resolve_expected_identity
    identity = resolver(request.wait_pid, expected_executable)
    renewed = request.with_process_behavior(
        relaunch=request.relaunch,
        wait_identity=identity,
    )
    renewed.save(request_path)
    return renewed


def _resolve_expected_identity(pid: int, executable: Path) -> ProcessIdentity | None:
    """Adapt the keyword-only process identity boundary for injection in tests."""

    return capture_expected_process_identity(pid, expected_executable=executable)


__all__ = ["LegacyIdentityResolver", "renew_legacy_launcher_handoff"]
