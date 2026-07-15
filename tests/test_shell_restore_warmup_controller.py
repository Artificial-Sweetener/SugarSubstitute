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

"""Tests for shell restored workspace warmup coordination."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.workspace_state import (
    RestoredCubeDefinitionWarmupResult,
    WorkspaceSnapshot,
)
from substitute.presentation.shell.shell_restore_warmup_controller import (
    ShellRestoreWarmupController,
)
import substitute.presentation.shell.shell_restore_warmup_controller as controller_module


class _WarmupService:
    """Capture restored cube-definition warmup inputs."""

    instances: list["_WarmupService"] = []

    def __init__(self) -> None:
        """Create one fake warmup service."""

        self.calls: list[tuple[WorkspaceSnapshot | None, object]] = []
        self.instances.append(self)

    def warm(
        self,
        snapshot: WorkspaceSnapshot | None,
        cube_load_service: object,
    ) -> RestoredCubeDefinitionWarmupResult:
        """Record warmup inputs and return a deterministic summary."""

        self.calls.append((snapshot, cube_load_service))
        return RestoredCubeDefinitionWarmupResult(
            requested_count=3,
            warmed_count=2,
            skipped_count=1,
            failed_count=0,
            failures=(),
        )


def test_warm_restored_workspace_cube_definitions_uses_shell_loader_and_traces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore warmup should run through the shell cube loader with trace context."""

    trace_calls: list[tuple[str, dict[str, object]]] = []
    _WarmupService.instances = []
    monkeypatch.setattr(
        controller_module,
        "RestoredCubeDefinitionWarmupService",
        _WarmupService,
    )
    monkeypatch.setattr(
        controller_module,
        "snapshot_trace_fields",
        lambda snapshot: {"workspace_present": snapshot is not None},
    )
    monkeypatch.setattr(
        controller_module,
        "trace_mark",
        lambda event, **context: trace_calls.append((event, context)),
    )
    snapshot = cast(WorkspaceSnapshot, object())
    cube_load_service = object()
    shell = SimpleNamespace(cube_load_service=cube_load_service)
    controller = ShellRestoreWarmupController(shell)

    result = controller.warm_restored_workspace_cube_definitions(snapshot)

    assert _WarmupService.instances[0].calls == [(snapshot, cube_load_service)]
    assert result.requested_count == 3
    assert trace_calls == [
        (
            "main_window.warm_restored_workspace_cube_definitions.start",
            {"workspace_present": True},
        ),
        (
            "main_window.warm_restored_workspace_cube_definitions.end",
            {
                "requested_count": 3,
                "warmed_count": 2,
                "skipped_count": 1,
                "failed_count": 0,
            },
        ),
    ]
