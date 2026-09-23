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

"""Qualify installer plan persistence and onboarding action exchange."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QAbstractButton, QWidget


from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)
from substitute.presentation.onboarding.installer_qualification import (
    OnboardingQualificationDriver,
)
from substitute.app.bootstrap.main_shell_qualification import (
    MainShellQualificationDriver,
    schedule_main_shell_qualification,
)
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_signal


def test_qualification_plan_round_trips_through_environment(tmp_path: Path) -> None:
    """Installer children should inherit one exact typed qualification plan."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        force_cpu_mode=True,
    )

    restored = InstallerQualificationPlan.from_environment(
        {INSTALLER_QUALIFICATION_PLAN_ENV: plan.to_json()}
    )

    assert restored == plan


def test_qualification_plan_exchanges_one_token_bound_shutdown_request(
    tmp_path: Path,
) -> None:
    """The installed shell should consume exactly one authenticated close request."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
    )

    assert plan.consume_main_shell_shutdown_request() is False

    plan.request_main_shell_shutdown()

    assert plan.consume_main_shell_shutdown_request() is True
    assert plan.consume_main_shell_shutdown_request() is False
    assert not plan.main_shell_shutdown_request_path.exists()


def test_qualification_plan_rejects_a_foreign_shutdown_request(tmp_path: Path) -> None:
    """A stale or foreign qualification must not close the running application."""

    plan = InstallerQualificationPlan(
        token="current-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
    )
    request_path = plan.main_shell_shutdown_request_path
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "foreign-token",
                "kind": "main_shell_shutdown",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not belong"):
        plan.consume_main_shell_shutdown_request()

    assert request_path.exists()


def test_main_shell_driver_closes_the_real_surface_after_authenticated_request(
    tmp_path: Path,
) -> None:
    """The qualification driver should invoke the same close action as the user."""

    events: list[str] = []
    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
    )
    plan.request_main_shell_shutdown()
    driver = cast(
        MainShellQualificationDriver,
        SimpleNamespace(
            _plan=plan,
            _timer=SimpleNamespace(stop=lambda: events.append("timer.stop")),
            _window=SimpleNamespace(close=lambda: events.append("window.close")),
        ),
    )

    MainShellQualificationDriver._poll_shutdown_request(driver)

    assert events == ["timer.stop", "window.close"]
    event_payload = json.loads(
        plan.event_log_path.read_text(encoding="utf-8").splitlines()[-1]
    )
    assert event_payload["event"] == "main_shell.shutdown.requested"


def test_scheduled_main_shell_driver_survives_until_the_real_widget_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parent-owned polling driver should close a painted QWidget normally."""

    ensure_qt_application()
    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
    )
    monkeypatch.setenv(INSTALLER_QUALIFICATION_PLAN_ENV, plan.to_json())
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    destroyed = QSignalSpy(window.destroyed)
    window.show()

    assert schedule_main_shell_qualification(window) is True
    plan.request_main_shell_shutdown()
    wait_for_qt_signal(destroyed, timeout_ms=2000)

    assert destroyed.count() == 1
    assert "main_shell.shutdown.requested" in plan.event_log_path.read_text(
        encoding="utf-8"
    )


def test_legacy_qualification_plan_defaults_cpu_override_off(tmp_path: Path) -> None:
    """Older serialized plans should remain compatible without forcing CPU."""

    payload = {
        "schema_version": 2,
        "token": "qualification-token",
        "install_root": str((tmp_path / "install").resolve()),
        "endpoint_host": "127.0.0.1",
        "endpoint_port": 8188,
        "event_log_path": str((tmp_path / "events.jsonl").resolve()),
        "timeout_seconds": 45.0,
    }

    restored = InstallerQualificationPlan.from_json(json.dumps(payload))

    assert restored.force_cpu_mode is False
    assert (
        restored.readiness_receipt_path
        == (
            tmp_path / "install" / "launcher" / "readiness" / "ci-installer-chain.json"
        ).resolve()
    )


def test_managed_qualification_applies_explicit_cpu_choice(tmp_path: Path) -> None:
    """The production managed page should receive the platform qualification choice."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=48188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        target_mode="managed_local",
        managed_workspace_path=(tmp_path / "comfyui").resolve(),
        force_cpu_mode=True,
    )
    values: dict[str, object] = {}
    checkbox = SimpleNamespace(
        setChecked=lambda value: values.__setitem__("force_cpu", value)
    )
    window = SimpleNamespace(
        managed_local_page=SimpleNamespace(
            runtime_summary_panel=SimpleNamespace(force_cpu_checkbox=checkbox)
        )
    )
    widgets = {
        "OnboardingManagedHostEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("host", value)
        ),
        "OnboardingManagedPortSpinBox": SimpleNamespace(
            setValue=lambda value: values.__setitem__("port", value)
        ),
        "OnboardingManagedWorkspaceEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("workspace", value)
        ),
    }
    driver = cast(
        OnboardingQualificationDriver,
        SimpleNamespace(
            _plan=plan,
            _window=window,
            _wait_for_page=lambda _page: None,
            _widget=lambda _type, name: widgets[name],
        ),
    )

    OnboardingQualificationDriver._configure_managed_target(driver)

    assert values == {
        "force_cpu": True,
        "host": "127.0.0.1",
        "port": 48188,
        "workspace": str((tmp_path / "comfyui").resolve()),
    }


def test_terminal_onboarding_action_runs_on_outer_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Open action should not destroy its widget during a synthetic mouse event."""

    events: list[str] = []
    waits: list[str] = []
    control = SimpleNamespace(click=lambda: events.append("control.click"))
    plan = SimpleNamespace(
        record=lambda event: events.append(event),
    )

    def wait_until(predicate: object, description: str) -> None:
        """Require the terminal control to become visible before its final click."""

        assert callable(predicate)
        assert predicate() is True
        waits.append(description)

    def activate_terminal(candidate: object) -> None:
        """Invoke the production activation helper from the scheduled callback."""

        OnboardingQualificationDriver._activate_terminal_action(
            driver,
            cast(QAbstractButton, candidate),
        )

    def schedule_terminal(_delay: int, callback: object) -> None:
        """Run the captured callback after recording its event-loop handoff."""

        assert callable(callback)
        events.append("scheduled")
        callback()

    driver = cast(
        OnboardingQualificationDriver,
        SimpleNamespace(
            _activate_terminal_action=activate_terminal,
            _control_is_clickable=lambda _name: True,
            _wait_until=wait_until,
            _widget=lambda _type, _name: control,
            _plan=plan,
        ),
    )
    monkeypatch.setattr(
        "substitute.presentation.onboarding.installer_qualification.QTimer.singleShot",
        schedule_terminal,
    )
    monkeypatch.setattr(
        OnboardingQualificationDriver,
        "_process_events",
        lambda *_args, **_kwargs: pytest.fail(
            "terminal handoff must not start a nested Qt event wait"
        ),
    )

    OnboardingQualificationDriver._click_terminal_action(
        driver,
        "OnboardingPrimaryButton",
    )

    assert waits == ["clickable control OnboardingPrimaryButton"]
    assert events == [
        "scheduled",
        "onboarding.open_substitute.clicked",
        "control.click",
    ]


def test_successful_provisioning_observes_automatic_completion_transition() -> None:
    """Qualification must not click the reused primary action after provisioning."""

    events: list[str] = []
    completion = object()
    driver = cast(
        OnboardingQualificationDriver,
        SimpleNamespace(
            _window=SimpleNamespace(_controller=SimpleNamespace(completion=completion)),
            _wait_until=lambda predicate, description: events.extend(
                [description, f"ready={predicate()}"]
            ),
            _wait_for_page=lambda page: events.append(page),
        ),
    )

    OnboardingQualificationDriver._wait_for_completion_page(driver)

    assert events == [
        "onboarding completion",
        "ready=True",
        "OnboardingCompletionPage",
    ]
