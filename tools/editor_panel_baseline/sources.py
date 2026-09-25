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

"""Validate and identify Base-Cubes sources used by editor baselines."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from tools.editor_projection_rig.fixtures import read_json, workflow_fixture_path
from tools.editor_projection_rig.scenarios import WorkflowScenario

_BASE_CUBE_ID_PREFIX = "Artificial-Sweetener/Base-Cubes/"


def validate_base_cube_sources(
    *,
    scenarios: Sequence[WorkflowScenario],
    fixtures_dir: Path,
    base_cubes_dir: Path,
) -> list[dict[str, Any]]:
    """Prove every captured cube matches the requested local Base-Cubes file."""

    if not base_cubes_dir.is_dir():
        raise FileNotFoundError(f"Base-Cubes checkout is missing: {base_cubes_dir}")
    records: list[dict[str, Any]] = []
    for scenario in scenarios:
        fixture = read_json(workflow_fixture_path(fixtures_dir, scenario.workflow_id))
        cubes = fixture.get("cubes")
        if not isinstance(cubes, list):
            raise ValueError(f"Fixture {scenario.workflow_id} has no cube list.")
        for cube in cubes:
            if not isinstance(cube, Mapping):
                raise ValueError(f"Fixture {scenario.workflow_id} has an invalid cube.")
            cube_id = str(cube.get("cube_id", ""))
            if not cube_id.startswith(_BASE_CUBE_ID_PREFIX):
                raise ValueError(f"Fixture cube is not from Base-Cubes: {cube_id!r}.")
            relative = PurePosixPath(cube_id.removeprefix(_BASE_CUBE_ID_PREFIX))
            source = base_cubes_dir.joinpath(*relative.parts)
            source_payload = json.loads(source.read_text(encoding="utf-8"))
            source_version = str(source_payload.get("version", ""))
            fixture_version = str(cube.get("version", ""))
            if (
                source_payload.get("cube_id") != cube_id
                or source_version != fixture_version
            ):
                raise ValueError(
                    f"Fixture/source mismatch for {cube_id}: "
                    f"fixture={fixture_version!r}, source={source_version!r}."
                )
            records.append(
                {
                    "scenario_id": scenario.workflow_id,
                    "cube_id": cube_id,
                    "version": fixture_version,
                    "path": str(source.resolve()),
                    "sha256": sha256(source),
                }
            )
    return records


def sha256(path: Path) -> str:
    """Return a prefixed SHA-256 digest for one file."""

    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def git_output(directory: Path, *arguments: str) -> str:
    """Return normalized output from a read-only Git query."""

    completed = subprocess.run(
        ["git", "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
