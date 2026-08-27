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

"""Protect platform-correct filesystem readiness checks."""

from __future__ import annotations

from pathlib import Path

import pytest

import substitute.infrastructure.onboarding.readiness_checks as readiness_checks
from substitute.infrastructure.onboarding.readiness_checks import (
    FileSystemReadinessChecks,
)


def test_managed_workspace_readiness_uses_canonical_python_path_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Readiness must not reproduce a Windows-only managed Python path."""

    workspace = tmp_path / "comfyui"
    canonical_python = workspace / ".venv" / "canonical" / "python"
    monkeypatch.setattr(
        readiness_checks,
        "workspace_python_path",
        lambda _workspace: canonical_python,
        raising=False,
    )
    canonical_python.parent.mkdir(parents=True)
    canonical_python.write_text("python", encoding="utf-8")
    (workspace / "main.py").write_text("main", encoding="utf-8")

    checks = FileSystemReadinessChecks()

    assert checks.managed_workspace_python_path(workspace) == canonical_python
    assert checks.is_managed_workspace_installed(workspace)
    assert checks.is_managed_workspace_launchable(workspace)
