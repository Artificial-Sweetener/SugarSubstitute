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

"""Tests for final bootstrap readiness routing behavior."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
import types
from typing import Any, cast
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap import (
    composition,
    managed_target_activation,
    startup,
    startup_environment,
    startup_diagnostics_presenter,
    startup_managed_ready_ports,
    startup_managed_ready_shell_launcher,
    startup_readiness_runtime,
    startup_restore_plan,
    startup_shell_runtime,
    startup_splash_controller,
    startup_shutdown_coordinator,
    startup_warmup_controller,
    startup_probe_tasks,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.application.workspace_state import InitialShellPlacement
from substitute.domain.workspace_snapshot import WindowGeometrySnapshot
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.presentation.shell.window_frame import ShellBackdropMode


class _FakeApp:
    """Minimal QApplication stand-in for startup contract tests."""

    def __init__(self, exit_code: int) -> None:
        self._exit_code = exit_code
        self.quit_calls = 0

    def exec(self) -> int:
        """Return configured event-loop exit code."""

        return self._exit_code

    def quit(self) -> None:
        """Record explicit quit requests."""

        self.quit_calls += 1


def _ensure_runtime_qapplication() -> None:
    """Ensure startup runtime services have a real Qt owner during tests."""

    if QApplication.instance() is None:
        QApplication([])


def _resolved_appearance_stub() -> object:
    """Return one resolved-appearance stub for startup contract tests."""

    return SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_accent_color="#E91E63",
        effective_backdrop_mode=None,
    )


def _build_ready_context(tmp_path: Path) -> InstallationContext:
    """Build a ready installation context for startup routing tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _build_managed_ready_context(tmp_path: Path) -> InstallationContext:
    """Build a ready managed-local installation context for migration tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _patch_startup_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    install_root: Path,
    context: InstallationContext,
    route: BootstrapRoute,
) -> None:
    """Patch startup environment preparation with one deterministic route."""

    readiness_assessment = ReadinessAssessment(route=route, issues=())
    service_bundle = SimpleNamespace(
        readiness_service=SimpleNamespace(assess=lambda: readiness_assessment)
    )

    def prepare_environment(
        **_kwargs: object,
    ) -> startup_environment.StartupEnvironment:
        """Return one deterministic startup environment."""

        return startup_environment.StartupEnvironment(
            install_root=install_root,
            service_bundle=cast(Any, service_bundle),
            readiness_assessment=readiness_assessment,
            installation_context=context,
        )

    monkeypatch.setattr(startup, "prepare_startup_environment", prepare_environment)
    monkeypatch.setattr(
        startup.composition,
        "build_application_localization_runtime",
        lambda _app, _context, _locale: SimpleNamespace(
            manager=SimpleNamespace(
                snapshot=SimpleNamespace(effective_language_identifier="en"),
                languageChanged=SimpleNamespace(connect=lambda _callback: None),
            ),
            initial_snapshot=SimpleNamespace(effective_language_identifier="en"),
        ),
    )


def _patch_startup_restore_plan(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace: object | None = None,
    shell_placement: object | None = None,
    provisional_restore_projection: object | None = None,
) -> None:
    """Patch startup restore-plan preparation with deterministic restore data."""

    restore_plan = SimpleNamespace(
        workspace=workspace,
        shell_placement=shell_placement,
        provisional_restore_projection=provisional_restore_projection,
    )
    preparation = startup_restore_plan.StartupRestorePlanPreparation(
        restore_plan=cast(Any, restore_plan),
        restore_asset_preload=None,
    )
    monkeypatch.setattr(
        startup,
        "prepare_startup_restore_plan",
        lambda **_kwargs: preparation,
    )


def test_run_application_routes_ready_context_to_main_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ready bootstrap state should open the main shell directly."""

    fake_app = _FakeApp(exit_code=11)
    ready_context = _build_ready_context(tmp_path)
    initial_workspace = SimpleNamespace(active_workflow_id="wf-a", workflows=())
    initial_shell_placement = object()
    show_main_calls: list[tuple[InstallationContext, object, object]] = []

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=ready_context,
        route=BootstrapRoute.READY,
    )

    def show_main_window(context: InstallationContext, **kwargs: object) -> object:
        """Record restore-plan arguments passed to shell show."""

        show_main_calls.append(
            (
                context,
                kwargs["initial_workspace"],
                kwargs["initial_shell_placement"],
            )
        )
        return object()

    monkeypatch.setattr(
        startup.composition,
        "show_main_window",
        show_main_window,
    )
    _patch_startup_restore_plan(
        monkeypatch,
        workspace=initial_workspace,
        shell_placement=initial_shell_placement,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _managed_cleanup_result,
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py", "--no-comfy"])

    assert exit_code == 11
    assert show_main_calls == [
        (ready_context, initial_workspace, initial_shell_placement)
    ]


def test_run_application_constructs_shutdown_coordinator_and_passes_request_to_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Startup should construct one coordinator and pass its shutdown request into the shell."""

    fake_app = _FakeApp(exit_code=0)
    ready_context = _build_ready_context(tmp_path)
    created_coordinator: list[tuple[object, object]] = []
    created_coordinator_instances: list[object] = []
    shown_shutdown_requests: list[object] = []

    def cleanup_sentinel() -> ManagedComfyCleanupResult:
        """Provide one callable cleanup sentinel for coordinator wiring tests."""

        return _managed_cleanup_result()

    class _FakeCoordinator:
        def __init__(self, *, app: object, cleanup: object, **_kwargs: object) -> None:
            created_coordinator.append((app, cleanup))
            self.parents: list[object | None] = []
            created_coordinator_instances.append(self)

        def request_shutdown(self, parent_window: object | None = None) -> None:
            """Record one forwarded shutdown parent."""

            self.parents.append(parent_window)

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=ready_context,
        route=BootstrapRoute.READY,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: cleanup_sentinel,
    )
    monkeypatch.setattr(
        startup_shutdown_coordinator,
        "ShutdownCoordinator",
        _FakeCoordinator,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_main_window",
        lambda context, **kwargs: _record_show_main_with_shutdown(
            shown_shutdown_requests,
            context,
            kwargs["shutdown_request"],
        ),
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py", "--no-comfy"])

    assert exit_code == 0
    assert len(created_coordinator) == 1
    assert created_coordinator[0][0] is fake_app
    assert callable(created_coordinator[0][1])
    assert len(shown_shutdown_requests) == 1
    assert callable(shown_shutdown_requests[0])

    parent = object()
    cast(Callable[[object | None], None], shown_shutdown_requests[0])(parent)

    coordinator = cast(Any, created_coordinator_instances[0])
    assert coordinator.parents == [parent]


def test_run_application_prebuilds_shell_and_reveals_after_http_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ready startup should reveal the prebuilt shell only after Comfy is ready."""

    import PySide6.QtCore as qtcore

    ready_context = _build_ready_context(tmp_path)
    calls: list[str] = []
    queued_callbacks: list[Callable[[], None]] = []
    comfy_restart_handlers: list[Callable[[], None]] = []
    initial_workspace = SimpleNamespace(active_workflow_id="wf-a", workflows=())
    initial_shell_placement = object()
    hydrated_workspaces: list[object] = []

    class _QueuedApp(_FakeApp):
        def exec(self) -> int:
            """Start the fake event loop and drain queued single-shot callbacks."""

            calls.append("exec")
            while queued_callbacks:
                queued_callbacks.pop(0)()
            for timer in _FakeTimer.instances:
                if timer.started and timer.timeout.callback is not None:
                    timer.timeout.callback()
            while queued_callbacks:
                queued_callbacks.pop(0)()
            return super().exec()

    fake_app = _QueuedApp(exit_code=0)

    class _FakeSignal:
        def __init__(self) -> None:
            self.callback: Callable[[], None] | None = None

        def connect(self, callback: object) -> None:
            self.callback = cast(Callable[[], None], callback)

        def emit(self) -> None:
            if self.callback is not None:
                self.callback()

    class _FakeTimer:
        instances: list["_FakeTimer"] = []

        def __init__(self, parent: object = None) -> None:
            assert parent is None
            self.timeout = _FakeSignal()
            self.started = False
            self.__class__.instances.append(self)

        def setInterval(self, _interval_ms: int) -> None:
            calls.append("timer_interval")

        def start(self) -> None:
            calls.append("timer_start")
            self.started = True

        def stop(self) -> None:
            calls.append("timer_stop")

        @staticmethod
        def singleShot(_interval_ms: int, callback: object) -> None:
            calls.append("single_shot")
            queued_callbacks.append(cast(Callable[[], None], callback))

    class _FakeSplash:
        def close(self) -> None:
            calls.append("splash_close")

        def append_log(self, _line: str) -> None:
            calls.append("splash_log")

    class _FakeMainWindow:
        def __init__(self) -> None:
            self.backend_states: list[str] = []
            self.execution_runtime: object | None = None
            self.generation_action_controller = SimpleNamespace(
                set_backend_state=self.record_backend_state
            )
            self.cube_load_service = object()
            self.cube_icon_factory = object()
            self.restore_finalized = _FakeSignal()
            self._restore_finalization_pending = False
            self.model_metadata_surface_refresh_controller = SimpleNamespace(
                handle_model_metadata_updated=self.handle_model_metadata_updated
            )
            self.workspace_restore_image_adapter = SimpleNamespace(
                set_restore_asset_preload=lambda preload: setattr(
                    self,
                    "_restore_asset_preload",
                    preload,
                )
            )
            self.restore_projection_controller = SimpleNamespace(
                start_pre_show_restore_projection=(
                    self.start_pre_show_restore_projection
                )
            )
            self.shell_prehydrated_restore_controller = SimpleNamespace(
                prepare_initial_workspace_restore_runtime=(
                    self.prepare_initial_workspace_restore_runtime
                ),
                finish_initial_workspace_restore_layout=(
                    self.finish_initial_workspace_restore_layout
                ),
                finalize_initial_workspace_restore=(
                    self.finalize_initial_workspace_restore
                ),
                restore_layout_finalization_pending=(
                    self.restore_layout_finalization_pending
                ),
            )
            self.shell_restore_warmup_controller = SimpleNamespace(
                warm_restored_workspace_cube_definitions=(
                    self.warm_restored_workspace_cube_definitions
                )
            )
            self.workspace_restore_controller = SimpleNamespace(
                prehydrate_initial_workspace=self.prehydrate_initial_workspace,
                hydrate_initial_workspace=self.hydrate_initial_workspace,
            )

        def record_backend_state(self, state: str) -> None:
            calls.append(f"backend_{state}")
            self.backend_states.append(state)

        def handle_model_metadata_updated(self, _event: object) -> None:
            calls.append("metadata_connected")

        def prehydrate_initial_workspace(self, workspace: object) -> bool:
            calls.append("prehydrate")
            hydrated_workspaces.append(workspace)
            return True

        def warm_restored_workspace_cube_definitions(self, workspace: object) -> None:
            assert workspace is initial_workspace
            calls.append("warm_restore_cubes")

        def prepare_initial_workspace_restore_runtime(self) -> bool:
            calls.append("prepare_restore_runtime")
            return True

        def finish_initial_workspace_restore_layout(self) -> bool:
            calls.append("finish_layout")
            self._restore_finalization_pending = True

            def finalize_restore() -> None:
                calls.append("restore_finalized")
                self._restore_finalization_pending = False
                self.restore_finalized.emit()

            queued_callbacks.append(finalize_restore)
            return True

        def finalize_initial_workspace_restore(self, workspace: object) -> None:
            calls.append("finalize_restore_runtime")
            assert workspace is initial_workspace
            assert self.prepare_initial_workspace_restore_runtime()
            assert self.finish_initial_workspace_restore_layout()

        def restore_layout_finalization_pending(self) -> bool:
            return self._restore_finalization_pending

        def hydrate_initial_workspace(self, workspace: object) -> None:
            calls.append("hydrate")
            hydrated_workspaces.append(workspace)

        def start_pre_show_restore_projection(
            self,
            _artifact: object,
            *,
            fallback_workflow_id: str,
            on_complete: Callable[[], None],
        ) -> bool:
            """Start and complete fake pre-show projection before reveal."""

            calls.append(f"pre_show_start:{fallback_workflow_id}")
            on_complete()
            return True

    class _FakeBridge:
        def __init__(self, _parent: object = None) -> None:
            self.model_updated = _FakeSignal()

    class _FakeRefreshHandle:
        def __init__(self, **_kwargs: object) -> None:
            calls.append("metadata_init")

        def start(self) -> None:
            calls.append("metadata_start")

        def cancel(self) -> None:
            calls.append("metadata_cancel")

        def shutdown(self) -> None:
            calls.append("metadata_shutdown")

    class _FakeIconWarmupHandle:
        def __init__(self, **kwargs: object) -> None:
            calls.append("icon_warmup_init")
            assert kwargs["cube_load_service"] is main_window.cube_load_service
            assert kwargs["cube_icon_factory"] is main_window.cube_icon_factory

        def start(self) -> None:
            calls.append("icon_warmup_start")

        def shutdown(self) -> None:
            calls.append("icon_warmup_shutdown")

    class _FakeQPaneSamWarmupHandle:
        def __init__(self, **_kwargs: object) -> None:
            """Accept warmup dependencies without importing optional packages."""

        def start(self) -> None:
            """Keep routing test focused on startup ordering."""

        def shutdown(self) -> None:
            """Accept shutdown without side effects."""

    class _FakeRuntimeSubmitter(ImmediateTaskSubmitter):
        def close(self) -> None:
            """Accept runtime submitter cleanup."""

    class _FakeExecutionRuntime:
        def submitter(self, *_args: object, **_kwargs: object) -> _FakeRuntimeSubmitter:
            """Return a synchronous startup submitter for warmup construction."""

            return _FakeRuntimeSubmitter()

    shell_frame = SimpleNamespace()
    main_window = _FakeMainWindow()
    main_window.execution_runtime = _FakeExecutionRuntime()

    def activate_target(**_kwargs: object) -> None:
        """Record target activation."""

        calls.append("activate")

    def start_launch_splash(**_kwargs: object) -> _FakeSplash:
        """Record splash creation and return the fake splash."""

        calls.append("splash")
        return _FakeSplash()

    def build_main_window(*_args: object, **_kwargs: object) -> object:
        """Record shell prebuild and return the fake shell frame."""

        calls.append("build")
        return shell_frame

    def is_comfy_http_ready(_host: str, _port: int) -> bool:
        """Record readiness probing and report Comfy as ready."""

        calls.append("http_ready")
        return True

    class _FakeReadinessProbe:
        """Queue readiness probe completion for deterministic startup tests."""

        def __init__(
            self,
            *,
            probe: Callable[[str, int], bool],
            **_kwargs: object,
        ) -> None:
            self._probe = probe
            self._callback: Callable[[object], None] | None = None
            self._next_request_id = 0
            self._in_flight_request_id: int | None = None

        def connect_finished(self, callback: Callable[[object], None]) -> None:
            """Store the startup result callback."""

            self._callback = callback

        def request_probe(self, *, host: str, port: int) -> int | None:
            """Queue one fake asynchronous readiness probe."""

            if self._in_flight_request_id is not None:
                return None
            self._next_request_id += 1
            request_id = self._next_request_id
            self._in_flight_request_id = request_id

            def finish_probe() -> None:
                ready = self._probe(host, port)
                assert self._callback is not None
                self._callback(
                    startup_probe_tasks.ReadinessProbeResult(
                        request_id=request_id,
                        host=host,
                        port=port,
                        ready=ready,
                    )
                )

            queued_callbacks.append(finish_probe)
            return request_id

        def accept_result(self, result: object) -> bool:
            """Accept the currently queued fake result."""

            probe_result = cast(startup_probe_tasks.ReadinessProbeResult, result)
            if self._in_flight_request_id != probe_result.request_id:
                return False
            self._in_flight_request_id = None
            return True

        def cancel_current(self) -> None:
            """Cancel the current fake probe."""

            self._in_flight_request_id = None

        def shutdown(self) -> None:
            """Record fake worker shutdown."""

            calls.append("readiness_shutdown")

    class _FakeRuntimeCompatibilityProbe:
        """Queue compatibility completion for deterministic startup tests."""

        def __init__(
            self,
            *,
            assess: Callable[[], object],
            **_kwargs: object,
        ) -> None:
            self._assess = assess
            self._callback: Callable[[object], None] | None = None
            self._next_request_id = 0
            self._in_flight_request_id: int | None = None

        def connect_finished(self, callback: Callable[[object], None]) -> None:
            """Store the startup compatibility callback."""

            self._callback = callback

        def request_assessment(self) -> int | None:
            """Queue one fake asynchronous compatibility assessment."""

            if self._in_flight_request_id is not None:
                return None
            self._next_request_id += 1
            request_id = self._next_request_id
            self._in_flight_request_id = request_id

            def finish_assessment() -> None:
                compatibility = self._assess()
                assert self._callback is not None
                self._callback(
                    startup_probe_tasks.RuntimeCompatibilityProbeResult(
                        request_id=request_id,
                        compatibility=cast(Any, compatibility),
                        error=None,
                    )
                )

            queued_callbacks.append(finish_assessment)
            return request_id

        def accept_result(self, result: object) -> bool:
            """Accept the currently queued fake compatibility result."""

            probe_result = cast(
                startup_probe_tasks.RuntimeCompatibilityProbeResult,
                result,
            )
            if self._in_flight_request_id != probe_result.request_id:
                return False
            self._in_flight_request_id = None
            return True

        def cancel_current(self) -> None:
            """Cancel the current fake compatibility assessment."""

            self._in_flight_request_id = None

        def shutdown(self) -> None:
            """Record fake compatibility worker shutdown."""

            calls.append("compatibility_shutdown")

    def show_built_main_window(frame: object, **kwargs: object) -> object:
        """Record shell reveal and return the same frame."""

        assert kwargs["initial_shell_placement"] is initial_shell_placement
        calls.append("show")
        return frame

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=ready_context,
        route=BootstrapRoute.READY,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _record_cleanup(calls),
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )
    monkeypatch.setattr(qtcore, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "create_model_metadata_update_bridge",
        lambda parent: _FakeBridge(parent),
    )
    monkeypatch.setattr(
        startup_managed_ready_shell_launcher,
        "StartupModelMetadataRefreshHandle",
        _FakeRefreshHandle,
    )
    monkeypatch.setattr(
        startup_warmup_controller,
        "StartupCubeIconWarmupHandle",
        _FakeIconWarmupHandle,
    )
    monkeypatch.setattr(
        startup_warmup_controller,
        "QPaneSamStartupWarmupHandle",
        _FakeQPaneSamWarmupHandle,
    )
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "activate_target",
        activate_target,
    )
    monkeypatch.setattr(
        startup_splash_controller,
        "start_launch_splash",
        start_launch_splash,
    )
    monkeypatch.setattr(
        startup.composition,
        "build_main_window",
        build_main_window,
    )
    monkeypatch.setattr(
        startup.composition,
        "is_comfy_http_ready",
        is_comfy_http_ready,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_built_main_window",
        show_built_main_window,
    )
    monkeypatch.setattr(
        startup.composition,
        "main_window_widget",
        lambda _frame: main_window,
    )
    monkeypatch.setattr(
        startup_shell_runtime,
        "comfy_runtime_actions_for",
        lambda candidate: (
            SimpleNamespace(
                set_comfy_restart_request_handler=lambda handler: (
                    comfy_restart_handlers.append(handler)
                )
            )
            if candidate is main_window
            else pytest.fail("unexpected Comfy runtime action shell")
        ),
    )
    _patch_startup_restore_plan(
        monkeypatch,
        workspace=initial_workspace,
        shell_placement=initial_shell_placement,
    )
    monkeypatch.setattr(
        startup_readiness_runtime,
        "StartupReadinessProbe",
        _FakeReadinessProbe,
    )
    monkeypatch.setattr(
        startup_readiness_runtime,
        "StartupRuntimeCompatibilityProbe",
        _FakeRuntimeCompatibilityProbe,
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py"])

    assert exit_code == 0
    assert calls[:4] == [
        "splash",
        "single_shot",
        "exec",
        "activate",
    ]
    assert calls.index("exec") < calls.index("activate")
    assert calls.index("timer_start") < calls.index("build")
    assert calls.index("build") < calls.index("http_ready")
    assert calls.index("backend_starting") < calls.index("http_ready")
    assert calls.index("http_ready") < calls.index("backend_ready")
    assert calls.index("backend_ready") < calls.index("warm_restore_cubes")
    assert calls.index("warm_restore_cubes") < calls.index("prepare_restore_runtime")
    assert calls.index("prepare_restore_runtime") < calls.index("pre_show_start:wf-a")
    assert comfy_restart_handlers
    assert all(callable(handler) for handler in comfy_restart_handlers)
    assert calls.index("pre_show_start:wf-a") < calls.index("show")
    assert calls.index("prepare_restore_runtime") < calls.index("show")
    assert calls.index("splash_close") < calls.index("show")
    assert calls.index("show") < calls.index("finish_layout")
    assert "splash_log" not in calls[calls.index("splash_close") + 1 :]
    assert "finalize_restore_runtime" not in calls
    assert calls.index("backend_ready") < calls.index("icon_warmup_start")
    assert calls.index("restore_finalized") < calls.index("icon_warmup_start")
    assert calls.index("http_ready") < calls.index("metadata_start")
    assert calls.index("restore_finalized") < calls.index("metadata_start")
    assert hydrated_workspaces == [initial_workspace]
    assert calls.count("single_shot") >= 5
    assert "icon_warmup_shutdown" in calls
    assert "metadata_cancel" in calls
    assert "metadata_shutdown" in calls


def test_ready_startup_closes_splash_and_reports_fatal_managed_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fatal managed startup results should close splash, report, clean up, and quit."""

    import PySide6.QtCore as qtcore

    ready_context = _build_managed_ready_context(tmp_path)
    calls: list[str] = []
    queued_callbacks: list[Callable[[], None]] = []
    presented_reports: list[Any] = []

    class _QueuedApp(_FakeApp):
        def exec(self) -> int:
            """Drain queued startup callbacks and one readiness timer tick."""

            calls.append("exec")
            while queued_callbacks:
                queued_callbacks.pop(0)()
            for timer in _FakeTimer.instances:
                if timer.started and timer.timeout.callback is not None:
                    timer.timeout.callback()
            return super().exec()

    class _FakeSignal:
        def __init__(self) -> None:
            self.callback: Callable[[], None] | None = None

        def connect(self, callback: object) -> None:
            """Store one connected callback."""

            self.callback = cast(Callable[[], None], callback)

    class _FakeTimer:
        instances: list["_FakeTimer"] = []

        def __init__(self, parent: object = None) -> None:
            assert parent is None
            self.timeout = _FakeSignal()
            self.started = False
            self.__class__.instances.append(self)

        def setInterval(self, _interval_ms: int) -> None:
            """Accept timer interval configuration."""

        def start(self) -> None:
            """Mark the fake timer as active."""

            calls.append("timer_start")
            self.started = True

        def stop(self) -> None:
            """Record timer shutdown."""

            calls.append("timer_stop")

        @staticmethod
        def singleShot(_interval_ms: int, callback: object) -> None:
            """Queue one startup callback."""

            calls.append("single_shot")
            queued_callbacks.append(cast(Callable[[], None], callback))

    class _FakeSplash:
        def close(self) -> None:
            """Record splash closure."""

            calls.append("splash_close")

        def append_log(self, _line: str) -> None:
            """Record splash log forwarding."""

            calls.append("splash_log")

    class _FakeMainWindow:
        cube_load_service = object()
        cube_icon_factory = object()
        model_metadata_surface_refresh_controller = SimpleNamespace(
            handle_model_metadata_updated=lambda _event: None
        )

        def __init__(self) -> None:
            """Expose composed backend-state controller."""

            self.generation_action_controller = SimpleNamespace(
                set_backend_state=lambda state: calls.append(f"backend_{state}")
            )

    class _FakeBridge:
        def __init__(self, _parent: object = None) -> None:
            """Accept a non-Qt fake shell parent."""

            self.model_updated = _FakeSignal()

    fatal_incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message="ComfyUI exited before it became ready.",
        source=str(ready_context.managed_comfy_dir),
        fingerprint="fatal",
        log_excerpt=("Traceback (most recent call last):", "RuntimeError: boom"),
        values={"pid": 123, "exit_code": 1},
    )
    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    fake_state.startup_result = ManagedStartupReadinessResult(
        ready=False,
        fatal_incident=fatal_incident,
    )
    fake_state.request_stop = lambda **_kwargs: calls.append("managed_stop")  # type: ignore[method-assign]
    fake_app = _QueuedApp(exit_code=0)
    shell_frame = SimpleNamespace()
    main_window = _FakeMainWindow()

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=ready_context,
        route=BootstrapRoute.READY,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _record_cleanup(calls),
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )
    monkeypatch.setattr(qtcore, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "create_model_metadata_update_bridge",
        lambda parent: _FakeBridge(parent),
    )
    _patch_startup_restore_plan(monkeypatch)
    monkeypatch.setattr(
        startup_splash_controller,
        "start_launch_splash",
        lambda **_kwargs: _FakeSplash(),
    )
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "activate_target",
        lambda **_kwargs: fake_state,
    )
    monkeypatch.setattr(
        startup.composition,
        "build_main_window",
        lambda *_args, **_kwargs: shell_frame,
    )
    monkeypatch.setattr(
        startup.composition,
        "main_window_widget",
        lambda _frame: main_window,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_built_main_window",
        lambda *_args, **_kwargs: pytest.fail("fatal startup must not show shell"),
    )
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "present_startup_failure_report",
        lambda report: presented_reports.append(report),
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py"])

    assert exit_code == 0
    assert fake_app.quit_calls == 1
    assert "managed_stop" in calls
    assert "cleanup" in calls
    assert "splash_close" in calls
    assert presented_reports
    assert presented_reports[0].message == "ComfyUI exited before it became ready."
    assert "show" not in calls


def test_run_application_routes_missing_setup_to_onboarding_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Onboarding route should show the onboarding surface instead of the shell."""

    fake_app = _FakeApp(exit_code=0)
    default_context = _build_ready_context(tmp_path)
    shown_routes: list[str] = []

    class _Signal:
        def connect(self, _callback: object) -> None:
            """Accept one connected callback."""

    window = type(
        "_Window",
        (),
        {
            "launch_requested": _Signal(),
            "close_requested": _Signal(),
        },
    )()

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=default_context,
        route=BootstrapRoute.ONBOARDING,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_onboarding_window",
        lambda **_kwargs: _record_route(shown_routes, "onboarding", window),
    )
    monkeypatch.setattr(
        startup.composition,
        "show_repair_window",
        lambda **_kwargs: _record_route(shown_routes, "repair", window),
    )
    monkeypatch.setattr(
        startup_splash_controller,
        "start_launch_splash",
        lambda **_kwargs: pytest.fail("onboarding route must not launch splash"),
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _managed_cleanup_result,
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py", "--no-comfy"])

    assert exit_code == 0
    assert shown_routes == ["onboarding"]


def test_fan_out_splash_and_shell_output_routes_one_line_to_both_targets() -> None:
    """Managed startup output should reach both the splash and shell stream sinks."""

    splash_lines: list[str] = []
    stream_lines: list[str] = []
    fake_splash = type(
        "_Splash",
        (),
        {"append_log": lambda self, line: splash_lines.append(line)},
    )()
    fake_stream = type(
        "_Stream",
        (),
        {"append_line": lambda self, line: stream_lines.append(line)},
    )()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=fake_splash,
        comfy_output_stream=fake_stream,
        line="Launching ComfyUI.",
    )

    assert splash_lines == ["Launching ComfyUI."]
    assert stream_lines == ["Launching ComfyUI."]


def test_startup_diagnostics_titlebar_state_is_sent_to_shell() -> None:
    """Recoverable startup diagnostics should be handed to shell chrome."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.STARTUP_WARNING,
        severity=ComfyStartupIncidentSeverity.WARNING,
        title="ComfyUI reported a startup warning",
        message="WARNING: optional package missing",
        fingerprint="warning-a",
    )
    ignored_incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.STARTUP_WARNING,
        severity=ComfyStartupIncidentSeverity.WARNING,
        title="ComfyUI reported a startup warning",
        message="WARNING: already ignored",
        fingerprint="existing",
    )
    states: list[object] = []

    class _Repository:
        def load_ignored_fingerprints(self) -> frozenset[str]:
            """Return one existing ignored startup diagnostic."""

            return frozenset({"existing"})

        def save_ignored_fingerprints(self, fingerprints: frozenset[str]) -> None:
            """Record persisted ignore fingerprints."""

            pytest.fail(
                f"bootstrap should not persist ignores directly: {fingerprints}"
            )

    class _MainWindow:
        shell_frame_integration_controller = SimpleNamespace(
            set_startup_diagnostics_state=states.append
        )

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_MainWindow(),
        incidents=(incident, ignored_incident),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
    )

    assert len(states) == 1
    state = cast(StartupDiagnosticsTitlebarState | None, states[0])
    assert state is not None
    assert state.incidents == (incident,)
    assert state.ignored_count == 1
    assert state.transcript == ("WARNING: optional package missing",)


def test_startup_diagnostics_titlebar_state_skips_ignored_incidents() -> None:
    """Ignored recoverable startup incidents should clear shell diagnostics."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.STARTUP_WARNING,
        severity=ComfyStartupIncidentSeverity.WARNING,
        title="ComfyUI reported a startup warning",
        message="WARNING: optional package missing",
        fingerprint="warning-a",
    )

    class _Repository:
        def load_ignored_fingerprints(self) -> frozenset[str]:
            """Return the incident fingerprint as already ignored."""

            return frozenset({"warning-a"})

        def save_ignored_fingerprints(self, _fingerprints: frozenset[str]) -> None:
            """Fail if ignored incidents are unexpectedly saved again."""

            pytest.fail("ignored incidents should not be saved again")

    states: list[object | None] = []

    class _MainWindow:
        shell_frame_integration_controller = SimpleNamespace(
            set_startup_diagnostics_state=states.append
        )

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_MainWindow(),
        incidents=(incident,),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
    )

    assert states == [None]


def test_startup_diagnostics_titlebar_state_enriches_before_shell_handoff() -> None:
    """Recoverable startup diagnostics should attach extension metadata."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=ComfyStartupIncidentSeverity.ERROR,
        title="Extension failed to load",
        message="SyntaxError: broken",
        source="BrokenExtension",
        fingerprint="broken-extension",
    )
    states: list[object] = []

    class _Repository:
        def load_ignored_fingerprints(self) -> frozenset[str]:
            """Return no ignored startup diagnostics."""

            return frozenset()

        def save_ignored_fingerprints(self, _fingerprints: frozenset[str]) -> None:
            """No selected ignores are expected."""

            pytest.fail("nothing should be saved")

    class _Provider:
        def installed_extensions(self) -> dict[str, ComfyExtensionMetadata]:
            """Return matching extension metadata."""

            return {
                "brokenextension": ComfyExtensionMetadata(
                    key="brokenextension",
                    version="abc123",
                    repository_url="https://github.com/example/BrokenExtension",
                    issues_url="https://github.com/example/BrokenExtension/issues",
                    source="manager_installed_aux_id",
                )
            }

    class _MainWindow:
        shell_frame_integration_controller = SimpleNamespace(
            set_startup_diagnostics_state=states.append
        )

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_MainWindow(),
        incidents=(incident,),
        transcript=("SyntaxError: broken",),
        ignore_repository=_Repository(),
        metadata_providers=(_Provider(),),
    )

    assert states
    state = cast(StartupDiagnosticsTitlebarState | None, states[0])
    assert state is not None
    enriched = state.incidents[0]
    assert enriched.fingerprint == "broken-extension"
    assert enriched.values["extension_version"] == "abc123"
    assert (
        enriched.values["repository_url"]
        == "https://github.com/example/BrokenExtension"
    )
    assert (
        enriched.values["issues_url"]
        == "https://github.com/example/BrokenExtension/issues"
    )


def test_startup_diagnostics_titlebar_state_survives_metadata_provider_failure() -> (
    None
):
    """Metadata failures should not suppress recoverable diagnostics."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.STARTUP_WARNING,
        severity=ComfyStartupIncidentSeverity.WARNING,
        title="ComfyUI reported a startup warning",
        message="WARNING: optional package missing",
        fingerprint="warning-a",
    )
    states: list[object] = []

    class _Repository:
        def load_ignored_fingerprints(self) -> frozenset[str]:
            """Return no ignored startup diagnostics."""

            return frozenset()

        def save_ignored_fingerprints(self, _fingerprints: frozenset[str]) -> None:
            """No selected ignores are expected."""

            pytest.fail("nothing should be saved")

    class _Provider:
        def installed_extensions(self) -> dict[str, ComfyExtensionMetadata]:
            """Raise a metadata lookup error."""

            raise RuntimeError("metadata unavailable")

    class _MainWindow:
        shell_frame_integration_controller = SimpleNamespace(
            set_startup_diagnostics_state=states.append
        )

    startup_diagnostics_presenter.apply_startup_diagnostics_titlebar_state(
        main_window=_MainWindow(),
        incidents=(incident,),
        transcript=("WARNING: optional package missing",),
        ignore_repository=_Repository(),
        metadata_providers=(_Provider(),),
    )

    assert states
    state = cast(StartupDiagnosticsTitlebarState | None, states[0])
    assert state is not None
    assert state.incidents == (incident,)


def test_custom_window_requests_mica_alt_without_frame_body_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The main shell should use Mica Alt without washing the menu row twice."""

    init_calls: list[dict[str, object]] = []

    def fake_frame_init(self: object, **kwargs: object) -> None:
        """Record shell-frame construction options without creating a real window."""

        _ = self
        init_calls.append(kwargs)

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.__init__",
        fake_frame_init,
    )

    window = composition.CustomWindow(
        appearance_runtime=cast(Any, object()),
        shutdown_request=_noop_shutdown_request,
    )

    assert window._shutdown_request is _noop_shutdown_request
    assert window._allow_direct_close is False
    assert init_calls == [
        {
            "create_menu_container": True,
            "create_comfy_output_toggle": True,
            "create_generation_action_cluster": True,
            "create_startup_diagnostics_button": True,
            "create_app_orb_menu": True,
            "backdrop_mode": ShellBackdropMode.MICA_ALT,
            "create_body_material_surface": False,
        }
    ]


def test_attach_main_window_to_shell_syncs_app_orb_after_body_attachment() -> None:
    """Body attachment should raise the frame-owned app orb after MainWindow is added."""

    app = QApplication.instance() or QApplication([])
    events: list[str] = []

    class _FakeFrame(QWidget):
        def __init__(self) -> None:
            """Create a shell-frame double without optional titlebar controls."""

            super().__init__()
            self.menuContainer = None
            self.generationActionCluster = None
            self.comfyOutputToggleButton = None
            self.startupDiagnosticsButton = None

        def add_body_widget(self, _widget: QWidget) -> None:
            """Record body attachment order."""

            events.append("body")

        def sync_app_orb_overlay(self) -> None:
            """Record app-orb overlay sync order."""

            events.append("orb")

    class _FakeMainWindow(QWidget):
        workflow_tabbar = None
        comfy_output_panel_visibility_changed = SimpleNamespace(
            connect=lambda *_args: None
        )

        def __init__(self) -> None:
            """Create the protocol attributes used by shell attachment."""

            super().__init__()
            self.workspace_controller = SimpleNamespace()
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    frame = _FakeFrame()
    main_window = _FakeMainWindow()

    composition._attach_main_window_to_shell(
        cast(composition.CustomWindow, frame),
        main_window,
    )

    assert events == ["body", "orb"]

    frame.close()
    main_window.close()
    app.processEvents()


def test_attach_main_window_to_shell_uses_generation_action_owner() -> None:
    """Titlebar generation controls should call shell-owned generation actions."""

    app = QApplication.instance() or QApplication([])
    events: list[tuple[str, object]] = []
    registries: list[object] = []
    queue_target = object()

    class _Signal:
        """Provide a tiny Qt-like signal for registry callback assertions."""

        def __init__(self) -> None:
            """Create an empty callback list."""

            self._callbacks: list[Callable[..., None]] = []

        def connect(self, callback: Callable[..., None]) -> None:
            """Record one connected callback."""

            self._callbacks.append(callback)

        def disconnect(self, callback: Callable[..., None]) -> None:
            """Remove one connected callback."""

            self._callbacks.remove(callback)

        def emit(self, *args: object) -> None:
            """Invoke every connected callback with emitted arguments."""

            for callback in tuple(self._callbacks):
                callback(*args)

    class _FakeTitlebarControl:
        """Expose the titlebar control protocol consumed by the registry."""

        def __init__(self) -> None:
            """Create fake titlebar signals and batch-count capture."""

            self.playClicked = _Signal()
            self.skipClicked = _Signal()
            self.stopClicked = _Signal()
            self.queueClicked = _Signal()
            self.queueContextMenuRequested = _Signal()
            self.generateModeSelected = _Signal()
            self.batchCountChanged = _Signal()
            self.batch_counts: list[int] = []

        def queue_button_target(self) -> object:
            """Return the queue-menu anchor target."""

            return queue_target

        def set_batch_count(self, value: int) -> None:
            """Record synchronized batch-count values."""

            self.batch_counts.append(value)

        def apply_generation_presentation(self, _presentation: object) -> None:
            """Accept presentation updates from the registry."""

            return None

    class _FakeFrame(QWidget):
        """Provide a shell frame with generation titlebar controls enabled."""

        def __init__(self) -> None:
            """Create a frame double with optional controls used by attachment."""

            super().__init__()
            self.menuContainer = None
            self.generationActionCluster = object()
            self.comfyOutputToggleButton = None
            self.startupDiagnosticsButton = None

        def add_body_widget(self, _widget: QWidget) -> None:
            """Accept body attachment."""

            return None

    class _FakeMainWindow(QWidget):
        """Provide shell collaborators consumed by frame attachment."""

        workflow_tabbar = None
        comfy_output_panel_visibility_changed = SimpleNamespace(
            connect=lambda *_args: None
        )

        def __init__(self) -> None:
            """Create callback collaborators and registry capture."""

            super().__init__()
            self.workspace_generation_actions = SimpleNamespace(
                on_generate_clicked=lambda: events.append(("generate", None)),
                on_skip_generation_clicked=lambda: events.append(("skip", None)),
                on_stop_generation_clicked=lambda: events.append(("stop", None)),
            )
            self.generation_queue_controller = SimpleNamespace(
                show_for=lambda target: events.append(("queue", target)),
                show_context_menu_for=lambda target: events.append(
                    ("queue_context", target)
                ),
            )
            self.generation_action_controller = SimpleNamespace(
                set_generation_selected_mode=lambda mode: events.append(("mode", mode))
            )
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_generation_titlebar_control_registry=registries.append,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    frame = _FakeFrame()
    main_window = _FakeMainWindow()

    composition._attach_main_window_to_shell(
        cast(composition.CustomWindow, frame),
        main_window,
    )
    control = _FakeTitlebarControl()
    cast(Any, registries[0]).register(cast(Any, control))
    control.playClicked.emit()
    control.skipClicked.emit()
    control.stopClicked.emit()
    control.queueClicked.emit()
    control.queueContextMenuRequested.emit()
    control.generateModeSelected.emit("continuous")

    assert events == [
        ("generate", None),
        ("skip", None),
        ("stop", None),
        ("queue", queue_target),
        ("queue_context", queue_target),
        ("mode", "continuous"),
    ]
    assert control.batch_counts == [1]

    frame.close()
    main_window.close()
    app.processEvents()


def test_create_application_sets_shared_app_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QApplication should receive the shared app identity icon at creation."""

    icon = object()
    construction_order: list[str] = []

    class _FakeApplication:
        def __init__(self, argv: list[str]) -> None:
            """Store QApplication construction arguments."""

            construction_order.append("qapplication")
            self.argv = argv
            self.window_icon: object | None = None
            self.quit_on_last_window_closed: bool | None = None

        def setWindowIcon(self, assigned_icon: object) -> None:
            """Record the assigned process window icon."""

            self.window_icon = assigned_icon

        def setQuitOnLastWindowClosed(self, value: bool) -> None:
            """Record the configured Qt quit policy."""

            self.quit_on_last_window_closed = value

    monkeypatch.setattr(composition, "application_icon", lambda: icon)
    monkeypatch.setattr(
        composition,
        "configure_windows_app_user_model_id",
        lambda: construction_order.append("app_user_model_id"),
    )
    monkeypatch.setattr(composition, "QApplication", _FakeApplication)

    app = cast(Any, composition.create_application(("main.py",)))

    assert construction_order == ["app_user_model_id", "qapplication"]
    assert app.argv == ["main.py"]
    assert app.window_icon is icon
    assert app.quit_on_last_window_closed is True


def test_configure_windows_app_user_model_id_calls_windows_shell_api() -> None:
    """Windows startup identity should use the configured AppUserModelID."""

    calls: list[str] = []

    class _FakeShell32:
        def SetCurrentProcessExplicitAppUserModelID(self, app_id: str) -> int:
            """Record the requested AppUserModelID."""

            calls.append(app_id)
            return 0

    composition.configure_windows_app_user_model_id(
        platform="win32",
        shell32=_FakeShell32(),
    )

    assert calls == [composition.WINDOWS_APP_USER_MODEL_ID]


def test_configure_windows_app_user_model_id_noops_off_windows() -> None:
    """Non-Windows platforms should never touch the Windows shell API."""

    calls: list[str] = []

    class _FakeShell32:
        def SetCurrentProcessExplicitAppUserModelID(self, app_id: str) -> int:
            """Record unexpected shell API calls."""

            calls.append(app_id)
            return 0

    composition.configure_windows_app_user_model_id(
        platform="linux",
        shell32=_FakeShell32(),
    )

    assert calls == []


def test_configure_windows_app_user_model_id_can_be_disabled_for_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shell identity call should be suppressible in test worker processes."""

    shell_lookups: list[str] = []
    monkeypatch.setenv(composition.DISABLE_WINDOWS_APP_USER_MODEL_ID_ENV, "1")
    monkeypatch.setattr(
        composition,
        "_windows_shell32",
        lambda: shell_lookups.append("called"),
    )

    composition.configure_windows_app_user_model_id(platform="win32")

    assert shell_lookups == []


def test_create_splash_window_uses_shared_app_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash creation should pass the shared app icon into the splash window."""

    icon = object()

    class _FakeSplashWindow:
        def __init__(self, *, icon: object) -> None:
            """Record the splash icon argument."""

            self.icon = icon
            self.centered = False
            self.shown = False

        def center_on_screen(self) -> None:
            """Record splash centering."""

            self.centered = True

        def show(self) -> None:
            """Record splash reveal."""

            self.shown = True

    fake_module = types.SimpleNamespace(SplashWindow=_FakeSplashWindow)
    monkeypatch.setattr(composition, "application_icon", lambda: icon)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    splash = composition.create_splash_window()

    assert isinstance(splash, _FakeSplashWindow)
    assert splash.icon is icon
    assert splash.centered is True
    assert splash.shown is True


def test_show_main_window_adds_main_window_to_shell_body(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Shell composition should delegate body placement to the frame-owned surface."""

    app = QApplication.instance() or QApplication([])
    context = _build_ready_context(tmp_path)
    added_body_widgets: list[QWidget] = []
    assigned_window_icons: list[object] = []
    attached_app_orbs: list[object] = []

    class _FakeSignal:
        def connect(self, _callback: object) -> None:
            """Accept one connected callback."""

    class _FakeScreen:
        def availableGeometry(self) -> object:
            """Return one large desktop geometry."""

            return types.SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame(QWidget):
        def __init__(
            self,
            *,
            appearance_runtime: object | None = None,
            shutdown_request: object | None = None,
            backdrop_mode: object | None = None,
            create_body_material_surface: bool = False,
        ) -> None:
            super().__init__()
            self.menuContainer = QWidget(self)
            self.comfyOutputToggleButton = None
            self.appOrbMenuButton = object()
            self.titleBar = types.SimpleNamespace(
                height=lambda: 64,
                closeBtn=types.SimpleNamespace(clicked=_FakeSignal()),
            )
            self.appearance_runtime = appearance_runtime
            self.shutdown_request = shutdown_request
            self.backdrop_mode = backdrop_mode
            self.create_body_material_surface = create_body_material_surface

        def setWindowTitle(self, _title: str) -> None:
            """Accept title updates."""

        def setWindowIcon(self, _icon: object) -> None:
            """Accept icon updates."""

            assigned_window_icons.append(_icon)

        def screen(self) -> _FakeScreen:  # type: ignore[override]
            """Return the fake screen geometry."""

            return _FakeScreen()

        def add_body_widget(self, widget: QWidget) -> None:
            """Record shell-body content placement."""

            added_body_widgets.append(widget)

    class _FakeMainWindow(QWidget):
        comfy_output_panel_visibility_changed = _FakeSignal()

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.menu_container = kwargs["menu_container"]
            self.dependencies = kwargs["dependencies"]
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda app_orb_menu: attached_app_orbs.append(
                    app_orb_menu
                ),
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    fake_module = types.ModuleType("substitute.presentation.shell.main_window")
    setattr(fake_module, "MainWindow", _FakeMainWindow)

    monkeypatch.setattr(
        composition, "_configure_control_registry_service", lambda: None
    )
    monkeypatch.setattr(
        composition,
        "_build_main_window_dependencies",
        lambda _runtime_services: SimpleNamespace(
            shell_resource_lifecycle=SimpleNamespace(shutdown=lambda *_args: ())
        ),
    )
    monkeypatch.setattr(composition, "CustomWindow", _FakeFrame)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    frame = composition.show_main_window(
        context,
        comfy_output_stream=cast(Any, object()),
    )

    assert len(added_body_widgets) == 1
    assert isinstance(added_body_widgets[0], _FakeMainWindow)
    assert not hasattr(frame, "mainWindow")
    assert composition.main_window_widget(frame) is added_body_widgets[0]
    assert len(assigned_window_icons) == 1
    assert isinstance(assigned_window_icons[0], QIcon)
    assert not assigned_window_icons[0].isNull()
    assert attached_app_orbs == [frame.appOrbMenuButton]

    frame.close()
    app.processEvents()


def test_main_window_dependencies_include_user_preset_service(tmp_path: Path) -> None:
    """Bootstrap composition should wire presets to the user-owned preset file."""

    context = _build_ready_context(tmp_path)
    application = cast(
        QApplication,
        QApplication.instance() or QApplication([]),
    )
    localization = composition.build_application_localization_runtime(
        application,
        context,
        None,
    )

    runtime_services = composition.build_application_runtime_services(
        context=context,
        comfy_output_stream=cast(Any, object()),
        localization_manager=localization.manager,
        appearance_runtime=composition.build_appearance_runtime(context),
    )
    dependencies = composition._build_main_window_dependencies(
        runtime_services,
    )
    preset = dependencies.user_preset_service.save_dimension_preset(
        width=1536,
        height=1024,
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert preset.payload.short_edge == 1024
    assert (context.user_dir / "presets.json").exists()
    assert dependencies.session_snapshot_repository is (
        runtime_services.session_snapshot_repository
    )
    assert dependencies.session_autosave_service is (
        runtime_services.session_autosave_service
    )
    assert dependencies.generation_result_snapshot_service is not None
    dependencies.shell_resource_lifecycle.shutdown()
    runtime_services.execution_runtime.shutdown()
    localization.manager.close()


def test_custom_window_close_event_delegates_to_shutdown_request() -> None:
    """Shell close should route through the coordinated shutdown callback when configured."""

    requested_shutdowns: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = requested_shutdowns.append
    window._allow_direct_close = False
    event = _FakeCloseEvent()

    composition.CustomWindow.closeEvent(window, event)

    assert event.ignored is True
    assert event.accepted is False
    assert requested_shutdowns == [window]


def test_custom_window_close_event_allows_final_close_after_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shell close should fall back to direct app quit once coordinated shutdown succeeds."""

    fake_app = _FakeApp(exit_code=0)
    base_close_calls: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = None
    window._allow_direct_close = True
    event = _FakeCloseEvent()

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.closeEvent",
        lambda self, close_event: base_close_calls.append((self, close_event)),
    )

    composition.CustomWindow.closeEvent(window, event)

    assert fake_app.quit_calls == 1
    assert event.accepted is True
    assert base_close_calls == [(window, event)]


def test_custom_window_close_event_allows_reload_disposal_without_app_quit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanctioned reload disposal should bypass shutdown and application quit."""

    requested_shutdowns: list[object] = []
    fake_app = _FakeApp(exit_code=0)
    base_close_calls: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = requested_shutdowns.append
    window._allow_direct_close = True
    window._quit_application_on_close = False
    event = _FakeCloseEvent()

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.closeEvent",
        lambda self, close_event: base_close_calls.append((self, close_event)),
    )

    composition.CustomWindow.closeEvent(window, event)

    assert requested_shutdowns == []
    assert fake_app.quit_calls == 0
    assert event.accepted is True
    assert base_close_calls == [(window, event)]


def test_show_main_window_wires_titlebar_close_button_to_window_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Titlebar close should use the same close path as a normal shell close."""

    app = QApplication.instance() or QApplication([])
    context = _build_ready_context(tmp_path)
    connected_callbacks: list[object] = []
    close_calls: list[object] = []

    class _FakeSignal:
        def connect(self, callback: object) -> None:
            connected_callbacks.append(callback)

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame(QWidget):
        def __init__(
            self,
            *,
            appearance_runtime: object | None = None,
            shutdown_request: object | None = None,
            backdrop_mode: object | None = None,
            create_body_material_surface: bool = False,
        ) -> None:
            super().__init__()
            self.menuContainer = QWidget(self)
            self.comfyOutputToggleButton = None
            self.titleBar = SimpleNamespace(
                height=lambda: 64,
                closeBtn=SimpleNamespace(clicked=_FakeSignal()),
            )
            self.appearance_runtime = appearance_runtime
            self.shutdown_request = shutdown_request
            self.backdrop_mode = backdrop_mode
            self.create_body_material_surface = create_body_material_surface

        def setWindowTitle(self, _title: str) -> None:
            return None

        def setWindowIcon(self, _icon: object) -> None:
            return None

        def screen(self) -> _FakeScreen:  # type: ignore[override]
            return _FakeScreen()

        def close(self) -> bool:
            close_calls.append(self)
            return True

        def add_body_widget(self, _widget: QWidget) -> None:
            return None

    class _FakeMainWindow(QWidget):
        comfy_output_panel_visibility_changed = _FakeSignal()

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )

    fake_module = types.ModuleType("substitute.presentation.shell.main_window")
    setattr(fake_module, "MainWindow", _FakeMainWindow)

    monkeypatch.setattr(
        composition, "_configure_control_registry_service", lambda: None
    )
    monkeypatch.setattr(
        composition,
        "_build_main_window_dependencies",
        lambda _runtime_services: SimpleNamespace(
            shell_resource_lifecycle=SimpleNamespace(shutdown=lambda *_args: ())
        ),
    )
    monkeypatch.setattr(composition, "CustomWindow", _FakeFrame)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    frame = composition.show_main_window(
        context,
        comfy_output_stream=cast(Any, object()),
        shutdown_request=_noop_shutdown_request,
    )

    assert connected_callbacks == [frame.close]
    cast(Any, connected_callbacks[0])()
    assert close_calls == [frame]

    frame.close()
    app.processEvents()


def test_show_built_main_window_reapplies_shell_geometry_at_reveal() -> None:
    """Prebuilt shell reveal should not inherit splash-sized hidden geometry."""

    calls: list[tuple[str, int, int] | tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame:
        def screen(self) -> _FakeScreen:
            return _FakeScreen()

        def resize(self, width: int, height: int) -> None:
            calls.append(("resize", width, height))

        def move(self, left: int, top: int) -> None:
            calls.append(("move", left, top))

        def show(self) -> None:
            calls.append(("show",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(cast(Any, _FakeFrame()))

    assert calls[:5] == [
        ("resize", 1632, 918),
        ("move", 144, 81),
        ("show",),
        ("resize", 1632, 918),
        ("move", 144, 81),
    ]
    assert ("raise",) in calls
    assert ("activate",) in calls


def test_show_built_main_window_can_preserve_restored_geometry() -> None:
    """GUI reload reveal should not overwrite geometry restored during hydration."""

    calls: list[tuple[str, int, int] | tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame:
        def screen(self) -> _FakeScreen:
            return _FakeScreen()

        def resize(self, width: int, height: int) -> None:
            calls.append(("resize", width, height))

        def move(self, left: int, top: int) -> None:
            calls.append(("move", left, top))

        def show(self) -> None:
            calls.append(("show",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        apply_default_geometry=False,
    )

    assert calls == [("show",), ("raise",), ("activate",)]


def test_show_built_main_window_applies_initial_shell_placement_pre_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restored placement should be the first visible shell state."""

    calls: list[tuple[str, int, int, int, int] | tuple[str]] = []
    scheduled: list[tuple[object, ...]] = []

    class _FakeFrame:
        def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
            calls.append(("geometry", x, y, width, height))

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    monkeypatch.setattr(
        composition,
        "_apply_main_window_geometry",
        lambda _frame: calls.append(("fallback",)),
    )
    qt_timer = getattr(composition, "QTimer")
    monkeypatch.setattr(qt_timer, "singleShot", lambda *_args: scheduled.append(_args))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=WindowGeometrySnapshot(x=11, y=22, width=1234, height=700),
            window_display_state="normal",
            maximized=False,
        ),
    )

    assert calls == [
        ("geometry", 11, 22, 1234, 700),
        ("show",),
        ("raise",),
        ("activate",),
    ]
    assert len(scheduled) == 1
    callback = cast(Callable[[], None], scheduled[0][1])
    callback()
    assert calls == [
        ("geometry", 11, 22, 1234, 700),
        ("show",),
        ("raise",),
        ("activate",),
        ("raise",),
        ("activate",),
    ]


def test_show_built_main_window_restores_maximized_display_state() -> None:
    """Saved maximized state should use the corresponding first show call."""

    calls: list[tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeFrame:
        def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
            calls.append(("geometry", x, y, width, height))

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=WindowGeometrySnapshot(x=10, y=20, width=1000, height=600),
            window_display_state="normal",
            maximized=True,
        ),
    )

    assert calls == [
        ("geometry", 10, 20, 1000, 600),
        ("maximized",),
        ("raise",),
        ("activate",),
    ]


def test_show_built_main_window_restores_fullscreen_display_state() -> None:
    """Saved fullscreen state should use the corresponding first show call."""

    calls: list[tuple[str]] = []

    class _FakeFrame:
        def setGeometry(self, _x: int, _y: int, _width: int, _height: int) -> None:
            """Accept optional restored geometry."""

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=None,
            window_display_state="fullscreen",
            maximized=False,
        ),
    )

    assert calls == [("fullscreen",), ("raise",), ("activate",)]


def test_run_application_routes_broken_setup_to_repair_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repair route should show the repair surface instead of onboarding."""

    fake_app = _FakeApp(exit_code=0)
    persisted_context = _build_ready_context(tmp_path)
    shown_routes: list[str] = []

    class _Signal:
        def connect(self, _callback: object) -> None:
            """Accept one connected callback."""

    window = type(
        "_Window",
        (),
        {
            "launch_requested": _Signal(),
            "close_requested": _Signal(),
        },
    )()

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=persisted_context,
        route=BootstrapRoute.REPAIR,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_onboarding_window",
        lambda **_kwargs: _record_route(shown_routes, "onboarding", window),
    )
    monkeypatch.setattr(
        startup.composition,
        "show_repair_window",
        lambda **_kwargs: _record_route(shown_routes, "repair", window),
    )
    monkeypatch.setattr(
        startup_splash_controller,
        "start_launch_splash",
        lambda **_kwargs: pytest.fail("repair route must not launch splash"),
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _managed_cleanup_result,
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py", "--no-comfy"])

    assert exit_code == 0
    assert shown_routes == ["repair"]


def test_run_application_routes_repair_after_prepared_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Startup should use the prepared environment for repair routing."""

    fake_app = _FakeApp(exit_code=0)
    persisted_context = _build_managed_ready_context(tmp_path)

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance_stub(),
    )
    _patch_startup_environment(
        monkeypatch,
        install_root=tmp_path,
        context=persisted_context,
        route=BootstrapRoute.REPAIR,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_repair_window",
        lambda **_kwargs: type(
            "_Window",
            (),
            {
                "launch_requested": type(
                    "_Signal", (), {"connect": staticmethod(lambda _callback: None)}
                )(),
                "close_requested": type(
                    "_Signal", (), {"connect": staticmethod(lambda _callback: None)}
                )(),
            },
        )(),
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _managed_cleanup_result,
    )
    monkeypatch.setattr(
        startup.lifecycle, "register_shutdown_handlers", lambda _app, _cleanup: None
    )

    _ensure_runtime_qapplication()
    exit_code = startup.run_application(["main.py", "--no-comfy"])

    assert exit_code == 0


def test_show_main_window_closes_generation_execution_on_frame_destroyed() -> None:
    """Shell destruction should close the shared resource lifecycle owner."""

    source = Path(composition.__file__).read_text(encoding="utf-8")

    assert '"generation_job_queue"' in source
    assert '"workspace_generation"' in source
    assert (
        "frame.destroyed.connect(dependencies.shell_resource_lifecycle.shutdown)"
        in source
    )


def _record_show_main(
    calls: list[InstallationContext],
    context: InstallationContext,
) -> object:
    """Record one show-main invocation and return a placeholder shell object."""

    calls.append(context)
    return object()


def _record_show_main_with_shutdown(
    calls: list[object],
    context: InstallationContext,
    shutdown_request: object,
) -> object:
    """Record one show-main invocation and the injected shutdown request."""

    _ = context
    calls.append(shutdown_request)
    return object()


def _noop_shutdown_request(_parent: QWidget | None = None) -> None:
    """Provide one typed no-op shutdown callback for shell composition tests."""


def _record_route(
    calls: list[str],
    route_name: str,
    window: object,
) -> object:
    """Record one routed window invocation and return the supplied window."""

    calls.append(route_name)
    return window


def _record_cleanup(calls: list[str]) -> Callable[[], ManagedComfyCleanupResult]:
    """Build one cleanup fake that records each invocation."""

    def cleanup() -> ManagedComfyCleanupResult:
        """Record cleanup and return a lifecycle result."""

        calls.append("cleanup")
        return _managed_cleanup_result()

    return cleanup


def _managed_cleanup_result() -> ManagedComfyCleanupResult:
    """Build one successful managed-Comfy cleanup result for startup tests."""

    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        managed_resource_present=False,
        live_process_present=False,
        metadata_present=False,
        used_persisted_metadata=False,
        termination_attempted=False,
        registry_cleared=True,
        pid=None,
        host=None,
        port=None,
        workspace=None,
        elapsed_ms=0,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="No managed ComfyUI cleanup was required.",
        technical_detail="No managed ComfyUI cleanup was required.",
        diagnostic_detail="No managed ComfyUI cleanup was required.",
    )


class _FakeCloseEvent:
    """Provide the minimal close-event surface used by shell close tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True
