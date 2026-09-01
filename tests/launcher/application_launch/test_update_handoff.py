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

"""Verify update decisions remain inside the elected supervisor lifetime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from launcher.sugarsubstitute_launcher import installed_app_handoff
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    PreLaunchUpdateResult,
)
from sugarsubstitute_shared.application_runtime_mode import (
    APPLICATION_RUNTIME_MODE_ENV,
    PACKAGED_APPLICATION_RUNTIME_MODE,
)
from sugarsubstitute_shared.startup_remote_access import (
    STARTUP_REMOTE_DEGRADED_ENV,
)


class _Broker:
    """Authorize child environments and expose deterministic restart state."""

    def __init__(self, restarts: Sequence[bool] = ()) -> None:
        """Store the restart decisions consumed after child exits."""

        self._restarts = iter(restarts)

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Mark one environment as authenticated by the supervisor."""

        child = dict(environment)
        child["TEST_INSTANCE_BROKER"] = "connected"
        return child

    def consume_restart_request(self) -> bool:
        """Return the next prepared restart decision."""

        return next(self._restarts, False)


def _layout(tmp_path: Path) -> InstallLayout:
    """Create the configuration needed by installed handoff orchestration."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    return layout


def test_normal_handoff_supervises_restarts_with_the_same_broker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A child restart should create another child, never another launcher."""

    layout = _layout(tmp_path)
    broker = _Broker((True, False))
    environments: list[dict[str, str]] = []

    class _NoUpdate:
        """Skip remote work while retaining normal launch orchestration."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Return a normal no-update result."""

            return PreLaunchUpdateResult(False, False, skipped_reason="disabled")

    class _Supervisor:
        """Record each full child lifetime."""

        def supervise(self, **kwargs: object) -> int:
            """Capture the authenticated environment."""

            environment = kwargs["environment"]
            assert isinstance(environment, Mapping)
            environments.append(dict(environment))
            return 0

    monkeypatch.setattr(installed_app_handoff, "LauncherUpdateOrchestrator", _NoUpdate)
    monkeypatch.setattr(
        installed_app_handoff, "ApplicationCrashSupervisor", _Supervisor
    )

    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=broker,  # type: ignore[arg-type]
        locale_argument="--locale=en",
        no_update_check=True,
        splash_session=None,
        handoff_geometry=None,
    )

    assert len(environments) == 2
    assert all(item["TEST_INSTANCE_BROKER"] == "connected" for item in environments)
    assert all(
        item[APPLICATION_RUNTIME_MODE_ENV] == PACKAGED_APPLICATION_RUNTIME_MODE
        for item in environments
    )


def test_update_failure_state_is_forwarded_without_a_lock_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Carry sticky remote degradation through the broker-owned child channel."""

    layout = _layout(tmp_path)
    captured: list[dict[str, str]] = []

    class _FailedUpdate:
        """Represent a best-effort pre-launch network failure."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Return the degradation reason handed to the child."""

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=False,
                failure_reason="URLError",
            )

    class _Supervisor:
        """Capture the single degraded child environment."""

        def supervise(self, **kwargs: object) -> int:
            """Record the environment and finish the child lifetime."""

            environment = kwargs["environment"]
            assert isinstance(environment, Mapping)
            captured.append(dict(environment))
            return 0

    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        _FailedUpdate,
    )
    monkeypatch.setattr(
        installed_app_handoff, "ApplicationCrashSupervisor", _Supervisor
    )

    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=_Broker(),  # type: ignore[arg-type]
        locale_argument="--locale=en",
        no_update_check=False,
        splash_session=None,
        handoff_geometry=None,
    )

    assert captured[0][STARTUP_REMOTE_DEGRADED_ENV] == "1"


def test_launcher_bundle_update_handoff_does_not_start_the_old_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Let the durable launcher updater replace and relaunch the supervisor."""

    layout = _layout(tmp_path)
    closed: list[bool] = []
    scheduled: list[dict[str, object]] = []
    splash = SimpleNamespace(
        client=SimpleNamespace(close=lambda: closed.append(True)),
        app_arguments=(),
    )

    class _LauncherUpdate:
        """Return one staged launcher replacement request."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Stop app handoff at the stable launcher replacement boundary."""

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=True,
                launcher_update_request_path=str(layout.launcher_update_request_path),
            )

    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        _LauncherUpdate,
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "schedule_launcher_update",
        lambda **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        installed_app_handoff,
        "ApplicationCrashSupervisor",
        lambda: pytest.fail("The replaced launcher must not start the old app."),
    )

    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=_Broker(),  # type: ignore[arg-type]
        locale_argument="--locale=en",
        no_update_check=False,
        splash_session=cast(Any, splash),
        handoff_geometry=None,
    )

    assert closed == [True]
    assert scheduled[0]["request_path"] == layout.launcher_update_request_path
