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
import os
from pathlib import Path
import tempfile


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "sugarsubstitute_onboarding_automation"
_EXTERNAL_COMFY_ROOT = _ARTIFACT_ROOT / "external-comfy"


@dataclass(frozen=True)
class ScenarioPaths:
    """Capture the key filesystem roots used by one automation scenario."""

    repo_root: Path
    artifact_root: Path
    external_comfy_root: Path


def resolve_scenario_paths() -> ScenarioPaths:
    """Return the deterministic paths shared by onboarding automation work."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    return ScenarioPaths(
        repo_root=_REPO_ROOT,
        artifact_root=_ARTIFACT_ROOT,
        external_comfy_root=_EXTERNAL_COMFY_ROOT,
    )
