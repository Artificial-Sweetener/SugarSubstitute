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

"""Tests for startup model metadata progress presentation."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
    ModelMetadataUpdateSignalProtocol,
    StartupModelMetadataRefreshHandleProtocol,
    StartupModelMetadataProgressSink,
    StartupModelMetadataRefreshState,
    start_model_metadata_refresh,
    wire_model_metadata_update_bridge,
)
from substitute.application.model_metadata import (
    ModelMetadataProgressSink,
    ModelMetadataRefreshEvent,
    RefreshCancellationToken,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_MODEL_METADATA_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_model_metadata.py"
)
STARTUP_MODEL_METADATA_BRIDGE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_model_metadata_bridge.py"
)
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_STARTUP_MODEL_METADATA_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_metadata_progress_sink_fans_out_stable_and_transient_lines() -> None:
    """Metadata progress lines should reach splash and shell output history."""

    splash = _Splash()
    stream = _Stream()
    sink = StartupModelMetadataProgressSink(
        splash=cast(Any, splash),
        comfy_output_stream=cast(TerminalOutputStream, stream),
    )

    sink.emit_line("Model metadata: loading.")
    sink.emit_progress("Model metadata: scanning.")

    assert splash.lines == ["Model metadata: loading.", "Model metadata: scanning."]
    assert stream.lines == ["Model metadata: loading.", "Model metadata: scanning."]


def test_startup_metadata_progress_sink_forwards_model_updates() -> None:
    """Model update events should be forwarded when a bridge is available."""

    bridge = _Bridge()
    sink = StartupModelMetadataProgressSink(
        splash=None,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
        update_bridge=bridge,
    )
    event = ModelMetadataRefreshEvent(
        kind="checkpoint",
        value="dream",
        relative_path="dream.safetensors",
        sha256="abc123",
        provider_status="ok",
        thumbnail_updated=True,
    )

    sink.emit_model_updated(event)

    assert bridge.events == [event]


def test_startup_metadata_progress_sink_accepts_missing_bridge() -> None:
    """Model update events should be optional during startup."""

    sink = StartupModelMetadataProgressSink(
        splash=None,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
    )
    event = ModelMetadataRefreshEvent(
        kind="checkpoint",
        value="dream",
        relative_path="dream.safetensors",
        sha256="abc123",
        provider_status="ok",
        thumbnail_updated=False,
    )

    sink.emit_model_updated(event)


def test_start_model_metadata_refresh_creates_and_starts_refresh_handle() -> None:
    """Metadata refresh startup should create one handle through explicit ports."""

    state = StartupModelMetadataRefreshState()
    bridge = _CoalescingBridge()
    handles: list[StartupModelMetadataRefreshHandleProtocol] = []
    factory = _RefreshHandleFactory()

    start_model_metadata_refresh(
        state=state,
        startup_cancelled=False,
        metadata_update_bridge=bridge,
        refreshes=handles,
        service_factory=_service_factory,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
        trace_fields=lambda: {"workflow_id": "wf-a"},
        refresh_handle_factory=factory,
    )

    assert state.started is True
    assert handles == [factory.handle]
    assert factory.handle.started is True
    assert callable(factory.finished_callback)
    factory.finished_callback()
    assert bridge.end_requests == 1


def test_start_model_metadata_refresh_skips_without_bridge_or_after_start() -> None:
    """Metadata refresh startup should be single-flight and bridge-gated."""

    state = StartupModelMetadataRefreshState()
    handles: list[StartupModelMetadataRefreshHandleProtocol] = []
    factory = _RefreshHandleFactory()

    start_model_metadata_refresh(
        state=state,
        startup_cancelled=False,
        metadata_update_bridge=None,
        refreshes=handles,
        service_factory=_service_factory,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
        trace_fields=lambda: {},
        refresh_handle_factory=factory,
    )

    assert state.started is False
    assert handles == []
    state.started = True
    start_model_metadata_refresh(
        state=state,
        startup_cancelled=False,
        metadata_update_bridge=_CoalescingBridge(),
        refreshes=handles,
        service_factory=_service_factory,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
        trace_fields=lambda: {},
        refresh_handle_factory=factory,
    )

    assert handles == []


def test_start_model_metadata_refresh_skips_after_startup_cancel() -> None:
    """Metadata refresh startup should not start after splash cancellation."""

    state = StartupModelMetadataRefreshState()
    handles: list[StartupModelMetadataRefreshHandleProtocol] = []

    start_model_metadata_refresh(
        state=state,
        startup_cancelled=True,
        metadata_update_bridge=_CoalescingBridge(),
        refreshes=handles,
        service_factory=_service_factory,
        comfy_output_stream=cast(TerminalOutputStream, _Stream()),
        trace_fields=lambda: {},
        refresh_handle_factory=_RefreshHandleFactory(),
    )

    assert state.started is False
    assert handles == []


def test_wire_model_metadata_update_bridge_connects_shell_refresh_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata bridge wiring should create, register, and connect the bridge."""

    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_model_metadata.trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    shell_frame = object()
    bridge = _SignalBridge()
    registered: list[object] = []
    main_window = _MainWindow(_MetadataSurfaceRefreshController())

    def bridge_factory(parent: object) -> ModelMetadataUpdateSignalBridgeProtocol:
        """Return the bridge for the expected shell frame."""

        assert parent is shell_frame
        return cast(ModelMetadataUpdateSignalBridgeProtocol, bridge)

    wired = wire_model_metadata_update_bridge(
        startup_cancelled=False,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=registered.append,
        main_window_for_shell=lambda parent: (
            main_window if parent is shell_frame else object()
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert cast(object, wired) is bridge
    assert registered == [bridge]
    signal = cast(_Signal, bridge.model_updated)
    assert signal.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_wire_model_metadata_update_bridge_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not create a metadata bridge."""

    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_model_metadata.trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    calls: list[str] = []

    def bridge_factory(_parent: object) -> ModelMetadataUpdateSignalBridgeProtocol:
        """Record unexpected bridge construction."""

        calls.append("bridge_factory")
        return cast(ModelMetadataUpdateSignalBridgeProtocol, _SignalBridge())

    wired = wire_model_metadata_update_bridge(
        startup_cancelled=True,
        shell_frame=object(),
        bridge_factory=bridge_factory,
        register_bridge=lambda _bridge: calls.append("register"),
        main_window_for_shell=lambda _parent: calls.append("main_window"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert calls == []
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_wire_model_metadata_update_bridge_skips_without_shell_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing shell frames should not create a metadata bridge."""

    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_model_metadata.trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    wired = wire_model_metadata_update_bridge(
        startup_cancelled=False,
        shell_frame=None,
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda _bridge: None,
        main_window_for_shell=lambda _parent: object(),
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "no_shell_frame"}),
    ]


def test_startup_model_metadata_imports_no_forbidden_boundaries() -> None:
    """Startup metadata presentation should avoid Qt and concrete shell widgets."""

    imported_modules = _imported_module_names(STARTUP_MODEL_METADATA_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_MODEL_METADATA_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_model_metadata_bridge_adapter_owns_concrete_presentation_import() -> (
    None
):
    """The Qt bridge factory should isolate the concrete shell bridge dependency."""

    imported_modules = _imported_module_names(STARTUP_MODEL_METADATA_BRIDGE_SOURCE)

    assert (
        "substitute.presentation.shell.model_metadata_update_bridge" in imported_modules
    )
    assert "subprocess" not in imported_modules
    assert "substitute.infrastructure" not in imported_modules


def test_startup_facade_no_longer_owns_model_metadata_progress_sink() -> None:
    """Startup should delegate model metadata progress and refresh startup."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    ready_shell_controller_source = READY_SHELL_CONTROLLER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "class _StartupModelMetadataProgressSink" not in source
    assert "def start_model_metadata_refresh" not in source
    assert "StartupModelMetadataRefreshHandle(" not in source
    assert "StartupModelMetadataProgressSink(" not in source
    assert "ModelMetadataUpdateBridge(" not in source
    assert "substitute.presentation.shell.model_metadata_update_bridge" not in source
    assert "managed_ready_runtime.create_model_metadata_update_bridge" not in source
    assert "managed_ready_launch.create_metadata_bridge_task" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task" not in source
    assert "managed_ready_ports.create_model_metadata_update_bridge" not in source
    assert "create_ready_shell_metadata_bridge_task(" not in source
    assert "ReadyShellMetadataBridgeTask(" not in source
    assert "def wire_metadata_bridge_task" not in source
    assert "wire_ready_shell_metadata_bridge_task(" not in source
    assert "wire_ready_shell_metadata_bridge(" not in source
    assert "wire_model_metadata_update_bridge(" not in source
    assert "wire_model_metadata_update_bridge(" in ready_shell_controller_source
    assert "wire_metadata_bridge_task.start" not in source
    assert "metadata_update_bridge.model_updated.connect" not in source


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Splash:
    """Collect splash log lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self.lines.append(line)


class _Stream:
    """Collect terminal output lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one shell output line."""

        self.lines.append(line)


class _Bridge:
    """Collect forwarded model metadata update events."""

    def __init__(self) -> None:
        self.events: list[ModelMetadataRefreshEvent] = []

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Record one model metadata event."""

        self.events.append(event)


class _CoalescingBridge(_Bridge):
    """Collect model events and expose startup coalescing shutdown."""

    def __init__(self) -> None:
        """Create empty event and coalescing records."""

        super().__init__()
        self.end_requests = 0

    def request_end_startup_coalescing(self) -> None:
        """Record one coalescing shutdown request."""

        self.end_requests += 1


class _Signal:
    """Collect connected metadata update callbacks."""

    def __init__(self) -> None:
        """Create empty callback records."""

        self.callbacks: list[object] = []

    def connect(
        self, callback: Callable[[ModelMetadataRefreshEvent], object]
    ) -> object:
        """Record one connected callback."""

        self.callbacks.append(callback)
        return None


class _SignalBridge(_CoalescingBridge):
    """Expose a connectable metadata update signal."""

    def __init__(self) -> None:
        """Create bridge event and signal records."""

        super().__init__()
        self.model_updated: ModelMetadataUpdateSignalProtocol = _Signal()


class _MetadataSurfaceRefreshController:
    """Expose the shell metadata refresh handler."""

    def __init__(self) -> None:
        """Create empty update records."""

        self.events: list[ModelMetadataRefreshEvent] = []

    def handle_model_metadata_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Record one model metadata update event."""

        self.events.append(event)


class _MainWindow:
    """Expose metadata surface refresh collaborators."""

    def __init__(self, controller: _MetadataSurfaceRefreshController) -> None:
        """Store the controller double."""

        self.model_metadata_surface_refresh_controller = controller


class _RefreshHandle:
    """Record refresh handle lifecycle calls."""

    def __init__(self) -> None:
        """Create empty lifecycle records."""

        self.started = False
        self.cancelled = False
        self.shutdown_requested = False

    def start(self) -> None:
        """Record refresh start."""

        self.started = True

    def cancel(self) -> None:
        """Record refresh cancellation."""

        self.cancelled = True

    def shutdown(self) -> None:
        """Record refresh shutdown."""

        self.shutdown_requested = True


class _RefreshHandleFactory:
    """Create one recording refresh handle."""

    def __init__(self) -> None:
        """Create factory records."""

        self.handle = _RefreshHandle()
        self.finished_callback: object | None = None

    def __call__(
        self,
        *,
        service_factory: object,
        progress_sink: StartupModelMetadataProgressSink,
        finished_callback: object | None,
    ) -> StartupModelMetadataRefreshHandleProtocol:
        """Record construction collaborators and return the test handle."""

        _ = service_factory, progress_sink
        self.finished_callback = finished_callback
        return self.handle


class _Service:
    """Accept metadata refresh calls from the startup handle contract."""

    def refresh(
        self,
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken | None = None,
    ) -> None:
        """Accept one refresh request without side effects."""

        _ = progress, cancellation_token


def _service_factory() -> _Service:
    """Return a placeholder metadata refresh service."""

    return _Service()
