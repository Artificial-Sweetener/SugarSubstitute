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

"""Tests for launcher-created shared splash session handoff."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from typing import Any, cast

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import (
    append_splash_session_args,
    start_launcher_splash_session,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)


def test_launcher_splash_session_starts_host_and_returns_app_args(
    tmp_path: Path,
) -> None:
    """The launcher should execute the app-payload host and parse its session spec."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    calls: list[dict[str, Any]] = []
    ready = {
        "type": "ready",
        "endpoint": "127.0.0.1:49152",
        "token": "x" * 32,
        "host_pid": 1234,
    }

    def _fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        """Record host process creation and return a ready fake process."""

        calls.append({"command": command, **kwargs})
        return _FakeProcess(stdout=json.dumps(ready) + "\n")

    session = start_launcher_splash_session(
        layout=layout,
        locale_identifier="ja",
        popen=cast(Any, _fake_popen),
    )

    assert session is not None
    assert session.host_pid == 1234
    assert session.app_arguments == (
        "--splash-session-endpoint=127.0.0.1:49152",
        f"--splash-session-token={'x' * 32}",
        "--splash-session-host-pid=1234",
    )
    assert calls[0]["command"] == [
        subprocess_path(layout.runtime_python),
        "-m",
        "substitute.app.bootstrap.shared_splash_host",
        "--locale=ja",
    ]
    assert calls[0]["cwd"] == subprocess_working_directory(layout.root)
    assert calls[0]["env"]["PYTHONPATH"] == subprocess_path(layout.app_dir)


def test_launcher_splash_session_returns_none_for_invalid_ready_payload(
    tmp_path: Path,
) -> None:
    """Malformed host output should leave app startup on its direct-splash fallback."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    def _fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        """Return invalid stdout while accepting the host command."""

        _ = command
        _ = kwargs
        return _FakeProcess(stdout='{"type":"not-ready"}\n')

    assert (
        start_launcher_splash_session(
            layout=layout,
            locale_identifier="en",
            popen=cast(Any, _fake_popen),
        )
        is None
    )


def test_append_splash_session_args_preserves_command_without_session() -> None:
    """Launch command construction should stay unchanged when no session exists."""

    assert append_splash_session_args(["python", "main.py"], None) == [
        "python",
        "main.py",
    ]


class _FakeProcess:
    """Provide the subset of `Popen[str]` used by splash session startup tests."""

    def __init__(self, *, stdout: str) -> None:
        """Create fake text pipes."""

        self.stdout = StringIO(stdout)
        self.stderr = StringIO("")
