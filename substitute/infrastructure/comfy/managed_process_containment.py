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

"""Select and describe platform-specific managed ComfyUI containment strategies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import IO, Protocol

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_process_metadata import (
    ContainmentMode,
    ManagedProcessMetadata,
)


class ManagedProcessHandle(Protocol):
    """Describe the minimal process surface used by managed lifecycle code."""

    pid: int
    stdout: IO[bytes] | None

    def poll(self) -> int | None:
        """Return the process return code when it has exited."""


@dataclass(frozen=True)
class ManagedContainmentLaunchRequest:
    """Describe one managed ComfyUI launch request before containment selection."""

    command: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    capture_output: bool


@dataclass(frozen=True)
class ManagedContainmentLaunchResult:
    """Describe one contained managed ComfyUI launch result."""

    process: ManagedProcessHandle
    metadata: ManagedProcessMetadata
    stdout_stream: IO[bytes] | None
    containment_handle: object | None


@dataclass(frozen=True)
class ManagedContainmentRuntimeStatus:
    """Describe persisted containment liveness facts for one managed record."""

    managed_process_running: bool
    owner_process_running: bool
    process_group_running: bool


class ManagedContainmentError(RuntimeError):
    """Describe one containment launch or cleanup failure."""


def build_launch_request(
    *,
    command: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    capture_output: bool,
) -> ManagedContainmentLaunchRequest:
    """Normalize one managed launch request for platform containment code."""

    return ManagedContainmentLaunchRequest(
        command=tuple(command),
        cwd=cwd,
        env=dict(env),
        capture_output=capture_output,
    )


def select_containment_mode(*, platform: str | None = None) -> ContainmentMode:
    """Return the authoritative containment mode for the supplied platform."""

    normalized_platform = (platform or sys.platform).lower()
    if normalized_platform.startswith("win"):
        return "windows_job_object"
    if normalized_platform.startswith("linux"):
        return "posix_guardian"
    if normalized_platform == "darwin":
        return "posix_guardian"
    raise ManagedContainmentError(
        "Managed ComfyUI containment is supported on Windows, Linux, and macOS."
    )


def launch_managed_process(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    request: ManagedContainmentLaunchRequest,
) -> ManagedContainmentLaunchResult:
    """Launch one managed ComfyUI process through the selected containment strategy."""

    containment_mode = select_containment_mode()
    if containment_mode == "windows_job_object":
        from substitute.infrastructure.comfy.windows_job_containment import (
            launch_in_job,
        )

        return launch_in_job(endpoint=endpoint, workspace=workspace, request=request)
    from substitute.infrastructure.comfy.posix_guardian_containment import (
        launch_with_guardian,
    )

    return launch_with_guardian(
        endpoint=endpoint,
        workspace=workspace,
        request=request,
        containment_mode=containment_mode,
    )


def describe_persisted_containment(
    metadata: ManagedProcessMetadata,
) -> ManagedContainmentRuntimeStatus:
    """Return containment-aware runtime facts for one persisted metadata record."""

    if metadata.containment_mode == "windows_job_object":
        from substitute.infrastructure.comfy.windows_job_containment import (
            describe_windows_job_runtime,
        )

        return describe_windows_job_runtime(metadata)
    if metadata.containment_mode == "posix_guardian":
        from substitute.infrastructure.comfy.posix_guardian_containment import (
            describe_posix_guardian_runtime,
        )

        return describe_posix_guardian_runtime(metadata)
    from substitute.infrastructure.comfy.managed_process_probe import is_process_running

    return ManagedContainmentRuntimeStatus(
        managed_process_running=is_process_running(metadata.pid),
        owner_process_running=is_process_running(metadata.parent_pid),
        process_group_running=False,
    )


__all__ = [
    "ManagedContainmentError",
    "ManagedContainmentLaunchRequest",
    "ManagedContainmentLaunchResult",
    "ManagedContainmentRuntimeStatus",
    "ManagedProcessHandle",
    "build_launch_request",
    "describe_persisted_containment",
    "launch_managed_process",
    "select_containment_mode",
]
