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

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateBridgeProtocol,
    StartupModelMetadataRefreshHandleProtocol,
    StartupModelMetadataRefreshState,
)
from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupLauncher,
    NonessentialStartupWarmupRuntime,
    NonessentialStartupWarmupScheduler,
    StartupWarmupState,
    create_nonessential_startup_warmup_launcher,
    create_nonessential_startup_warmup_runtime,
)


from .support import (
    _ReadinessState,
    _MetadataRefreshHandleFactory,
    _Registry,
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


def test_nonessential_startup_warmup_launcher_uses_live_startup_ports() -> None:
    """Nonessential warmup launcher should adapt current shell and metadata state."""

    state = StartupWarmupState()
    readiness_state = _ReadinessState()
    model_state = StartupModelMetadataRefreshState()
    shell_state: list[object | None] = [None]
    bridge_state: list[ModelMetadataUpdateBridgeProtocol | None] = [None]
    refreshes: list[StartupModelMetadataRefreshHandleProtocol] = []
    stream = object()
    service = object()
    calls: list[tuple[str, dict[str, object]]] = []

    handle_factory = _MetadataRefreshHandleFactory()

    launcher = NonessentialStartupWarmupLauncher(
        state=state,
        startup_cancelled=lambda: False,
        comfy_http_ready=lambda: True,
        readiness_state=readiness_state,
        metadata_update_bridge=lambda: bridge_state[0],
        shell_frame=lambda: shell_state[0],
        main_window_for_shell=lambda frame: SimpleNamespace(frame=frame),
        registry=_Registry(),
        model_metadata_refresh_state=model_state,
        model_metadata_refreshes=lambda: refreshes,
        model_metadata_service_factory=lambda: service,
        model_metadata_refresh_handle_factory=handle_factory,
        comfy_output_stream=cast(Any, stream),
        scheduler=lambda _delay_ms, _callback: None,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        backend_editor_warmup=lambda **kwargs: calls.append(("backend", kwargs)),
        cube_icon_warmup=lambda **kwargs: calls.append(("cube", kwargs)),
        model_metadata_refresh=lambda **kwargs: calls.append(("metadata", kwargs)),
    )

    shell_state[0] = object()
    bridge_state[0] = _MetadataBridge()
    launcher.start()

    assert [name for name, _kwargs in calls] == ["backend", "cube", "metadata"]
    assert calls[0][1]["state"] is state
    assert calls[0][1]["shell_frame"] is shell_state[0]
    assert calls[1][1]["shell_frame"] is shell_state[0]
    assert calls[2][1]["state"] is model_state
    assert calls[2][1]["metadata_update_bridge"] is bridge_state[0]
    assert calls[2][1]["refreshes"] is refreshes
    service_factory = cast(Callable[[], object], calls[2][1]["service_factory"])
    assert service_factory() is service
    assert calls[2][1]["comfy_output_stream"] is stream
    assert calls[2][1]["refresh_handle_factory"] is handle_factory


def test_create_nonessential_startup_warmup_launcher_returns_launcher() -> None:
    """Nonessential warmup launcher construction should live in its owner."""

    launcher = create_nonessential_startup_warmup_launcher(
        state=StartupWarmupState(),
        startup_cancelled=lambda: False,
        comfy_http_ready=lambda: False,
        readiness_state=_ReadinessState(),
        metadata_update_bridge=lambda: None,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: None,
        registry=_Registry(),
        model_metadata_refresh_state=StartupModelMetadataRefreshState(),
        model_metadata_refreshes=lambda: [],
        model_metadata_service_factory=lambda: object(),
        model_metadata_refresh_handle_factory=_MetadataRefreshHandleFactory(),
        comfy_output_stream=cast(Any, object()),
        scheduler=lambda _delay_ms, _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(launcher, NonessentialStartupWarmupLauncher)


def test_create_nonessential_startup_warmup_runtime_returns_runtime() -> None:
    """Nonessential warmup runtime should own launcher and scheduler pairing."""

    runtime = create_nonessential_startup_warmup_runtime(
        state=StartupWarmupState(),
        startup_cancelled=lambda: False,
        comfy_http_ready=lambda: False,
        readiness_state=_ReadinessState(),
        metadata_update_bridge=lambda: None,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: None,
        registry=_Registry(),
        model_metadata_refresh_state=StartupModelMetadataRefreshState(),
        model_metadata_refreshes=lambda: [],
        model_metadata_service_factory=lambda: object(),
        model_metadata_refresh_handle_factory=_MetadataRefreshHandleFactory(),
        comfy_output_stream=cast(Any, object()),
        scheduler=lambda _delay_ms, _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(runtime, NonessentialStartupWarmupRuntime)
    assert isinstance(runtime.launcher, NonessentialStartupWarmupLauncher)
    assert isinstance(runtime.scheduler, NonessentialStartupWarmupScheduler)
