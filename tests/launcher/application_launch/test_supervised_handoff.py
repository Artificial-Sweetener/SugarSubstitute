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

"""Verify installer app handoffs return through the stable supervisor."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import process
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from sugarsubstitute_shared.crash_reporting.protocol import (
    CRASHPAD_CLIENT_LIBRARY_ENV,
    CRASHPAD_DATABASE_ENV,
    CRASHPAD_HANDLER_ENV,
    CRASH_EXIT_INTENT_PATH_ENV,
    CRASH_EXIT_RECEIPT_PATH_ENV,
    CRASH_INCIDENT_ROOT_ENV,
    CRASH_RUN_ID_ENV,
    CRASH_RUN_TOKEN_ENV,
)


def test_installer_handoff_builds_stable_launcher_command(tmp_path: Path) -> None:
    """Setup completion must not execute the application child directly."""

    layout = InstallLayout.from_root(tmp_path / "install")
    app_command = [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        "--handoff-geometry=10,20,1200,800",
        "--locale=ja",
        "--unrelated-internal-flag",
    ]

    assert process.build_installed_launcher_handoff_command(app_command) == [
        subprocess_path(layout.executable_path),
        f"--install-root={subprocess_path(layout.root)}",
        "--handoff-geometry=10,20,1200,800",
        "--locale=ja",
    ]


def test_installer_handoff_starts_only_stable_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The handoff adapter should delegate its rewritten launcher command."""

    layout = InstallLayout.from_root(tmp_path / "install")
    app_command = [
        "python",
        "main.py",
        f"--install-root={layout.root}",
    ]
    started: list[list[str]] = []
    monkeypatch.setattr(
        process,
        "start_detached_handoff",
        lambda command: started.append(list(command)),
    )

    process.start_installed_launcher_handoff(app_command)

    assert started == [
        [
            subprocess_path(layout.executable_path),
            f"--install-root={subprocess_path(layout.root)}",
        ]
    ]


def test_detached_handoff_drops_completed_crash_supervision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new stable launcher must not inherit a partial prior-run contract."""

    crash_names = (
        CRASH_RUN_ID_ENV,
        CRASH_RUN_TOKEN_ENV,
        CRASH_INCIDENT_ROOT_ENV,
        CRASH_EXIT_INTENT_PATH_ENV,
        CRASH_EXIT_RECEIPT_PATH_ENV,
        CRASHPAD_DATABASE_ENV,
        CRASHPAD_HANDLER_ENV,
        CRASHPAD_CLIENT_LIBRARY_ENV,
    )
    for name in crash_names:
        monkeypatch.setenv(name, f"inherited-{name}")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_UNRELATED", "preserved")
    captured: dict[str, object] = {}

    def _start_detached(command: object, **options: object) -> None:
        """Capture the independent handoff environment."""

        captured["command"] = command
        captured.update(options)

    monkeypatch.setattr(process, "start_detached", _start_detached)

    process.start_detached_handoff(["SugarSubstitute.exe"])

    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["SUGAR_SUBSTITUTE_UNRELATED"] == "preserved"
    assert set(crash_names).isdisjoint(environment)
    assert (
        captured["startup_timeout_seconds"] == process.HANDOFF_STARTUP_TIMEOUT_SECONDS
    )
