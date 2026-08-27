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

"""Define stable filesystem locations used by onboarding automation scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ScenarioPaths:
    """Capture the key filesystem roots used by one automation scenario."""

    repo_root: Path
    artifact_root: Path
    sandbox_root: Path
    external_comfy_root: Path


def resolve_scenario_paths(run_root: Path) -> ScenarioPaths:
    """Return isolated automation paths beneath the caller-owned run root."""

    return ScenarioPaths(
        repo_root=_REPO_ROOT,
        artifact_root=run_root,
        sandbox_root=run_root / "sandboxes",
        external_comfy_root=run_root / "external-comfy",
    )
