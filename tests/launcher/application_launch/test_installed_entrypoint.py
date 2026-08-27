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

"""Verify installed launcher entrypoint routing and app handoff."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher import installed_app_handoff
from launcher.sugarsubstitute_launcher import splash_session as splash_session_module
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import GitHubReleaseSource
from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from tests.launcher.support import (
    launcher_test_application,
    write_launcher_executable,
)


def test_launcher_main_repairs_moved_installed_exe_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An adjacent config pointing elsewhere should be repair, not setup mode."""

    _ = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    other_layout = InstallLayout.from_root(tmp_path / "OtherSugarSubstitute")
    LauncherConfig.from_layout(layout=other_layout).save(layout.config_path)
    write_launcher_executable(layout)
    windows: list[dict[str, object]] = []
    manifest_url = "https://localhost:44443/manifest.json"

    class _FakeWindow:
        """Record launcher window construction without showing real UI."""

        def __init__(self, **kwargs: object) -> None:
            """Capture construction keyword arguments."""

            windows.append(kwargs)

        def show(self) -> None:
            """Record that the window would be shown."""

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(launcher_app, "LauncherMainWindow", _FakeWindow)
    assert launcher_app.main(["--manifest-url", manifest_url]) == 0
    assert windows
    assert windows[0]["initial_layout"] == layout
    assert windows[0]["repair"] is True
    assert windows[0]["continue_install"] is False
    initial_release_source = windows[0]["initial_release_source"]
    assert isinstance(initial_release_source, GitHubReleaseSource)
    assert initial_release_source.manifest_url == manifest_url


def test_launcher_main_starts_app_from_installed_exe_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The installed executable should launch the app instead of setup UI."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    layout.launcher_support_path.mkdir(parents=True, exist_ok=True)
    resolved_executable = layout.launcher_support_path / layout.executable_path.name
    resolved_executable.write_text("", encoding="utf-8")
    started_commands: list[list[str]] = []
    started_environments: list[dict[str, str]] = []

    def record_app_start(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
    ) -> None:
        """Record the command and isolated environment passed to the app child."""

        started_commands.append(list(command))
        started_environments.append(dict(environment))

    monkeypatch.setattr(sys, "executable", str(resolved_executable))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        sys,
        "_MEIPASS",
        str(layout.launcher_support_path),
        raising=False,
    )
    monkeypatch.setenv(APPLICATION_LAUNCH_TOKEN_ENV, "inherited-poison-token")
    monkeypatch.setattr(
        splash_session_module,
        "start_launcher_splash_session",
        lambda *, layout, locale_identifier: None,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "start_detached",
        record_app_start,
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert started_commands == [
        [
            subprocess_path(layout.runtime_python),
            subprocess_path(layout.app_entrypoint),
            f"--install-root={subprocess_path(layout.root)}",
            "--locale=en",
        ]
    ]
    assert len(started_environments) == 1
    assert started_environments[0][APPLICATION_LAUNCH_TOKEN_ENV] != (
        "inherited-poison-token"
    )


def test_frozen_launcher_main_uses_invoked_installed_bundle_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A packaged launch should route from argv when runtime paths are unrelated."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    unrelated_bundle = tmp_path / "frozen-runtime"
    unrelated_bundle.mkdir()
    resolved_executable = unrelated_bundle / layout.executable_path.name
    resolved_executable.write_text("", encoding="utf-8")
    started_commands: list[list[str]] = []

    monkeypatch.setattr(sys, "argv", [str(layout.executable_path)])
    monkeypatch.setattr(sys, "executable", str(resolved_executable))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(unrelated_bundle), raising=False)
    monkeypatch.setattr(
        splash_session_module,
        "start_launcher_splash_session",
        lambda *, layout, locale_identifier: None,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "start_detached",
        lambda command, *, environment: started_commands.append(list(command)),
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert started_commands == [
        [
            subprocess_path(layout.runtime_python),
            subprocess_path(layout.app_entrypoint),
            f"--install-root={subprocess_path(layout.root)}",
            "--locale=en",
        ]
    ]
