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

"""Protect automated dependency maintenance and vulnerability gates."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_REVIEW_REVISION = "a1d282b36b6f3519aa1f3fc636f609c47dddb294"


def test_dependabot_maintains_every_repository_dependency_ecosystem() -> None:
    """Keep routine update pull requests comprehensive and predictably grouped."""

    configuration = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    updates = {
        update["package-ecosystem"]: update for update in configuration["updates"]
    }

    assert configuration["version"] == 2
    assert updates.keys() == {"pip", "npm", "github-actions"}
    assert {update["directory"] for update in updates.values()} == {"/"}
    assert {update["schedule"]["interval"] for update in updates.values()} == {"weekly"}
    assert {update["schedule"]["timezone"] for update in updates.values()} == {
        "America/New_York"
    }
    assert {update["schedule"]["day"] for update in updates.values()} == {
        "monday",
        "tuesday",
        "wednesday",
    }
    for update in updates.values():
        assert update["open-pull-requests-limit"] == 5
        [group] = update["groups"].values()
        assert group == {
            "patterns": ["*"],
            "update-types": ["minor", "patch"],
        }


def test_authoritative_ci_blocks_known_dependency_vulnerabilities() -> None:
    """Audit resolved platform graphs and release tooling before tests can pass."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    quality_script = _job_script(workflow["jobs"]["quality"])
    platform_script = _job_script(workflow["jobs"]["platform-tests"])

    assert "npm audit --audit-level=high" in quality_script
    assert "-m pip_audit" in platform_script
    assert "--local --strict --progress-spinner off" in platform_script
    assert workflow["env"]["PIP_AUDIT_IGNORED_VULNERABILITY"] == "CVE-2026-24049"
    assert "--ignore-vuln ${{ env.PIP_AUDIT_IGNORED_VULNERABILITY }}" in platform_script


def test_python_audit_exception_remains_tied_to_photoshop_constraint() -> None:
    """Retain the reviewed wheel exception only while Photoshop forces that version."""

    runtime_requirements = (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    )
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )

    assert "PIP_AUDIT_IGNORED_VULNERABILITY: CVE-2026-24049" in workflow
    assert 'photoshop==0.21.9; sys_platform == "win32"' in runtime_requirements
    assert "requires wheel<0.42" in workflow
    assert "never invokes the affected" in workflow


def test_dependency_review_rejects_new_moderate_vulnerabilities() -> None:
    """Review dependency changes with an immutable official action revision."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    job = workflow["jobs"]["dependency-review"]
    action_step = next(
        step
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/dependency-review-action@")
    )

    assert job["if"] == "github.event_name == 'pull_request'"
    assert action_step["uses"] == (
        f"actions/dependency-review-action@{DEPENDENCY_REVIEW_REVISION}"
    )
    assert action_step["with"]["fail-on-severity"] == "moderate"


def test_dependency_audits_run_without_repository_changes() -> None:
    """Schedule the complete authoritative suite to catch newly disclosed risks."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )

    assert workflow[True]["schedule"] == [{"cron": "17 13 * * 1"}]


def test_dependabot_pull_requests_run_one_authoritative_suite() -> None:
    """Avoid duplicate push and pull-request matrices for bot branches."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )

    assert workflow[True]["push"]["branches-ignore"] == ["main", "dependabot/**"]


def _job_script(job: dict[str, object]) -> str:
    """Combine one workflow job's command steps for policy assertions."""

    steps = job.get("steps")
    if not isinstance(steps, list):
        return ""
    return "\n".join(
        str(step.get("run", "")) for step in steps if isinstance(step, dict)
    )
