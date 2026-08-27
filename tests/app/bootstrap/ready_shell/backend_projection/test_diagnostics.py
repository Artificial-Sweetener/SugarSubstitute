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

"""Tests for ready-shell startup task orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
)

from ..support.backend_state import _BackendStateMainWindow
from ..support.trace import _patch_trace

PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_project_ready_shell_backend_state_delegates_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell backend-state helper should delegate projection policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _BackendStateMainWindow()
    shell_frame = object()

    updated = ready_shell_controller.project_ready_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is True
    assert main_window.generation_action_controller.states == ["ready"]
    assert events == [
        ("shell_backend_state.update", {"state": "ready", "route": "ready"}),
    ]


def test_project_ready_shell_backend_state_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect backend-state collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    updated = ready_shell_controller.project_ready_shell_backend_state(
        state="ready",
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert calls == []
    assert events == []


def test_request_ready_shell_startup_diagnostics_update_delegates_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell diagnostics helper should delegate and trace the request."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    requested: list[dict[str, object]] = []
    main_window = object()
    incident = object()
    ignore_repository = object()
    installation_context = object()
    startup_resources = object()
    execution_runtime = object()

    def execution_dispatcher_factory() -> object:
        """Return a diagnostics dispatcher test double."""

        return object()

    def startup_cancelled() -> bool:
        """Report startup cancellation state."""

        return False

    def shell_frame_available() -> bool:
        """Report shell frame availability state."""

        return True

    def request_update(**kwargs: object) -> bool:
        """Record the delegated diagnostics request."""

        requested.append(kwargs)
        return True

    started = ready_shell_controller.request_ready_shell_startup_diagnostics_update(
        main_window=main_window,
        incidents=(incident,),
        transcript=("line",),
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
        request_update=request_update,
        trace_fields=lambda: {"route": "ready"},
    )

    assert started is True
    assert requested == [
        {
            "main_window": main_window,
            "incidents": (incident,),
            "transcript": ("line",),
            "ignore_repository": ignore_repository,
            "installation_context": installation_context,
            "startup_resources": startup_resources,
            "execution_runtime": execution_runtime,
            "execution_dispatcher_factory": execution_dispatcher_factory,
            "startup_cancelled": startup_cancelled,
            "shell_frame_available": shell_frame_available,
        }
    ]
    assert events == [("post_show.diagnostics.async_requested", {"route": "ready"})]


def test_ready_shell_startup_diagnostics_update_adapter_uses_live_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostics update adapter should own reveal request port assembly."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    requested: list[dict[str, object]] = []
    main_window = object()
    incident = object()
    ignore_repository = object()
    installation_context = object()
    startup_resources = object()
    execution_runtime = object()

    def execution_dispatcher_factory() -> object:
        """Return a diagnostics dispatcher test double."""

        return object()

    def request_update(**kwargs: object) -> bool:
        """Record the delegated diagnostics request."""

        requested.append(kwargs)
        return True

    def startup_cancelled() -> bool:
        """Report startup cancellation state."""

        return False

    def shell_frame_available() -> bool:
        """Report shell frame availability state."""

        return True

    adapter = ready_shell_controller.ReadyShellStartupDiagnosticsUpdateAdapter(
        incidents=lambda: (incident,),
        transcript=lambda: ("line",),
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
        request_update=request_update,
        trace_fields=lambda: {"route": "ready"},
    )

    started = adapter.request(main_window)

    assert started is True
    assert requested == [
        {
            "main_window": main_window,
            "incidents": (incident,),
            "transcript": ("line",),
            "ignore_repository": ignore_repository,
            "installation_context": installation_context,
            "startup_resources": startup_resources,
            "execution_runtime": execution_runtime,
            "execution_dispatcher_factory": execution_dispatcher_factory,
            "startup_cancelled": startup_cancelled,
            "shell_frame_available": shell_frame_available,
        }
    ]
    assert events == [("post_show.diagnostics.async_requested", {"route": "ready"})]


def test_create_ready_shell_startup_diagnostics_update_adapter_returns_adapter() -> (
    None
):
    """Ready-shell diagnostics adapter construction should live in its owner."""

    adapter = (
        ready_shell_controller.create_ready_shell_startup_diagnostics_update_adapter(
            incidents=lambda: (),
            transcript=lambda: (),
            ignore_repository=object(),
            installation_context=object(),
            startup_resources=object(),
            execution_runtime=object(),
            execution_dispatcher_factory=lambda: object(),
            startup_cancelled=lambda: False,
            shell_frame_available=lambda: True,
            request_update=lambda **_kwargs: True,
            trace_fields=lambda: {},
        )
    )

    assert isinstance(
        adapter,
        ready_shell_controller.ReadyShellStartupDiagnosticsUpdateAdapter,
    )
