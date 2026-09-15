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

"""Verify launcher election for duplicate setup and repair invocations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher import application_launch
from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher import splash_session
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tests.launcher.application_launch.instance_routing_support import (
    BrokerDouble,
    installed_layout,
)


def test_duplicate_launcher_forwards_before_creating_a_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A losing launcher should exit without another supervisor, app, or surface."""

    layout = installed_layout(tmp_path)
    observed_arguments: list[tuple[str, ...]] = []
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))

    def forward(_layout: InstallLayout, arguments: Sequence[str]) -> None:
        """Capture the invocation already accepted by the active supervisor."""

        observed_arguments.append(tuple(arguments))
        return None

    monkeypatch.setattr(application_launch, "elect_application", forward)
    monkeypatch.setattr(
        splash_session,
        "start_launcher_splash_session",
        lambda **_kwargs: pytest.fail("A duplicate must not create another splash."),
    )

    assert launcher_app.main(["--locale=en"]) == 0
    assert observed_arguments == [(sys.argv[0], "--locale=en")]


def test_duplicate_fresh_setup_forwards_before_creating_a_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A second first-run launcher must activate the existing setup surface."""

    install_root = tmp_path / "fresh-install"
    observed_arguments: list[tuple[str, ...]] = []

    def forward(_layout: InstallLayout, arguments: Sequence[str]) -> None:
        """Capture the setup invocation accepted by the active supervisor."""

        observed_arguments.append(tuple(arguments))
        return None

    monkeypatch.setattr(application_launch, "elect_application", forward)
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        lambda **_kwargs: pytest.fail("A duplicate must not create another setup UI."),
    )

    assert launcher_app.main([f"--install-root={install_root}"]) == 0
    assert observed_arguments == [(sys.argv[0], f"--install-root={install_root}")]


def test_duplicate_repair_forwards_before_creating_a_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A second repair launcher must activate the existing recovery surface."""

    layout = installed_layout(tmp_path)
    observed_arguments: list[tuple[str, ...]] = []
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))

    def forward(_layout: InstallLayout, arguments: Sequence[str]) -> None:
        """Capture the repair invocation accepted by the active supervisor."""

        observed_arguments.append(tuple(arguments))
        return None

    monkeypatch.setattr(application_launch, "elect_application", forward)
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        lambda **_kwargs: pytest.fail("A duplicate must not create another repair UI."),
    )

    assert launcher_app.main(["--repair", f"--install-root={layout.root}"]) == 0
    assert observed_arguments == [
        (sys.argv[0], "--repair", f"--install-root={layout.root}")
    ]


def test_primary_fresh_setup_authorizes_the_launcher_ui_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep the setup surface registered with the elected supervisor."""

    install_root = tmp_path / "fresh-install"
    broker = BrokerDouble()
    observed_environments: list[Mapping[str, str]] = []
    monkeypatch.setattr(
        application_launch,
        "elect_application",
        lambda _layout, _arguments: broker,
    )

    def supervise_setup(**kwargs: object) -> int:
        """Capture the authorized launcher child environment."""

        environment = kwargs["environment"]
        assert isinstance(environment, Mapping)
        observed_environments.append(environment)
        return 0

    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        supervise_setup,
    )

    assert launcher_app.main([f"--install-root={install_root}"]) == 0
    assert observed_environments[0]["TEST_INSTANCE_BROKER"] == "connected"
    assert broker.closed
