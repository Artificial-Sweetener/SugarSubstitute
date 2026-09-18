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

"""Verify repair execution retires only its retained attempt request."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout

import pytest
from sugarsubstitute_shared.installation_mutation import InstallationMutationOwnership

from launcher.sugarsubstitute_launcher.application.repair.execution_result import (
    CompletedRepair,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher import repair_helper


def test_helper_keeps_another_prepared_attempt_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Follow the retained request through real loading and retirement, without UI."""
    root = tmp_path.resolve()
    first_id, second_id = "a" * 32, "b" * 32
    staging = root / ".repair/staging/1.2.3" / first_id
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
        preparation_id=first_id,
    )
    second_staging = staging.parent / second_id
    second = replace(
        request,
        preparation_id=second_id,
        staged_app_dir=second_staging / "app",
        staged_launcher_dir=second_staging / "launcher",
    )
    request.save(request.request_path)
    second.save(second.request_path)
    second_bytes = second.request_path.read_bytes()
    executed: list[PreparedRepairRequest] = []
    recovered: list[Path] = []

    class Executor:
        """Replace the filesystem mutation boundary while retaining request routing."""

        def execute_application(
            self,
            candidate: PreparedRepairRequest,
            *,
            mutation: InstallationMutationOwnership,
        ) -> CompletedRepair:
            """Verify the original request reaches the mutation owner."""
            assert recovered == [root]
            executed.append(candidate)
            return CompletedRepair("1.2.3", root / ".repair/quarantine/fixture", False)

    def build(**_options: object) -> Executor:
        """Keep this request-routing test out of installation mutation."""
        return Executor()

    class Recovery:
        """Record recovery at the installation orchestration boundary."""

        def __init__(self, layout: InstallLayout) -> None:
            """Retain the exact installation selected by the request worker."""
            self.root = layout.root

        def recover(
            self, *, ownership: InstallationMutationOwnership | None = None
        ) -> bool:
            """Observe admission to mutation before the request executor runs."""
            recovered.append(self.root)
            return False

    monkeypatch.setattr(repair_helper, "InstallationRecovery", Recovery)
    monkeypatch.setattr(repair_helper, "build_repair_execution_service", build)
    result = repair_helper.run_prepared_repair(request.request_path)
    assert result.version == request.version
    assert executed == [request]
    assert not request.request_path.exists()
    assert second.request_path.read_bytes() == second_bytes
