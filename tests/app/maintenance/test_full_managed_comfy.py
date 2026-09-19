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

"""Require executable runtime evidence before accepting a repaired workspace."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import subprocess

import pytest

from substitute.app.maintenance.full_managed_comfy import (
    FullManagedComfyMaintenanceService,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS


@pytest.mark.parametrize("returncode", [0, 103])
def test_validation_runs_the_interpreter_at_the_promoted_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    """Reject an existing launcher whose former staging interpreter is unavailable."""

    workspace = tmp_path / "promoted"
    workspace.mkdir()
    (workspace / "main.py").write_text("# core", encoding="utf-8")
    (workspace / "manager_requirements.txt").write_text(
        "comfyui-manager", encoding="utf-8"
    )
    (workspace / "comfy").mkdir()
    (workspace / "comfy" / "cli_args.py").write_text(
        "--enable-manager", encoding="utf-8"
    )
    python = workspace_python_path(workspace)
    python.parent.mkdir(parents=True)
    python.write_bytes(b"present interpreter launcher")
    for nodepack in CORE_COMFY_NODEPACKS:
        root = workspace / nodepack.expected_folder
        root.mkdir(parents=True)
        for sentinel in nodepack.sentinel_files:
            path = root / sentinel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("sentinel", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{nodepack.registry_id}"\nversion = "{nodepack.required_version}"\n',
            encoding="utf-8",
        )
        (root / ".tracking").write_text("{}", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def probe(
        args: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Control only the native interpreter process result."""

        assert Path(args[0]).resolve() == python.resolve()
        assert Path(str(kwargs["cwd"])).resolve() == workspace.resolve()
        commands.append(tuple(args))
        return subprocess.CompletedProcess(
            args,
            returncode,
            'SUGARSUBSTITUTE_MANAGER_PROBE={"version":"1.0","supports_pygit2":false}',
            "staging interpreter is missing" if returncode else "",
        )

    monkeypatch.setattr(subprocess, "run", probe)
    if returncode:
        with pytest.raises(RuntimeError, match="staging interpreter is missing"):
            FullManagedComfyMaintenanceService().validate(workspace)
    else:
        FullManagedComfyMaintenanceService().validate(workspace)
    assert commands
