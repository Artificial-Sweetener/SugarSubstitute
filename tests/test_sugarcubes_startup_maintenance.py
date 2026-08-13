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

"""Verify that SugarCubes maintenance can degrade without blocking startup."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
)
from substitute.infrastructure.comfy import sugarcubes_startup_maintenance
from sugarsubstitute_shared.startup_remote_access import StartupConnectivityError


def test_successful_startup_maintenance_returns_the_strict_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Successful preparation must retain the strict runner's result."""

    expected = SugarCubesMaintenanceResult(0, {}, (), ())
    monkeypatch.setattr(
        sugarcubes_startup_maintenance,
        "run_sugarcubes_baseline_maintenance",
        lambda *_args, **_kwargs: expected,
    )

    assert (
        sugarcubes_startup_maintenance.attempt_sugarcubes_startup_maintenance(tmp_path)
        is expected
    )


def test_failed_startup_maintenance_reports_degradation_and_returns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Any maintenance failure must remain visible without refusing startup."""

    def fail_maintenance(*_args: object, **_kwargs: object) -> None:
        """Simulate a multi-line repository or dependency failure."""

        raise RuntimeError("local checkout is ahead\nand must be preserved")

    monkeypatch.setattr(
        sugarcubes_startup_maintenance,
        "run_sugarcubes_baseline_maintenance",
        fail_maintenance,
    )
    emitted: list[str] = []

    result = sugarcubes_startup_maintenance.attempt_sugarcubes_startup_maintenance(
        tmp_path,
        on_log=emitted.append,
    )

    assert result is None
    assert emitted == [
        "ERROR: SugarCubes[sugarcubes_maintenance_failed]: "
        "SugarCubes startup maintenance failed: local checkout is ahead and "
        "must be preserved ComfyUI will continue starting."
    ]


def test_connectivity_failure_reaches_the_launch_scoped_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SugarCubes must expose connectivity loss to the shared sticky decision."""

    def fail_connectivity(*_args: object, **_kwargs: object) -> None:
        """Represent one typed remote-access failure."""

        raise StartupConnectivityError("repository fetch unavailable")

    monkeypatch.setattr(
        sugarcubes_startup_maintenance,
        "run_sugarcubes_baseline_maintenance",
        fail_connectivity,
    )

    with pytest.raises(StartupConnectivityError):
        sugarcubes_startup_maintenance.attempt_sugarcubes_startup_maintenance(tmp_path)
