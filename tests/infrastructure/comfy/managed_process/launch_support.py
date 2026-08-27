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

"""Provide shared fixtures and fakes for managed ComfyUI launch tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
import pytest
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy import (
    managed_launcher,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentLaunchRequest,
    ManagedContainmentLaunchResult,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationResult,
    ManagedProcessTerminationStatus,
)


@pytest.fixture(autouse=True)
def _use_integrated_manager_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep lifecycle tests focused on launch behavior after setup validation."""

    def detect(
        workspace: Path,
        *,
        python_executable: Path,
        **_kwargs: object,
    ) -> ComfyManagerRuntime:
        """Return the verified integrated runtime supplied by setup."""

        return ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python_executable,
            version="test",
            supports_pygit2=True,
            uses_pygit2=True,
        )

    monkeypatch.setattr(managed_launcher, "detect_workspace_manager_runtime", detect)


def _record_termination(
    calls: list[int | None],
    pid: int | None,
) -> ManagedProcessTerminationResult:
    """Record one termination request and return a successful result."""

    calls.append(pid)
    return ManagedProcessTerminationResult(
        status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
        pid=pid,
        attempted=True,
        user_safe_detail="Shutdown finished cleanly.",
        diagnostic_detail="terminated",
    )


def _write_launchable_workspace(workspace: Path) -> Path:
    """Create the installed artifacts required by ordinary Comfy launch."""

    python_executable = workspace_python_path(workspace)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    workspace_main_path(workspace).write_text("", encoding="utf-8")
    return workspace


def _record_launch_request(
    observed_request: dict[str, object],
    request: ManagedContainmentLaunchRequest,
    process: object,
) -> ManagedContainmentLaunchResult:
    """Capture one managed launch request and return a fake containment result."""

    observed_request["command"] = request.command
    observed_request["cwd"] = request.cwd
    observed_request["env"] = dict(request.env)
    observed_request["capture_output"] = request.capture_output
    return ManagedContainmentLaunchResult(
        process=cast(Any, process),
        metadata=ManagedProcessMetadata(
            pid=790,
            host="127.0.0.1",
            port=8188,
            workspace_path=request.cwd,
            containment_mode="legacy_uncontained",
        ),
        stdout_stream=None,
        containment_handle=None,
    )
