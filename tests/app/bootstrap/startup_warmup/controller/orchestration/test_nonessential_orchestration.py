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

"""Test startup-warmup behavior owners."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_warmup_controller import (
    StartupWarmupState,
    start_nonessential_startup_warmups,
)


from .support import (
    _ReadinessState,
    _MetadataBridge,
)

PROJECT_ROOT = Path(__file__).resolve().parents[6]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_WARMUP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_warmup_controller.py"
)
FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_start_nonessential_startup_warmups_waits_for_backend() -> None:
    """Nonessential warmups should mark backend-pending before Comfy is ready."""

    state = StartupWarmupState()
    readiness_state = _ReadinessState()
    calls: list[str] = []

    start_nonessential_startup_warmups(
        state=state,
        comfy_http_ready=False,
        readiness_state=readiness_state,
        metadata_update_bridge=None,
        coalescing_timeout_delay_ms=30000,
        scheduler=lambda _delay_ms, _callback: calls.append("schedule"),
        start_backend_editor_warmup=lambda: calls.append("backend"),
        start_cube_icon_warmup=lambda: calls.append("cube"),
        start_model_metadata_refresh=lambda: calls.append("metadata"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert state.nonessential_started is False
    assert readiness_state.nonessential_startup_warmups_pending_backend is True
    assert calls == []


def test_start_nonessential_startup_warmups_runs_once_and_coalesces() -> None:
    """Nonessential warmups should start dependencies and metadata coalescing once."""

    state = StartupWarmupState()
    readiness_state = _ReadinessState()
    bridge = _MetadataBridge()
    scheduled: list[tuple[int, object]] = []
    calls: list[str] = []

    start_nonessential_startup_warmups(
        state=state,
        comfy_http_ready=True,
        readiness_state=readiness_state,
        metadata_update_bridge=bridge,
        coalescing_timeout_delay_ms=30000,
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_backend_editor_warmup=lambda: calls.append("backend"),
        start_cube_icon_warmup=lambda: calls.append("cube"),
        start_model_metadata_refresh=lambda: calls.append("metadata"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )
    start_nonessential_startup_warmups(
        state=state,
        comfy_http_ready=True,
        readiness_state=readiness_state,
        metadata_update_bridge=bridge,
        coalescing_timeout_delay_ms=30000,
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_backend_editor_warmup=lambda: calls.append("backend"),
        start_cube_icon_warmup=lambda: calls.append("cube"),
        start_model_metadata_refresh=lambda: calls.append("metadata"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert state.nonessential_started is True
    assert readiness_state.nonessential_startup_warmups_pending_backend is False
    assert calls == ["backend", "cube", "metadata"]
    assert bridge.begin_calls == 1
    assert scheduled == [(30000, bridge.timeout_startup_coalescing)]
