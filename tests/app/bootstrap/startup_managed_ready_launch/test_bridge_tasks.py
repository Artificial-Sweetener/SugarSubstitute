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

"""Test managed-ready metadata and diagnostics bridge-task contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_managed_ready_launch import (
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellMetadataBridgeTask,
    ReadyShellStartupDiagnosticsUpdateAdapter,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer


from .launch_support import (
    _Clock,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_creates_metadata_bridge_task(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create metadata bridge tasks."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    shell_frame = object()
    registered_bridges: list[object] = []
    recorded_metadata_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []

    task = launch_runtime.create_metadata_bridge_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        register_bridge=registered_bridges.append,
        main_window_for_shell=lambda _shell_frame: object(),
        set_metadata_update_bridge=recorded_metadata_bridges.append,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellMetadataBridgeTask)
    assert getattr(task, "_shell_frame")() is shell_frame
    assert getattr(task, "_register_bridge") == registered_bridges.append
    assert (
        getattr(task, "_set_metadata_update_bridge") == recorded_metadata_bridges.append
    )


def test_managed_ready_launch_runtime_creates_startup_diagnostics_update_adapter(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create diagnostics update adapters."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    adapter = launch_runtime.create_startup_diagnostics_update_adapter(
        startup_cancelled=lambda: True,
        shell_frame_available=lambda: False,
        trace_fields=lambda: {},
    )

    assert isinstance(adapter, ReadyShellStartupDiagnosticsUpdateAdapter)
    assert adapter._startup_cancelled() is True
    assert adapter._shell_frame_available() is False
