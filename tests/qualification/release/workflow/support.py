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
from typing import cast

import yaml  # type: ignore[import-untyped]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_ROOT = PROJECT_ROOT / ".github" / "workflows"
ACTION_ROOT = PROJECT_ROOT / ".github" / "actions"
EXPECTED_ACTIONS = frozenset(
    {
        "actions/checkout",
        "actions/cache",
        "actions/cache/restore",
        "actions/dependency-review-action",
        "actions/download-artifact",
        "actions/setup-node",
        "actions/setup-python",
        "actions/upload-artifact",
    }
)
WORKFLOW_PATHS = tuple(WORKFLOW_ROOT.glob("*.yml"))
ACTION_PATHS = tuple(ACTION_ROOT.glob("*/action.yml"))
DOCUMENTATION_PATH_FILTER = ["**/*.md"]
TRUSTED_CACHE_EVENTS = ("push", "workflow_dispatch", "repository_dispatch", "schedule")


def workflow_path(name: str) -> Path:
    """Return one workflow owner's repository path."""

    return WORKFLOW_ROOT / name


def action_path(name: str) -> Path:
    """Return one local action owner's metadata path."""

    return ACTION_ROOT / name / "action.yml"


def load_action(name: str) -> dict[str, object]:
    """Load one local composite-action owner."""

    return cast(
        dict[str, object],
        yaml.safe_load(action_path(name).read_text(encoding="utf-8")),
    )


def action_steps(action: dict[str, object]) -> list[dict[str, object]]:
    """Return typed steps from one composite-action owner."""

    runs = action["runs"]
    assert isinstance(runs, dict)
    steps = runs["steps"]
    assert isinstance(steps, list)
    return steps


def action_step(action: dict[str, object], name: str) -> dict[str, object]:
    """Return one exact named step from a composite-action owner."""

    return next(step for step in action_steps(action) if step["name"] == name)


def workflow_consumers(action_reference: str) -> set[str]:
    """Return workflow owners delegating to one local action."""

    return {
        path.name
        for path in WORKFLOW_PATHS
        if action_reference in path.read_text(encoding="utf-8")
    }


def assert_trusted_cache_policy(
    action: dict[str, object],
    trusted_step_name: str,
    untrusted_step_name: str,
) -> None:
    """Require allowlisted writes and restore-only untrusted cache access."""

    trusted = action_step(action, trusted_step_name)
    untrusted = action_step(action, untrusted_step_name)
    trusted_if = str(trusted["if"])
    untrusted_if = str(untrusted["if"])

    assert trusted["uses"] == ("actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae")
    assert untrusted["uses"] == (
        "actions/cache/restore@27d5ce7f107fe9357f9df03efb73ab90386fccae"
    )
    for event in TRUSTED_CACHE_EVENTS:
        assert f"github.event_name == '{event}'" in trusted_if
        assert f"github.event_name != '{event}'" in untrusted_if
    assert "pull_request" not in trusted_if


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
