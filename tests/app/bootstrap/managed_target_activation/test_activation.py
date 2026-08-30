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

"""Qualify managed target launch activation ownership."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from sugarsubstitute_shared.localization import app_text

from substitute.app.bootstrap import managed_target_activation
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)

from tests.app.bootstrap.managed_target_activation.support import (
    Diagnostics as _Diagnostics,
    FailingAfterActivationSplash as _FailingAfterActivationSplash,
    Splash as _Splash,
    Stream as _Stream,
    context as _context,
    task_factory as _task_factory,
)


def test_activate_target_starts_launch_owned_managed_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launch-owned targets should start managed Comfy and route startup output."""

    captured: dict[str, object] = {}
    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    def _start_managed(**kwargs: object) -> process_manager.ManagedComfyState:
        captured.update(kwargs)
        cast(Any, kwargs["on_log"])("log line")
        cast(Any, kwargs["on_status"])("status line")
        cast(Any, kwargs["on_progress"])(
            app_text("Waiting for ComfyUI to become ready%1", "...")
        )
        return fake_state

    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        _start_managed,
    )
    splash = _Splash()
    stream = _Stream()
    diagnostics = _Diagnostics()
    context = _context(tmp_path, launch_owned=True)

    state = managed_target_activation.activate_target(
        installation_context=context,
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, diagnostics),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert captured["endpoint"] == context.comfy_target.endpoint
    assert captured["workspace"] == tmp_path / "ComfyUI"
    assert captured["runtime_state_dir"] == context.runtime_state_dir
    assert captured["diagnostics"] is diagnostics
    assert captured["launch_task_factory"] is _task_factory
    assert captured["process_pump_task_factory"] is _task_factory
    assert splash.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "log line",
        "status line",
        "Waiting for ComfyUI to become ready...\r",
    ]
    assert stream.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "log line",
        "status line",
        "Waiting for ComfyUI to become ready...\r",
    ]
    assert diagnostics.lines == ["log line", "status line"]


def test_activate_target_skips_non_launch_owned_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached targets should log activation context without spawning Comfy."""

    starts: list[str] = []
    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        lambda **_kwargs: starts.append("start"),
    )
    splash = _Splash()
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=False),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is None
    assert starts == []
    assert splash.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]
    assert stream.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]


def test_activate_target_routes_activation_line_without_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pre-theme activation should not require a visible splash reference."""

    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        lambda **_kwargs: fake_state,
    )
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=True),
        splash=None,
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert stream.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]


def test_activate_target_detaches_unresponsive_splash_after_first_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed output should stop retrying a splash endpoint that has gone away."""

    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    def _start_managed(**kwargs: object) -> process_manager.ManagedComfyState:
        """Emit two output records through the activation-owned callbacks."""

        cast(Any, kwargs["on_log"])("first output")
        cast(Any, kwargs["on_log"])("second output")
        return fake_state

    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        _start_managed,
    )
    splash = _FailingAfterActivationSplash()
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=True),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert splash.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]
    assert splash.failure_count == 1
    assert stream.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "first output",
        "second output",
    ]
