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

import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher import application_launch
from launcher.sugarsubstitute_launcher import crash_routing
from launcher.sugarsubstitute_launcher import installed_app_handoff
from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher import splash_session
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_broker import (
    ApplicationInstanceBroker,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from tests.launcher.support import write_launcher_executable


class _Broker:
    """Provide deterministic broker behavior for launcher orchestration tests."""

    def __init__(self) -> None:
        """Start as an open primary without a restart request."""

        self.closed = False

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Mark the environment as authorized by this fake supervisor."""

        child = dict(environment)
        child["TEST_INSTANCE_BROKER"] = "connected"
        return child

    def consume_restart_request(self) -> bool:
        """Report no restart request for the recorded initial run."""

        return False

    def close(self) -> None:
        """Record release of supervisor ownership."""

        self.closed = True


def _installed_layout(tmp_path: Path) -> InstallLayout:
    """Create the minimum launchable installed layout."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    return layout


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
        "elect_installed_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "ApplicationCrashSupervisor",
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


def test_duplicate_launcher_forwards_before_creating_a_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A losing launcher should exit without another supervisor, app, or surface."""

    layout = _installed_layout(tmp_path)
    observed_arguments: list[tuple[str, ...]] = []
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))

    def forward(_layout: InstallLayout, arguments: Sequence[str]) -> None:
        """Capture the invocation already accepted by the active supervisor."""

        observed_arguments.append(tuple(arguments))
        return None

    monkeypatch.setattr(application_launch, "elect_installed_application", forward)
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: pytest.fail("A duplicate must not create another splash."),
    )

    assert launcher_app.main(["--locale=en"]) == 0
    assert observed_arguments == [(sys.argv[0], "--locale=en")]


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
        "elect_installed_application",
        lambda _layout, _arguments: broker,
    )
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: None,
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


def test_installed_election_uses_the_resolved_installation_identity(
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
        application_launch.elect_installed_application(
            layout,
            ["Substitute", "example.sugar"],
        )
        is None
    )
    assert observed == [(layout.root, ("Substitute", "example.sugar"))]
