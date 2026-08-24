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

"""Provide shared repository access for release workflow qualification contracts."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_ROOT = PROJECT_ROOT / ".github" / "workflows"
EXPECTED_ACTIONS = frozenset(
    {
        "actions/checkout",
        "actions/cache",
        "actions/dependency-review-action",
        "actions/download-artifact",
        "actions/setup-node",
        "actions/setup-python",
        "actions/upload-artifact",
    }
)
WORKFLOW_PATHS = tuple(WORKFLOW_ROOT.glob("*.yml"))
DOCUMENTATION_PATH_FILTER = ["**/*.md"]


def workflow_path(name: str) -> Path:
    """Return one workflow owner's repository path."""

    return WORKFLOW_ROOT / name


def workflow_text(*names: str) -> str:
    """Combine exact workflow owners participating in one tested contract."""

    return "\n".join(workflow_path(name).read_text(encoding="utf-8") for name in names)


def job_script(job: dict[str, object]) -> str:
    """Combine one workflow job's run scripts for contract assertions."""

    steps = job.get("steps")
    if not isinstance(steps, list):
        return ""
    return "\n".join(
        str(step.get("run", "")) for step in steps if isinstance(step, dict)
    )
