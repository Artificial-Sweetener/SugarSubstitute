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

"""Verify installed launcher election and supervised application routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher import application_launch
from launcher.sugarsubstitute_launcher import crash_routing
from launcher.sugarsubstitute_launcher import installed_app_handoff
from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher import logging_setup
from launcher.sugarsubstitute_launcher import localization
from launcher.sugarsubstitute_launcher import splash_session
from launcher.sugarsubstitute_launcher import startup_plan
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
)
from sugarsubstitute_shared.application_instance_broker import (
    ApplicationInstanceBroker,
)
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore
from sugarsubstitute_shared.windows_long_paths import subprocess_path


from tests.launcher.application_launch.instance_routing_support import (
    BrokerDouble as _Broker,
    installed_layout as _installed_layout,
)


def test_installed_launcher_supervises_one_broker_authorized_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The elected launcher should remain through the complete child lifetime."""

    layout = _installed_layout(tmp_path)
    broker = _Broker()
    calls: list[tuple[list[str], dict[str, str]]] = []

    class _Supervisor:
        """Capture the installed application process without spawning it."""

        def __init__(self, **kwargs: object) -> None:
            """Accept the startup cancellation policy at the process boundary."""

        def supervise(self, **kwargs: object) -> int:
            """Record command and environment at the crash-owner boundary."""

            command = kwargs["command"]
            environment = kwargs["environment"]
            assert isinstance(command, Sequence)
            assert isinstance(environment, Mapping)
            calls.append((list(command), dict(environment)))
            return 0

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: SimpleNamespace(
            app_arguments=(),
            client=None,
            ensure_closed=lambda: None,
            cancellation_requested=lambda: False,
            present=lambda: "startup-splash",
        ),
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "ApplicationLifecycleSupervisor",
        _Supervisor,
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert calls[0][0] == [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        "--locale=en",
    ]
    assert calls[0][1]["TEST_INSTANCE_BROKER"] == "connected"
    assert broker.closed


def test_installed_launcher_performs_only_reviewed_work_before_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep nonessential startup work behind the visible splash boundary."""

    layout = _installed_layout(tmp_path)
    broker = _Broker()
    events: list[str] = []
    original_resolve_candidate = startup_plan.resolve_startup_candidate
    original_should_attempt = startup_plan.should_attempt_installed_app_launch
    original_resolve_locale = localization.resolve_launcher_locale

    def resolve_candidate(**kwargs: object) -> object:
        """Record install-root discovery while preserving production behavior."""

        events.append("install-root")
        return original_resolve_candidate(**kwargs)  # type: ignore[arg-type]

    def should_attempt(**kwargs: object) -> bool:
        """Record the minimum route decision before splash presentation."""

        events.append("launch-route")
        return original_should_attempt(**kwargs)  # type: ignore[arg-type]

    def resolve_locale(*args: object, **kwargs: object) -> object:
        """Record locale resolution while preserving its effective language."""

        events.append("locale")
        return original_resolve_locale(*args, **kwargs)  # type: ignore[arg-type]

    class _Splash:
        """Provide the startup presentation contract without a Qt process."""

        def present(self) -> str:
            """Report the already-visible startup surface."""

            return "startup-splash"

    def elect(_layout: InstallLayout, _arguments: Sequence[str]) -> _Broker:
        """Record owner election and return the deterministic primary."""

        events.append("election")
        return broker

    def start_splash(**_kwargs: object) -> _Splash:
        """Record the presentation boundary and return a visible surface."""

        events.append("splash")
        return _Splash()

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        crash_routing,
        "route_explicit_crash_operation",
        lambda _args: events.append("crash-route"),
    )
    monkeypatch.setattr(startup_plan, "resolve_startup_candidate", resolve_candidate)
    monkeypatch.setattr(
        startup_plan, "should_attempt_installed_app_launch", should_attempt
    )
    monkeypatch.setattr(
        logging_setup,
        "configure_launcher_logging",
        lambda **_kwargs: events.append("logging"),
    )
    monkeypatch.setattr(
        localization,
        "resolve_launcher_locale",
        resolve_locale,
    )
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        elect,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        start_splash,
    )
    monkeypatch.setattr(
        crash_routing,
        "recover_pending_crash_reports",
        lambda **_kwargs: events.append("crash-recovery"),
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "complete_installed_app_handoff",
        lambda **_kwargs: events.append("handoff"),
    )
    monkeypatch.setattr(launcher_app, "_configure_normal_logging", lambda _plan: None)

    assert launcher_app.main(["--locale=en"]) == 0
    assert events[:6] == [
        "crash-route",
        "install-root",
        "logging",
        "election",
        "launch-route",
        "splash",
    ]
    assert events[6:] == ["locale", "crash-recovery", "handoff"]


def test_pending_report_recovery_failure_does_not_open_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reporter defects must not reclassify a launchable installation as damaged."""

    layout = _installed_layout(tmp_path)
    broker = _Broker()
    handoffs: list[InstallLayout] = []
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: SimpleNamespace(
            app_arguments=(),
            client=None,
            ensure_closed=lambda: None,
            cancellation_requested=lambda: False,
            present=lambda: "startup-splash",
        ),
    )
    monkeypatch.setattr(
        crash_routing,
        "recover_pending_crash_reports",
        lambda **_kwargs: (_ for _ in ()).throw(ImportError("QtWidgets unavailable")),
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "complete_installed_app_handoff",
        lambda **kwargs: handoffs.append(kwargs["layout"]),
    )
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        lambda **_kwargs: pytest.fail("Reporter failure must not open repair."),
    )

    assert launcher_app.main([]) == 0
    assert handoffs == [layout]
    assert broker.closed


def test_unavailable_installed_splash_routes_to_visible_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never continue a potentially long installed launch without a surface."""

    layout = _installed_layout(tmp_path)
    broker = _Broker()
    repair_requests: list[bool] = []
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "complete_installed_app_handoff",
        lambda **_kwargs: pytest.fail("Invisible application launch is forbidden."),
    )

    def supervise_repair(**kwargs: object) -> int:
        """Record that invisible startup routes to a repair surface."""

        repair_requests.append(bool(kwargs["repair"]))
        return 0

    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        supervise_repair,
    )

    assert launcher_app.main([]) == 0
    assert repair_requests == [True]
    assert broker.closed


def test_launch_failure_closes_splash_only_after_repair_window_is_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep the existing surface alive until painted repair replaces it."""

    layout = _installed_layout(tmp_path)
    broker = _Broker()
    events: list[str] = []

    class _Splash:
        """Record idempotent closure of the visible startup surface."""

        closed = False

        def present(self) -> str:
            """Report the visible startup surface."""

            return "startup-splash"

        def close(self) -> None:
            """Record the first applied surface closure."""

            if not self.closed:
                self.closed = True
                events.append("splash-closed")

    splash = _Splash()
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: splash,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "complete_installed_app_handoff",
        lambda **_kwargs: (_ for _ in ()).throw(
            ApplicationReadinessError(
                "child failed",
                incident_id="startup-incident",
            )
        ),
    )
    monkeypatch.setattr(
        CrashIncidentStore,
        "acknowledge",
        lambda _store, incident_id: events.append(f"acknowledged-{incident_id}"),
    )

    def supervise_repair(**kwargs: object) -> int:
        """Simulate a painted repair window through its readiness callback."""

        events.append("repair-started")
        assert events == ["repair-started"]
        environment = kwargs["environment"]
        assert isinstance(environment, Mapping)
        assert environment["TEST_INSTANCE_BROKER"] == "connected"
        on_ready = kwargs["on_ready"]
        assert callable(on_ready)
        on_ready()
        events.append("repair-ready")
        return 0

    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        supervise_repair,
    )

    assert launcher_app.main([]) == 0
    assert events == [
        "repair-started",
        "acknowledged-startup-incident",
        "splash-closed",
        "repair-ready",
    ]
    assert broker.startup_presenters[-1] is None
    assert broker.closed


def test_application_election_uses_the_resolved_installation_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep election rooted in the resolved install rather than the working directory."""

    layout = _installed_layout(tmp_path)
    observed: list[tuple[Path, tuple[str, ...]]] = []

    def elect(
        *,
        install_root: Path,
        invocation: object,
    ) -> ApplicationInstanceBroker | None:
        """Record the native election inputs without opening an endpoint."""

        arguments = getattr(invocation, "arguments")
        observed.append((install_root, tuple(arguments)))
        return None

    monkeypatch.setattr(ApplicationInstanceBroker, "elect", elect)

    assert (
        application_launch.elect_application(
            layout,
            ["Substitute", "example.sugar"],
        )
        is None
    )
    assert observed == [(layout.root, ("Substitute", "example.sugar"))]


def test_failed_secondary_activation_shows_recovery_and_retries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Never leave an invocation with only an invisible broker failure."""

    layout = _installed_layout(tmp_path)
    expected_broker = _Broker()
    attempts = 0
    presented: list[bool] = []
    expected_result = cast(ApplicationInstanceBroker, expected_broker)

    def elect(
        _layout: InstallLayout,
        _arguments: Sequence[str],
    ) -> ApplicationInstanceBroker:
        """Fail once like an unresponsive owner and then win election."""

        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ApplicationInstanceBrokerError("not presented")
        return expected_result

    def present_recovery(**kwargs: object) -> InstanceRecoveryAction:
        """Record recovery eligibility and request a bounded retry."""

        presented.append(bool(kwargs["can_end_owner"]))
        return InstanceRecoveryAction.RETRY

    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_instance_recovery_window",
        present_recovery,
    )

    result = ApplicationElectionRecovery(
        layout=layout,
        process_arguments=("Substitute",),
        locale_override="en",
        elect=elect,
    ).run()

    assert result is expected_result
    assert attempts == 2
    assert presented == [False]
