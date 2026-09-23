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
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, cast

import pytest

from launcher.sugarsubstitute_launcher import (
    application_launch,
    installed_application_supervisor,
    installed_app_handoff,
)
from launcher.sugarsubstitute_launcher.application_release_selection import (
    ApplicationReleaseSelection,
)
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

    def bind_startup_presenter(self, presenter: object) -> None:
        """Accept presentation registration at the broker boundary."""

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


def test_root_refresh_handoff_precedes_app_update_and_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A selected launcher must relinquish ownership before root replacement."""

    layout = _layout(tmp_path)
    expected_root = layout.root
    closed: list[bool] = []

    class _Refresh:
        """Report a required root replacement at the handoff boundary."""

        def start_if_required(self, *, layout: InstallLayout) -> bool:
            """Require refresh before the app update orchestrator starts."""

            assert layout.root == expected_root
            return True

    class _Splash:
        """Record release of the current launcher's visible splash."""

        def close(self) -> None:
            """Record that the selected launcher relinquished presentation."""

            closed.append(True)

    monkeypatch.setattr(installed_app_handoff, "LauncherBaselineRefresh", _Refresh)
    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        lambda: pytest.fail("App update ran before required root refresh."),
    )

    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=_Broker(),  # type: ignore[arg-type]
        locale_argument="--locale=en",
        no_update_check=False,
        splash_session=cast(Any, _Splash()),
        handoff_geometry=None,
    )

    assert closed == [True]


def test_application_child_environment_replaces_legacy_release_paths(
    tmp_path: Path,
) -> None:
    """Bind Python startup to the selected generation after a launcher handoff."""

    layout = _layout(tmp_path)
    generation = "a" * 32
    selection = ApplicationReleaseSelection(layout.root)
    release_root = selection.prepare(generation=generation, version="2.0.0")
    candidate_app = release_root / "app"
    candidate_package = candidate_app / "fixture_package"
    candidate_package.mkdir(parents=True)
    (candidate_app / "sitecustomize.py").write_text(
        "import fixture_package\n", encoding="utf-8"
    )
    (candidate_package / "__init__.py").write_text("", encoding="utf-8")
    (candidate_package / "candidate_only.py").write_text("", encoding="utf-8")
    (release_root / "runtime").mkdir()
    selection.activate(generation=generation)
    legacy_app = layout.root / "app"
    legacy_package = legacy_app / "fixture_package"
    legacy_package.mkdir(parents=True)
    (legacy_app / "sitecustomize.py").write_text(
        "import fixture_package\n", encoding="utf-8"
    )
    (legacy_package / "__init__.py").write_text("", encoding="utf-8")

    environment = application_launch.installed_application_environment(
        _Broker(),  # type: ignore[arg-type]
        layout=layout,
        remote_failure_reason=None,
        environment={"PYTHONPATH": str(legacy_app)},
    )

    assert environment["PYTHONPATH"] == str(release_root / "app")
    assert environment["VIRTUAL_ENV"] == str(release_root / "runtime" / ".venv")
    assert environment["PYTHONPATH"] != str(legacy_app)
    import_probe = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import fixture_package.candidate_only"],
        cwd=layout.root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60.0,
    )
    assert import_probe.returncode == 0, import_probe.stderr


def test_normal_handoff_supervises_restarts_with_the_same_broker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A child restart should create another child, never another launcher."""

    monkeypatch.setattr(
        installed_application_supervisor,
        "start_launcher_splash_session",
        lambda **_: None,
    )
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

        def __init__(self, **kwargs: object) -> None:
            """Accept the startup cancellation policy at the process boundary."""

        def supervise(self, **kwargs: object) -> int:
            """Capture the authenticated environment."""

            environment = kwargs["environment"]
            assert isinstance(environment, Mapping)
            environments.append(dict(environment))
            return 0

    monkeypatch.setattr(installed_app_handoff, "LauncherUpdateOrchestrator", _NoUpdate)
    monkeypatch.setattr(
        installed_application_supervisor, "ApplicationLifecycleSupervisor", _Supervisor
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

    monkeypatch.setattr(
        installed_application_supervisor,
        "start_launcher_splash_session",
        lambda **_: None,
    )
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
                connectivity_failure=True,
            )

    class _Supervisor:
        """Capture the single degraded child environment."""

        def __init__(self, **kwargs: object) -> None:
            """Accept the startup cancellation policy at the process boundary."""

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
        installed_application_supervisor, "ApplicationLifecycleSupervisor", _Supervisor
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


@pytest.mark.parametrize("schedule_failure", [False, True])
def test_launcher_update_handoff_preserves_app_until_helper_starts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    schedule_failure: bool,
) -> None:
    """Transfer ownership only after helper creation; otherwise retain the app."""

    monkeypatch.setattr(
        installed_application_supervisor,
        "start_launcher_splash_session",
        lambda **_: None,
    )
    layout = _layout(tmp_path)
    closed: list[bool] = []
    scheduled: list[dict[str, object]] = []
    splash = SimpleNamespace(
        client=SimpleNamespace(close=lambda: closed.append(True)),
        app_arguments=(),
        close=lambda: closed.append(True),
    )

    class _LauncherUpdate:
        """Return one staged launcher replacement request."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Stop app handoff at the stable launcher replacement boundary."""

            return PreLaunchUpdateResult(
                checked_manifest=True,
                installed_update=True,
                launcher_update_request_path=str(
                    (layout.launcher_dir / "updates" / "fixture-request.json")
                ),
            )

    monkeypatch.setattr(
        installed_app_handoff,
        "LauncherUpdateOrchestrator",
        _LauncherUpdate,
    )

    def schedule(**kwargs: object) -> int:
        """Inject an OS launch denial before any updater owns the installation."""
        scheduled.append(kwargs)
        if schedule_failure:
            raise PermissionError("The operating system denied helper creation")
        return 42

    continued: list[bool] = []

    class InstalledSupervisor:
        """Observe the installed application boundary after optional update failure."""

        def __init__(self, **kwargs: object) -> None:
            """Retain failure attribution for normal application startup."""
            assert kwargs["remote_failure_reason"] is None

        def supervise(self, **kwargs: object) -> None:
            """Require the original splash to remain usable for normal startup."""
            assert schedule_failure
            assert kwargs["splash_session"] is splash
            assert closed == []
            continued.append(True)

    monkeypatch.setattr(installed_app_handoff, "schedule_launcher_update", schedule)
    monkeypatch.setattr(
        installed_app_handoff, "InstalledApplicationSupervisor", InstalledSupervisor
    )

    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=_Broker(),  # type: ignore[arg-type]
        locale_argument="--locale=en",
        no_update_check=False,
        splash_session=cast(Any, splash),
        handoff_geometry=None,
    )

    assert closed == ([] if schedule_failure else [True])
    assert continued == ([True] if schedule_failure else [])
    assert scheduled[0]["request_path"] == (
        layout.launcher_dir / "updates" / "fixture-request.json"
    )
