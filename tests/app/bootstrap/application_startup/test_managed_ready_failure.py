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

"""Cover fatal managed-ready startup routing through the application boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap import (
    startup,
    startup_environment,
    startup_managed_ready_ports,
    startup_restore_plan,
    startup_splash_controller,
    startup_warmup_controller,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
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

from .runtime_fakes import build_startup_runtime_services_fake
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)
from substitute.shared.cutecanvas_sam_warmup_state import (
    CuteCanvasSamWarmupSnapshot,
    set_cutecanvas_sam_warmup_snapshot,
)


class _FakeApp:
    """Provide a queued application lifecycle for managed startup."""

    def __init__(self, callbacks: list[Callable[[], None]]) -> None:
        """Store startup callbacks and initialize application state."""

        self._callbacks = callbacks
        self.quit_calls = 0

    def exec(self) -> int:
        """Drain the queued startup work before completing the event loop."""

        while self._callbacks:
            self._callbacks.pop(0)()
        for timer in _FakeTimer.instances:
            if timer.started and timer.timeout.callback is not None:
                timer.timeout.callback()
        return 0

    def quit(self) -> None:
        """Record application shutdown after fatal startup failure."""

        self.quit_calls += 1

    def request_quit(self) -> None:
        """Model the queued application-exit boundary."""

        self.quit()


class _FakeSignal:
    """Store one signal callback for deterministic timer delivery."""

    def __init__(self) -> None:
        """Initialize with no connected callback."""

        self.callback: Callable[[], None] | None = None

    def connect(self, callback: object) -> None:
        """Store the callback supplied by production startup code."""

        self.callback = cast(Callable[[], None], callback)


class _FakeTimer:
    """Queue timer callbacks without relying on real clock progress."""

    instances: list[_FakeTimer] = []
    queued_callbacks: list[Callable[[], None]] = []
    calls: list[str] = []

    def __init__(self, parent: object = None) -> None:
        """Create one detached timer endpoint."""

        assert parent is None
        self.timeout = _FakeSignal()
        self.started = False
        self.__class__.instances.append(self)

    def setInterval(self, _interval_ms: int) -> None:
        """Accept the production probe interval."""

    def start(self) -> None:
        """Mark this timer ready for one deterministic timeout."""

        self.calls.append("timer_start")
        self.started = True

    def stop(self) -> None:
        """Record cancellation of the readiness timer."""

        self.calls.append("timer_stop")

    @staticmethod
    def singleShot(_interval_ms: int, callback: object) -> None:
        """Queue startup work for the fake event loop."""

        _FakeTimer.calls.append("single_shot")
        _FakeTimer.queued_callbacks.append(cast(Callable[[], None], callback))


class _FakeSplash:
    """Record splash output and closure across fatal startup."""

    def __init__(self, calls: list[str]) -> None:
        """Store the application lifecycle trace."""

        self._calls = calls

    def close(self) -> None:
        """Record terminal splash closure."""

        self._calls.append("splash_close")

    def append_log(self, _line: str) -> None:
        """Record output fanout while the splash is active."""

        self._calls.append("splash_log")


def _ensure_qapplication() -> None:
    """Ensure runtime startup collaborators can resolve a Qt application."""

    if QApplication.instance() is None:
        QApplication([])


def _managed_context(tmp_path: Path) -> InstallationContext:
    """Build the managed-local context required by the fatal path."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=installation.default_managed_comfy_dir,
            install_owned=True,
            launch_owned=True,
        ),
    )


def _patch_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    context: InstallationContext,
) -> None:
    """Provide the deterministic managed-ready startup environment."""

    assessment = ReadinessAssessment(route=BootstrapRoute.READY, issues=())
    service_bundle = SimpleNamespace(
        readiness_service=SimpleNamespace(assess=lambda: assessment)
    )

    def prepare_environment(
        **_kwargs: object,
    ) -> startup_environment.StartupEnvironment:
        """Return the managed-ready startup environment."""

        return startup_environment.StartupEnvironment(
            install_root=tmp_path,
            service_bundle=cast(Any, service_bundle),
            readiness_assessment=assessment,
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


def _successful_cleanup() -> ManagedComfyCleanupResult:
    """Return a successful cleanup receipt for the fatal route."""

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


def test_ready_startup_closes_splash_and_reports_fatal_managed_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Close splash, report, clean up, and quit after a fatal managed failure."""

    _FakeTimer.instances = []
    _FakeTimer.queued_callbacks = []
    _FakeTimer.calls = []
    context = _managed_context(tmp_path)
    calls = _FakeTimer.calls
    reports: list[Any] = []
    fake_app = _FakeApp(_FakeTimer.queued_callbacks)

    class _FakeMainWindow:
        """Expose the managed-ready collaborators used before failure handling."""

        cube_load_service = object()
        cube_icon_factory = object()
        model_metadata_surface_refresh_controller = SimpleNamespace(
            handle_model_metadata_updated=lambda _event: None
        )

        def __init__(self) -> None:
            """Expose backend state publication."""

            self.generation_action_controller = SimpleNamespace(
                set_backend_state=lambda state: calls.append(f"backend_{state}")
            )

    class _FakeBridge:
        """Provide the metadata signal endpoint expected by startup."""

        def __init__(self, _parent: object = None) -> None:
            """Accept the shell parent without creating Qt state."""

            self.model_updated = _FakeSignal()

    class _FakeCuteCanvasSamWarmupHandle:
        """Complete the prerequisite warmup without optional-package imports."""

        def __init__(self, **_kwargs: object) -> None:
            """Accept production warmup dependencies."""

        def start(self) -> None:
            """Publish deterministic warmup completion."""

            set_cutecanvas_sam_warmup_snapshot(
                CuteCanvasSamWarmupSnapshot(state="completed")
            )

        def shutdown(self) -> None:
            """Accept cleanup without side effects."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message="ComfyUI exited before it became ready.",
        source=str(context.managed_comfy_dir),
        fingerprint="fatal",
        log_excerpt=("Traceback (most recent call last):", "RuntimeError: boom"),
        values={"pid": 123, "exit_code": 1},
    )
    state = process_manager.ManagedComfyState(registry=ManagedProcessRegistry(tmp_path))
    state.startup_result = ManagedStartupReadinessResult(
        ready=False,
        fatal_incident=incident,
    )
    state.request_stop = lambda **_kwargs: calls.append("managed_stop")  # type: ignore[method-assign]
    frame = SimpleNamespace()
    main_window = _FakeMainWindow()

    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(
        startup.composition, "create_application", lambda _argv: fake_app
    )
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: SimpleNamespace(
            effective_theme_mode=SimpleNamespace(value="dark"),
            effective_accent_color="#E91E63",
            effective_backdrop_mode=None,
        ),
    )
    _patch_environment(monkeypatch, tmp_path=tmp_path, context=context)
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: lambda: _record_cleanup(calls),
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "register_shutdown_handlers",
        lambda _app, _cleanup: None,
    )
    monkeypatch.setattr(QtCore, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "create_model_metadata_update_bridge",
        lambda parent: _FakeBridge(parent),
    )
    monkeypatch.setattr(
        startup_warmup_controller,
        "CuteCanvasSamStartupWarmupHandle",
        _FakeCuteCanvasSamWarmupHandle,
    )
    monkeypatch.setattr(
        startup,
        "prepare_startup_restore_plan",
        lambda **_kwargs: startup_restore_plan.StartupRestorePlanPreparation(
            restore_plan=cast(
                Any,
                SimpleNamespace(
                    workspace=None,
                    shell_placement=None,
                    provisional_restore_projection=None,
                ),
            ),
            restore_asset_preload=None,
        ),
    )
    monkeypatch.setattr(
        startup_splash_controller,
        "start_launch_splash",
        lambda **_kwargs: _FakeSplash(calls),
    )
    monkeypatch.setattr(
        startup_managed_ready_ports,
        "activate_target",
        lambda **_kwargs: state,
    )
    monkeypatch.setattr(
        startup.composition,
        "build_main_window",
        lambda *_args, **_kwargs: frame,
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
        reports.append,
    )

    _ensure_qapplication()

    assert startup.run_application(["main.py"]) == 0
    assert fake_app.quit_calls == 1
    assert "managed_stop" in calls
    assert "cleanup" in calls
    assert "splash_close" in calls
    assert reports[0].message == "ComfyUI exited before it became ready."
    assert "show" not in calls


def _record_cleanup(calls: list[str]) -> ManagedComfyCleanupResult:
    """Record cleanup and return its successful receipt."""

    calls.append("cleanup")
    return _successful_cleanup()
