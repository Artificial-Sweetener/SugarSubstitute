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

"""Verify readiness policy for one normal installed-application lifetime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher import application_lifecycle_supervisor
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


def test_normal_lifecycle_accepts_every_painted_primary_application_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal launch must supervise main, setup, and repair application routes."""

    captured_surfaces: list[frozenset[ApplicationReadinessSurface]] = []

    class _ReadinessSupervisor:
        """Capture normal-lifecycle readiness construction."""

        def __init__(
            self,
            *,
            accepted_surfaces: tuple[ApplicationReadinessSurface, ...],
            cancellation_requested: object = None,
        ) -> None:
            """Record the accepted painted surfaces."""

            captured_surfaces.append(frozenset(accepted_surfaces))

    class _CrashSupervisor:
        """Stand in for unrelated crash supervision construction."""

    monkeypatch.setattr(
        application_lifecycle_supervisor,
        "ApplicationReadinessSupervisor",
        _ReadinessSupervisor,
    )
    monkeypatch.setattr(
        application_lifecycle_supervisor,
        "ApplicationCrashSupervisor",
        _CrashSupervisor,
    )

    application_lifecycle_supervisor.ApplicationLifecycleSupervisor()

    assert captured_surfaces == [
        frozenset(
            {
                ApplicationReadinessSurface.MAIN_SHELL,
                ApplicationReadinessSurface.ONBOARDING,
            }
        )
    ]


def test_pre_readiness_failure_defers_report_to_single_recovery_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Record startup failure without racing a crash dialog against repair UI."""

    terminated_process = cast(CandidateProcess, object())

    class _ReadinessSupervisor:
        """Fail deterministically before a painted surface exists."""

        def __init__(self, **_arguments: object) -> None:
            """Accept the production readiness policy."""

        def launch_until_ready(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
        ) -> object:
            """Raise the startup failure carrying its terminated process."""

            del layout, command, environment
            raise ApplicationReadinessError(
                "candidate failed",
                terminated_process=terminated_process,
            )

    class _CrashSupervisor:
        """Record whether crash presentation was requested."""

        def __init__(self) -> None:
            """Initialize deterministic calls."""

            self.calls: list[bool] = []

        def prepare(
            self,
            *,
            layout: InstallLayout,
            environment: Mapping[str, str],
        ) -> object:
            """Return an opaque prepared crash contract."""

            del layout, environment
            return SimpleNamespace(
                environment={},
                context=SimpleNamespace(run_id="startup-incident"),
            )

        def supervise_process(
            self,
            *,
            layout: InstallLayout,
            process: object,
            prepared: object,
            present_report: bool = True,
        ) -> int:
            """Capture the presentation policy applied to the failure."""

            del layout, process, prepared
            self.calls.append(present_report)
            return 1

    monkeypatch.setattr(
        application_lifecycle_supervisor,
        "ApplicationReadinessSupervisor",
        _ReadinessSupervisor,
    )
    crash = _CrashSupervisor()
    lifecycle = application_lifecycle_supervisor.ApplicationLifecycleSupervisor(
        crash_supervisor=crash,  # type: ignore[arg-type]
    )

    with pytest.raises(ApplicationReadinessError, match="candidate failed") as raised:
        lifecycle.supervise(
            layout=InstallLayout.from_root(tmp_path / "install"),
            command=("application.exe",),
            environment={},
        )

    assert crash.calls == [False]
    assert raised.value.incident_id == "startup-incident"
