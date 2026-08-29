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

"""Verify update decisions at the launcher-to-application handoff boundary."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY

import pytest

from launcher.sugarsubstitute_launcher import app as launcher_app
from launcher.sugarsubstitute_launcher import installed_app_handoff
from launcher.sugarsubstitute_launcher import splash_session as splash_session_module
from launcher.sugarsubstitute_launcher.application_launch import (
    InstalledApplicationLaunchSession,
)
from launcher.sugarsubstitute_launcher.config import (
    DEFAULT_RELEASE_MANIFEST_URL,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import GitHubReleaseSource
from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
)
from sugarsubstitute_shared.application_runtime_mode import (
    APPLICATION_RUNTIME_MODE_ENV,
    PACKAGED_APPLICATION_RUNTIME_MODE,
)
from sugarsubstitute_shared.startup_remote_access import (
    STARTUP_REMOTE_DEGRADED_ENV,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from tests.launcher.support import write_launcher_executable


@pytest.mark.parametrize(
    ("failure_reason", "expected_degraded_value"),
    [(None, None), ("URLError", "1")],
)
def test_launcher_main_runs_pre_launch_update_before_app_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_reason: str | None,
    expected_degraded_value: str | None,
) -> None:
    """Installed launches should hand update degradation to the app child."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    calls: list[str] = []
    child_environments: list[dict[str, str]] = []
    progress_client = object()
    splash_session = SimpleNamespace(
        client=progress_client,
        app_arguments=("--splash-session-endpoint=127.0.0.1:49152",),
    )

    def record_app_start(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
    ) -> None:
        """Record launch ordering and the app child's private environment."""

        calls.extend(["launch", *command])
        child_environments.append(dict(environment))

    class _FakeUpdateOrchestrator:
        """Record pre-launch update orchestration."""

        def run(self, **kwargs: object) -> object:
            """Record update arguments before app launch."""

            calls.append("update")
            assert kwargs["layout"] == layout
            assert isinstance(kwargs["config"], LauncherConfig)
            assert isinstance(kwargs["release_source"], GitHubReleaseSource)
            assert kwargs["release_source"].manifest_url == DEFAULT_RELEASE_MANIFEST_URL
            assert kwargs["release_source"].timeout_seconds == 3.0
            assert kwargs["no_update_check"] is False
            assert kwargs["progress"] is progress_client
            from launcher.sugarsubstitute_launcher.update_orchestrator import (
                PreLaunchUpdateResult,
            )

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                failure_reason=failure_reason,
            )

    def record_splash_start(**_kwargs: object) -> object:
        """Record that visibility precedes logging, updates, and app handoff."""

        calls.append("splash")
        return splash_session

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setenv(STARTUP_REMOTE_DEGRADED_ENV, "1")
    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        _FakeUpdateOrchestrator,
    )
    monkeypatch.setattr(
        splash_session_module,
        "start_launcher_splash_session",
        record_splash_start,
    )
    monkeypatch.setattr(
        launcher_app,
        "_configure_normal_logging",
        lambda _startup_plan: calls.append("logging"),
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "start_detached",
        record_app_start,
    )
    monkeypatch.setattr(
        InstalledApplicationLaunchSession,
        "wait_for_application_owner",
        lambda self: True,
    )
    monkeypatch.setattr(
        launcher_app,
        "LauncherMainWindow",
        lambda **_kwargs: pytest.fail("Installed launch must not show setup UI."),
    )

    assert launcher_app.main([]) == 0
    assert calls == [
        "splash",
        "logging",
        "update",
        "launch",
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        "--locale=en",
        "--splash-session-endpoint=127.0.0.1:49152",
    ]
    assert len(child_environments) == 1
    assert APPLICATION_LAUNCH_TOKEN_ENV in child_environments[0]
    assert (
        child_environments[0][APPLICATION_RUNTIME_MODE_ENV]
        == PACKAGED_APPLICATION_RUNTIME_MODE
    )
    assert (
        child_environments[0].get(STARTUP_REMOTE_DEGRADED_ENV)
        == expected_degraded_value
    )


def test_launcher_main_hands_off_pending_launcher_update_instead_of_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A staged launcher update should replace, relaunch, then start the app."""

    from launcher.sugarsubstitute_launcher.update_orchestrator import (
        PreLaunchUpdateResult,
    )

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    write_launcher_executable(layout)
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_text("", encoding="utf-8")
    closed: list[bool] = []
    splash_session = SimpleNamespace(
        client=SimpleNamespace(close=lambda: closed.append(True)),
        app_arguments=(),
    )
    scheduled: list[dict[str, object]] = []

    def schedule_update(**kwargs: object) -> int:
        """Record the detached launcher update handoff."""

        scheduled.append(kwargs)
        return 1234

    class _FakeUpdateOrchestrator:
        """Return one pending launcher request."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Return the staged update result."""

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=True,
                launcher_update_request_path=str(layout.launcher_update_request_path),
            )

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        _FakeUpdateOrchestrator,
    )
    monkeypatch.setattr(
        splash_session_module,
        "start_launcher_splash_session",
        lambda *, layout, locale_identifier: splash_session,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "schedule_launcher_update",
        schedule_update,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "start_detached",
        lambda _command: pytest.fail("The old launcher must not start the app."),
    )

    assert launcher_app.main([]) == 0
    assert closed == [True]
    assert scheduled == [
        {
            "request_path": layout.launcher_update_request_path,
            "runtime_python": layout.runtime_python,
            "app_dir": layout.app_dir,
            "relaunch": True,
            "wait_pid": ANY,
        }
    ]
