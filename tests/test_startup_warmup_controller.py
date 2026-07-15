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

"""Tests for startup warmup launch orchestration."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
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
    connect_restore_finalized_warmups,
    create_nonessential_startup_warmup_launcher,
    create_nonessential_startup_warmup_runtime,
    create_nonessential_startup_warmup_scheduler,
    schedule_nonessential_startup_warmups,
    start_backend_editor_startup_warmup,
    start_cube_icon_startup_warmup,
    start_local_editor_startup_warmup,
    start_nonessential_startup_warmups,
    start_qpane_sam_startup_warmup,
)
from substitute.app.bootstrap.startup_resources import ShutdownResource


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def test_start_cube_icon_startup_warmup_registers_and_starts_handle() -> None:
    """Cube icon warmup should use shell dependencies and start once."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    shell_frame = object()
    cube_load_service = object()
    cube_icon_factory = object()
    main_window = SimpleNamespace(
        cube_load_service=cube_load_service,
        cube_icon_factory=cube_icon_factory,
    )

    start_cube_icon_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )

    assert state.cube_icon_started is True
    assert registry.cube_icon_warmups == [factory.handle]
    assert factory.kwargs == {
        "cube_load_service": cube_load_service,
        "cube_icon_factory": cube_icon_factory,
    }
    assert factory.handle.started is True


def test_start_qpane_sam_startup_warmup_registers_and_starts_handle() -> None:
    """QPane SAM warmup should register its handle and start once."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _NoArgWarmupFactory()

    start_qpane_sam_startup_warmup(
        state=state,
        startup_cancelled=False,
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )
    start_qpane_sam_startup_warmup(
        state=state,
        startup_cancelled=False,
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )

    assert state.qpane_sam_started is True
    assert registry.qpane_sam_warmups == [factory.handle]
    assert factory.calls == 1
    assert factory.handle.started is True


def test_start_qpane_sam_startup_warmup_skips_cancelled_startup() -> None:
    """QPane SAM warmup should not start after startup cancellation."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _NoArgWarmupFactory()

    start_qpane_sam_startup_warmup(
        state=state,
        startup_cancelled=True,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.qpane_sam_started is False
    assert registry.qpane_sam_warmups == []
    assert factory.calls == 0


def test_start_cube_icon_startup_warmup_skips_missing_dependencies() -> None:
    """Cube icon warmup should not start without required shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()

    start_cube_icon_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(cube_load_service=None),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )

    assert state.cube_icon_started is False
    assert registry.cube_icon_warmups == []


def test_start_local_editor_startup_warmup_registers_and_starts_handle() -> None:
    """Local editor warmup should pass backend-independent shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    main_window = SimpleNamespace(
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        prompt_lora_catalog_service=object(),
        prompt_spellcheck_service=object(),
    )

    start_local_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.local_editor_started is True
    assert registry.editor_warmups == [factory.handle]
    assert set(factory.kwargs) == {
        "prompt_autocomplete_gateway",
        "prompt_wildcard_catalog_gateway",
        "prompt_lora_catalog_service",
        "prompt_spellcheck_service",
    }
    assert factory.handle.started is True


def test_start_backend_editor_startup_warmup_registers_and_starts_handle() -> None:
    """Backend editor warmup should pass Comfy-dependent shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    main_window = SimpleNamespace(
        node_definition_gateway=object(),
        model_choice_resolver=object(),
    )

    start_backend_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.backend_editor_started is True
    assert registry.editor_warmups == [factory.handle]
    assert set(factory.kwargs) == {
        "node_definition_gateway",
        "model_choice_resolver",
    }
    assert factory.handle.started is True


def test_startup_warmups_skip_cancelled_or_repeated_requests() -> None:
    """Warmups should stay single-flight and honor startup cancellation."""

    state = StartupWarmupState(local_editor_started=True)
    registry = _Registry()

    start_local_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )
    start_backend_editor_startup_warmup(
        state=state,
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )

    assert registry.editor_warmups == []


def test_schedule_nonessential_startup_warmups_defers_with_reason() -> None:
    """Nonessential warmup scheduling should delegate to the injected scheduler."""

    scheduled: list[tuple[int, object]] = []
    started: list[str] = []

    schedule_nonessential_startup_warmups(
        reason="restore_finalized",
        delay_ms=2000,
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_warmups=lambda: started.append("start"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert scheduled == [(2000, scheduled[0][1])]
    callback = scheduled[0][1]
    assert callable(callback)
    callback()
    assert started == ["start"]


def test_nonessential_startup_warmup_scheduler_binds_delay_and_ports() -> None:
    """Nonessential warmup scheduler should expose one reusable schedule port."""

    scheduled: list[tuple[int, Callable[[], None]]] = []
    calls: list[dict[str, object]] = []
    started: list[str] = []

    def schedule_warmups(**kwargs: object) -> None:
        """Record scheduling inputs and use the supplied scheduler."""

        calls.append(kwargs)
        scheduler = cast(
            Callable[[int, Callable[[], None]], None],
            kwargs["scheduler"],
        )
        start_warmups = cast(Callable[[], None], kwargs["start_warmups"])
        scheduler(cast(int, kwargs["delay_ms"]), start_warmups)

    scheduler = NonessentialStartupWarmupScheduler(
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_warmups=lambda: started.append("start"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
        delay_ms=2400,
        schedule_warmups=schedule_warmups,
    )

    scheduler.schedule("restore_finalized")

    assert calls[0]["reason"] == "restore_finalized"
    assert calls[0]["delay_ms"] == 2400
    trace_fields = cast(Callable[[], dict[str, object]], calls[0]["trace_fields"])
    assert trace_fields() == {"workflow_id": "wf-a"}
    assert scheduled == [(2400, scheduled[0][1])]
    scheduled[0][1]()
    assert started == ["start"]


def test_create_nonessential_startup_warmup_scheduler_returns_scheduler() -> None:
    """Nonessential warmup scheduler construction should live in its owner."""

    scheduler = create_nonessential_startup_warmup_scheduler(
        scheduler=lambda _delay_ms, _callback: None,
        start_warmups=lambda: None,
        trace_fields=lambda: {},
    )

    assert isinstance(scheduler, NonessentialStartupWarmupScheduler)


def test_connect_restore_finalized_warmups_schedules_after_signal() -> None:
    """Restore-finalized wiring should retain and connect one callback."""

    state = StartupWarmupState()
    signal = _Signal()
    scheduled_reasons: list[str] = []
    main_window = SimpleNamespace(restore_finalized=signal)

    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )
    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert state.restore_finalized_warmups_connected is True
    assert state.restore_finalized_warmups_callback is signal.callback
    assert signal.connect_count == 1
    signal.emit()
    assert scheduled_reasons == ["restore_finalized"]


def test_connect_restore_finalized_warmups_skips_missing_signal() -> None:
    """Restore-finalized wiring should be optional for shell-like test doubles."""

    state = StartupWarmupState()

    connect_restore_finalized_warmups(
        state=state,
        main_window=SimpleNamespace(),
        schedule_warmups=lambda _reason: None,
        trace_fields=lambda: {},
    )

    assert state.restore_finalized_warmups_connected is False
    assert state.restore_finalized_warmups_callback is None


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


def test_startup_warmup_controller_imports_no_forbidden_boundaries() -> None:
    """Warmup controller should not import concrete UI, IO, or subprocess owners."""

    imported_modules = _imported_module_names(STARTUP_WARMUP_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_direct_warmup_starts() -> None:
    """Startup should delegate direct warmup starts to the warmup controller."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    nonessential_warmup_source = launch_source[
        launch_source.index(
            "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        ) : launch_source.index(
            "diagnostics_update_adapter =",
        )
    ]

    assert "def start_cube_icon_startup_warmup" not in source
    assert "def start_local_editor_startup_warmup" not in source
    assert "def start_backend_editor_startup_warmup" not in source
    assert "def schedule_nonessential_startup_warmups" not in source
    assert "def connect_restore_finalized_warmups" not in source
    assert "def start_nonessential_startup_warmups" not in source
    assert "def run_nonessential_startup_warmups" not in source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime("
        not in source
    )
    assert (
        "from substitute.app.bootstrap.startup_warmup_controller import" not in source
    )
    assert "create_nonessential_startup_warmup_launcher(" not in source
    assert "NonessentialStartupWarmupLauncher(" not in source
    assert "create_nonessential_startup_warmup_scheduler(" not in source
    assert "NonessentialStartupWarmupScheduler(" not in source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude(" not in source
    assert "managed_ready_runtime.start_qpane_sam_startup_warmup" not in source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert "managed_ready_runtime.create_local_editor_warmup_adapter(" not in source
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "ReadyShellLocalEditorWarmupAdapter(" not in source
    assert (
        "readiness_state=readiness_controller_state" not in nonessential_warmup_source
    )
    assert "mark_pending_backend=lambda" not in source
    assert "schedule_nonessential_startup_warmups(" not in source
    assert "start_local_editor_startup_warmup(" not in source
    assert "StartupCubeIconWarmupHandle(" not in source
    assert "QPaneSamStartupWarmupHandle(" not in source
    assert "LocalEditorStartupWarmupHandle(" not in source
    assert "BackendEditorStartupWarmupHandle(" not in source


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


@dataclass
class _ReadinessState:
    """Expose nonessential warmup backend-pending state."""

    nonessential_startup_warmups_pending_backend: bool = False


class _WarmupHandle:
    """Record warmup starts."""

    def __init__(self) -> None:
        """Create start records."""

        self.started = False

    def start(self) -> None:
        """Record start."""

        self.started = True

    def shutdown(self) -> None:
        """Accept registry shutdown."""


class _WarmupFactory:
    """Create one recording warmup handle."""

    def __init__(self) -> None:
        """Create factory records."""

        self.handle = _WarmupHandle()
        self.kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> _WarmupHandle:
        """Record construction kwargs and return the handle."""

        self.kwargs = kwargs
        return self.handle


class _NoArgWarmupFactory:
    """Create one no-argument recording warmup handle."""

    def __init__(self) -> None:
        """Create factory records."""

        self.handle = _WarmupHandle()
        self.calls = 0

    def __call__(self) -> _WarmupHandle:
        """Record construction and return the handle."""

        self.calls += 1
        return self.handle


class _MetadataRefreshHandle:
    """Satisfy startup model metadata refresh handle protocol in tests."""

    def start(self) -> None:
        """Accept refresh start."""

    def cancel(self) -> None:
        """Accept refresh cancellation."""

    def shutdown(self) -> None:
        """Accept refresh shutdown."""


class _MetadataRefreshHandleFactory:
    """Create model metadata refresh handles with the production factory shape."""

    def __call__(
        self,
        *,
        service_factory: Any,
        progress_sink: Any,
        finished_callback: Callable[[], None] | None,
    ) -> StartupModelMetadataRefreshHandleProtocol:
        """Return one placeholder refresh handle."""

        _ = service_factory, progress_sink, finished_callback
        return _MetadataRefreshHandle()


class _Registry:
    """Record registered warmup handles."""

    def __init__(self) -> None:
        """Create empty registration records."""

        self.cube_icon_warmups: list[object] = []
        self.qpane_sam_warmups: list[object] = []
        self.editor_warmups: list[object] = []

    def register_cube_icon_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record cube icon warmup registration."""

        self.cube_icon_warmups.append(warmup)
        return warmup

    def register_qpane_sam_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record QPane SAM warmup registration."""

        self.qpane_sam_warmups.append(warmup)
        return warmup

    def register_editor_startup_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record editor warmup registration."""

        self.editor_warmups.append(warmup)
        return warmup


class _Signal:
    """Record signal callback wiring."""

    def __init__(self) -> None:
        """Create empty signal records."""

        self.callback: object | None = None
        self.connect_count = 0

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self.callback = callback
        self.connect_count += 1

    def emit(self) -> None:
        """Invoke the connected callback."""

        assert callable(self.callback)
        self.callback()


class _MetadataBridge:
    """Record metadata coalescing requests."""

    def __init__(self) -> None:
        """Create empty coalescing records."""

        self.begin_calls = 0

    def begin_startup_coalescing(self) -> None:
        """Record coalescing start."""

        self.begin_calls += 1

    def timeout_startup_coalescing(self) -> None:
        """Accept coalescing timeout."""

    def emit_model_updated(self, event: object) -> None:
        """Accept model metadata update events."""

        _ = event
