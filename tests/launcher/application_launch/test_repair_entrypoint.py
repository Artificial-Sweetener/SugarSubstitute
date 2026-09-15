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

"""Verify the adjacent repair executable enters the shared launcher route."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.repair_entrypoint import (
    repair_arguments,
    run_repair,
)
from launcher.sugarsubstitute_launcher import __main__ as launcher_bootstrap
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.repair_session_supervisor import (
    RepairSessionSupervisor,
)


def test_repair_arguments_select_repair_once_and_preserve_other_options() -> None:
    """The direct entrypoint should be equivalent to an explicit repair invocation."""

    assert repair_arguments(("--locale", "ja_JP", "--repair")) == (
        "--repair",
        "--locale",
        "ja_JP",
    )


def test_run_repair_delegates_to_normal_launcher_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repair must reuse the launcher's startup, localization, and UI composition."""

    received: list[tuple[str, ...]] = []

    def launcher_main(arguments: Sequence[str]) -> int:
        """Record the direct repair invocation."""

        received.append(tuple(arguments))
        return 17

    monkeypatch.setattr(sys, "argv", ["Repair.exe"])
    result = run_repair(launcher_main)

    assert result == 17
    assert received == [("--repair",)]


def test_run_repair_routes_internal_execution_without_constructing_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The independent helper should bypass the normal graphical launcher route."""

    request_path = tmp_path / "prepared.json"
    normal_calls: list[tuple[str, ...]] = []
    prepared_calls: list[Path] = []

    def normal_runner(arguments: Sequence[str]) -> int:
        """Record any unexpected normal repair launch."""

        normal_calls.append(tuple(arguments))
        return 1

    monkeypatch.setattr(
        sys,
        "argv",
        ["Repair.exe", f"--execute-repair-request={request_path}"],
    )

    result = run_repair(
        normal_runner,
        prepared_runner=lambda path: prepared_calls.append(path),
    )

    assert result == 0
    assert normal_calls == []
    assert prepared_calls == [request_path]


def test_regular_launcher_routes_detached_repair_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every platform's launcher bundle must understand the detached helper route."""
    root = tmp_path / "install"
    staging = root / ".repair/staging/1.2.3"
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
    )
    request_path = root / ".repair/prepared.json"
    request.save(request_path)
    calls: list[str] = []
    monkeypatch.setattr(
        sys, "argv", ["SugarSubstitute", f"--execute-repair-request={request_path}"]
    )

    def supervise(
        self: RepairSessionSupervisor, candidate: PreparedRepairRequest
    ) -> int:
        """Capture the lifecycle boundary without starting a process."""
        calls.append(candidate.version)
        return 7

    monkeypatch.setattr(RepairSessionSupervisor, "run", supervise)

    def reject_normal_launch() -> int:
        """Prove execution does not fall through into the ordinary CLI."""
        pytest.fail("Detached repair entered normal launcher routing")

    assert launcher_bootstrap.run_launcher(reject_normal_launch) == 7
    assert calls == ["1.2.3"]
