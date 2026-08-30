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

"""Test managed-ready prompt, local-editor, prelude, and canvas warmup contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_managed_ready_launch import (
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellLocalEditorWarmupAdapter,
    ReadyShellManagedStartupPrelude,
    ReadyShellPromptEditorWarmupTask,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer


from .launch_support import (
    _Clock,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_creates_prompt_editor_warmup_task(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create prompt editor warmup tasks."""

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
    main_window = object()

    task = launch_runtime.create_prompt_editor_warmup_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda _shell_frame: main_window,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellPromptEditorWarmupTask)
    assert getattr(task, "_shell_frame")() is shell_frame
    assert getattr(task, "_main_window_for_shell")(shell_frame) is main_window


def test_managed_ready_launch_runtime_binds_local_editor_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind warmup state into local editor."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    registry = StartupResourceRegistry()

    adapter = launch_runtime.create_local_editor_warmup_adapter(
        startup_cancelled=lambda: False,
        main_window_for_shell=lambda _shell_frame: object(),
        registry=registry,
        trace_fields=lambda: {},
    )

    assert isinstance(adapter, ReadyShellLocalEditorWarmupAdapter)
    assert getattr(adapter, "_state") is launch_runtime.state.startup_warmup_state
    assert getattr(adapter, "_registry") is registry


def test_managed_ready_launch_runtime_creates_managed_startup_prelude(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create the startup prelude."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    prelude = launch_runtime.create_managed_startup_prelude(
        connect_cancel_request=lambda _callback: object(),
        request_startup_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        emit_splash_cancel=lambda: None,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        startup_timer=StartupTimer(clock=_Clock()),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )

    assert isinstance(prelude, ReadyShellManagedStartupPrelude)


def test_managed_ready_launch_runtime_binds_cutecanvas_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind CuteCanvas warmup state separately."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    registry = StartupResourceRegistry()

    callback = launch_runtime.create_cutecanvas_sam_warmup_callback(
        startup_cancelled=lambda: False,
        registry=registry,
        trace_fields=lambda: {},
    )

    assert callable(callback)
