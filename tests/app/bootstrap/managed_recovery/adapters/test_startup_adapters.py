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

"""Exercise one managed-recovery adapter behavior owner."""

from __future__ import annotations
from pathlib import Path
from typing import Any, cast
import pytest
from sugarsubstitute_shared.launch_splash import SplashSessionMessageError
from sugarsubstitute_shared.localization import render_source_application_text
from substitute.app.bootstrap import managed_recovery_adapters
from substitute.application.backend_compatibility import (
    RuntimeCompatibilityStatus,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)

from .support import (
    _DisposedSplash,
    _OutputStream,
    _Splash,
    _compatibility,
    _context,
    _task_factory,
)


def test_startup_recovery_adapters_use_live_splash_and_output_stream(
    tmp_path: Path,
) -> None:
    """Startup recovery adapters should read the current splash per callback."""

    first_splash = _Splash()
    second_splash = _Splash()
    splash_state: list[_Splash | None] = [first_splash]
    output_stream = _OutputStream()
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: splash_state[0],
        comfy_output_stream=output_stream,
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.append_recovery_message("Updating Substitute BackEnd before opening.")
    splash_state[0] = second_splash
    adapters.emit_recovery_log("setup complete")

    assert first_splash.lines == ["Updating Substitute BackEnd before opening."]
    assert second_splash.lines == ["setup complete"]
    assert output_stream.lines == ["setup complete"]


def test_create_managed_recovery_startup_adapters_returns_adapter(
    tmp_path: Path,
) -> None:
    """Managed recovery startup adapter construction should live in its owner."""

    splash = _Splash()

    adapters = managed_recovery_adapters.create_managed_recovery_startup_adapters(
        installation_context=_context(tmp_path),
        splash=lambda: splash,
        comfy_output_stream=_OutputStream(),
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert isinstance(
        adapters, managed_recovery_adapters.ManagedRecoveryStartupAdapters
    )
    adapters.append_recovery_message("Recovering managed runtime.")
    assert splash.lines == ["Recovering managed runtime."]


def test_startup_recovery_log_survives_disposed_splash(tmp_path: Path) -> None:
    """Disposed splash logging should not block shell output retention."""

    output_stream = _OutputStream()
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: _DisposedSplash(),
        comfy_output_stream=output_stream,
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.emit_recovery_log("late setup line")

    assert output_stream.lines == ["late setup line"]


def test_startup_recovery_log_survives_rejected_splash_message(
    tmp_path: Path,
) -> None:
    """A splash protocol limit should not abort authoritative runtime repair."""

    class _RejectingSplash:
        """Reject one recovery line at the optional splash boundary."""

        def append_log(self, _line: str) -> None:
            """Raise the protocol failure observed during Torch repair."""

            raise SplashSessionMessageError("Splash session message is too large.")

    output_stream = _OutputStream()
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: cast(Any, _RejectingSplash()),
        comfy_output_stream=output_stream,
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.emit_recovery_log("large package-install output")

    assert output_stream.lines == ["large package-install output"]


def test_startup_recovery_failure_builds_runtime_incident(tmp_path: Path) -> None:
    """Recovery failure adapter should build the fatal runtime incident once."""

    diagnostics = ComfyStartupDiagnosticsCollector()
    diagnostics.append_output("captured recovery transcript")
    incidents: list[object] = []
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: None,
        comfy_output_stream=_OutputStream(),
        startup_diagnostics=diagnostics,
        handle_managed_startup_failure=incidents.append,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.handle_recovery_failure(
        _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD),
        RuntimeError("recovery failed"),
    )

    incident = incidents[0]
    assert render_source_application_text(getattr(incident, "message")) == (
        "SugarCubes version is incompatible. Required BackEnd: >=1.6.2,<2.0.0. "
        "Required SugarCubes: 0.11.0. recovery failed"
    )
    assert getattr(incident, "log_excerpt") == ("captured recovery transcript",)
    assert getattr(incident, "values")["recovery_attempted"] is True


def test_startup_recovery_relaunch_delegates_to_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Recovery relaunch adapter should restart through managed target activation."""

    splash = _Splash()
    output_stream = _OutputStream()
    diagnostics = ComfyStartupDiagnosticsCollector()
    context = _context(tmp_path)
    relaunched_state = object()
    calls: list[dict[str, object]] = []

    def fake_activate_target(**kwargs: object) -> object:
        """Record activation arguments."""

        calls.append(kwargs)
        return relaunched_state

    monkeypatch.setattr(
        managed_recovery_adapters,
        "activate_target",
        fake_activate_target,
    )
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=context,
        splash=lambda: splash,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert adapters.relaunch_managed_comfy() is relaunched_state
    assert calls == [
        {
            "installation_context": context,
            "splash": splash,
            "comfy_output_stream": output_stream,
            "startup_diagnostics": diagnostics,
            "launch_task_factory": _task_factory,
            "process_pump_task_factory": _task_factory,
        }
    ]
