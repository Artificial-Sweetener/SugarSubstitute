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

"""Keep bootstrap readiness aligned with the managed hydration transaction."""

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.standalone_environment.hydration_state import (
    StandaloneHydrationState,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    FileSystemReadinessChecks,
)


@pytest.mark.parametrize("phase", ["legacy", "hydrating", "complete"])
def test_bootstrap_only_accepts_completed_or_legacy_environments(
    tmp_path: Path, phase: str
) -> None:
    """A visible interpreter cannot bypass the installer-owned completion boundary."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True)
    python_path.write_bytes(b"test interpreter")
    (tmp_path / "main.py").write_text("# Comfy", encoding="utf-8")
    state = StandaloneHydrationState(tmp_path)
    if phase != "legacy":
        state.begin()
    if phase == "complete":
        state.complete()

    checks = FileSystemReadinessChecks()

    assert checks.managed_workspace_python_path(tmp_path) == python_path
    assert checks.is_managed_workspace_installed(tmp_path) is (phase != "hydrating")
    assert checks.is_managed_workspace_launchable(tmp_path) is (phase != "hydrating")
