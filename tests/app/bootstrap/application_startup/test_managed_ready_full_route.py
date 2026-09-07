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

"""Cover the complete managed-ready startup route."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap import (
    startup,
    startup_environment,
    startup_managed_ready_ports,
    startup_managed_ready_shell_launcher,
    startup_probe_tasks,
    startup_readiness_runtime,
    startup_restore_plan,
    startup_shell_runtime,
    startup_splash_controller,
    startup_warmup_controller,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from tests.support.execution import ImmediateTaskSubmitter
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

from .runtime_fakes import build_startup_runtime_services_fake
from substitute.shared.cutecanvas_sam_warmup_state import (
    CuteCanvasSamWarmupSnapshot,
    set_cutecanvas_sam_warmup_snapshot,
)


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

    def request_quit(self) -> None:
        """Model the queued application-exit boundary."""

        self.quit()


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
    monkeypatch.setattr(
        startup.composition,
        "build_application_runtime_services",
        lambda **_kwargs: build_startup_runtime_services_fake(),
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


def _record_cleanup(calls: list[str]) -> Callable[[], ManagedComfyCleanupResult]:
    """Build one cleanup fake that records managed-route disposal."""

    def cleanup() -> ManagedComfyCleanupResult:
        """Record cleanup and return a successful receipt."""

        calls.append("cleanup")
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

    return cleanup


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

    class _FakeCuteCanvasSamWarmupHandle:
        def __init__(self, **_kwargs: object) -> None:
            """Accept warmup dependencies without importing optional packages."""

        def start(self) -> None:
            """Complete the dependency prerequisite without importing packages."""

            set_cutecanvas_sam_warmup_snapshot(
                CuteCanvasSamWarmupSnapshot(state="completed")
            )

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
        "CuteCanvasSamStartupWarmupHandle",
        _FakeCuteCanvasSamWarmupHandle,
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
    assert calls[:3] == [
        "splash",
        "single_shot",
        "exec",
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
