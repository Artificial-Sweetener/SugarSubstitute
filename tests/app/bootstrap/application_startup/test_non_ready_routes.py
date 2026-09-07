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

"""Cover non-ready startup routing through the application boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap import (
    startup,
    startup_environment,
    startup_splash_controller,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
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


class _FakeApp:
    """Provide the application lifecycle used by non-ready routes."""

    def __init__(self, exit_code: int) -> None:
        """Store the expected event-loop outcome."""

        self._exit_code = exit_code

    def exec(self) -> int:
        """Return the configured event-loop outcome."""

        return self._exit_code

    def quit(self) -> None:
        """Accept an unexpected shutdown request from the route boundary."""

    def request_quit(self) -> None:
        """Accept a phase-safe shutdown request from the route boundary."""


class _Signal:
    """Accept callbacks registered by routed windows."""

    def connect(self, _callback: object) -> None:
        """Accept the callback without executing it."""


class _RouteWindow:
    """Expose the route-window signals consumed by application startup."""

    def __init__(self) -> None:
        """Create route-window signal endpoints."""

        self.launch_requested = _Signal()
        self.close_requested = _Signal()


def _ensure_qapplication() -> None:
    """Ensure production runtime composition can resolve a Qt application."""

    if QApplication.instance() is None:
        QApplication([])


def _resolved_appearance() -> object:
    """Return the resolved appearance surface required during startup."""

    return SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_accent_color="#E91E63",
        effective_backdrop_mode=None,
    )


def _context(tmp_path: Path, *, managed: bool) -> InstallationContext:
    """Build a ready installation context for one route outcome."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL if managed else ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir if managed else None,
        install_owned=managed,
        launch_owned=managed,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _patch_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    install_root: Path,
    context: InstallationContext,
    route: BootstrapRoute,
) -> None:
    """Provide deterministic environment preparation for one route."""

    assessment = ReadinessAssessment(route=route, issues=())
    service_bundle = SimpleNamespace(
        readiness_service=SimpleNamespace(assess=lambda: assessment)
    )

    def prepare_environment(
        **_kwargs: object,
    ) -> startup_environment.StartupEnvironment:
        """Return the ready context and requested route."""

        return startup_environment.StartupEnvironment(
            install_root=install_root,
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


def _successful_cleanup() -> ManagedComfyCleanupResult:
    """Return the no-op cleanup result required by route startup."""

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


def _prepare_route_startup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    context: InstallationContext,
    route: BootstrapRoute,
) -> _FakeApp:
    """Patch startup collaborators shared by non-ready route contracts."""

    app = _FakeApp(exit_code=0)
    monkeypatch.setattr(startup.lifecycle, "register_signal_handlers", lambda: None)
    monkeypatch.setattr(startup, "install_qt_message_trace_handler", lambda: None)
    monkeypatch.setattr(startup.composition, "create_application", lambda _argv: app)
    monkeypatch.setattr(
        startup.composition,
        "configure_theme",
        lambda _appearance_runtime: _resolved_appearance(),
    )
    monkeypatch.setattr(
        startup.composition,
        "build_application_runtime_services",
        lambda **_kwargs: build_startup_runtime_services_fake(),
    )
    monkeypatch.setattr(
        startup,
        "prepare_startup_restore_plan",
        lambda **_kwargs: SimpleNamespace(
            restore_plan=SimpleNamespace(
                workspace=None,
                shell_placement=None,
                provisional_restore_projection=None,
            ),
            restore_asset_preload=None,
        ),
    )
    _patch_environment(
        monkeypatch,
        install_root=tmp_path,
        context=context,
        route=route,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "create_cleanup_handler",
        lambda _getter, _kill: _successful_cleanup,
    )
    monkeypatch.setattr(
        startup.lifecycle,
        "register_shutdown_handlers",
        lambda _app, _cleanup: None,
    )
    return app


def test_run_application_routes_missing_setup_to_onboarding_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Route missing setup to onboarding without starting the managed splash."""

    shown_routes: list[str] = []
    window = _RouteWindow()
    context = _context(tmp_path, managed=False)
    _prepare_route_startup(
        monkeypatch,
        tmp_path=tmp_path,
        context=context,
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

    _ensure_qapplication()

    assert startup.run_application(["main.py", "--no-comfy"]) == 0
    assert shown_routes == ["onboarding"]


def test_run_application_routes_broken_setup_to_repair_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Route broken setup to repair rather than the onboarding surface."""

    shown_routes: list[str] = []
    window = _RouteWindow()
    context = _context(tmp_path, managed=False)
    _prepare_route_startup(
        monkeypatch,
        tmp_path=tmp_path,
        context=context,
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

    _ensure_qapplication()

    assert startup.run_application(["main.py", "--no-comfy"]) == 0
    assert shown_routes == ["repair"]


def test_run_application_routes_repair_after_prepared_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Preserve managed-ready context while routing an assessed repair outcome."""

    context = _context(tmp_path, managed=True)
    _prepare_route_startup(
        monkeypatch,
        tmp_path=tmp_path,
        context=context,
        route=BootstrapRoute.REPAIR,
    )
    monkeypatch.setattr(
        startup.composition,
        "show_repair_window",
        lambda **_kwargs: _RouteWindow(),
    )

    _ensure_qapplication()

    assert startup.run_application(["main.py", "--no-comfy"]) == 0


def _record_route(calls: list[str], route_name: str, window: object) -> object:
    """Record one route-window selection and return its window."""

    calls.append(route_name)
    return window
