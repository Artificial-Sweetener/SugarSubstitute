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

import json
from pathlib import Path
import re

import pytest
import yaml  # type: ignore[import-untyped]

from tests.support.execution.node_runtime import run_node


PROJECT_ROOT = Path(__file__).resolve().parents[4]


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

    quality_workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "quality-gates.yml").read_text(
            encoding="utf-8"
        )
    )
    platform_workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "platform-tests.yml").read_text(
            encoding="utf-8"
        )
    )
    quality_script = _job_script(quality_workflow["jobs"]["quality"])
    platform_script = _job_script(platform_workflow["jobs"]["platform-tests"])

    assert "npm run audit:release" in quality_script
    release_audit_script = PROJECT_ROOT / "scripts" / "audit-release-dependencies.mjs"
    audit_source = release_audit_script.read_text(encoding="utf-8")
    assert '["npm", "audit", "--json"]' in audit_source
    assert '"corepack.cmd" : "corepack"' in audit_source
    assert "ignoredAdvisory" not in audit_source
    assert "unresolvedReleaseFindings(report)" in audit_source
    assert "-m pip_audit" in platform_script
    assert "--local --strict --progress-spinner off" in platform_script
    assert platform_workflow["env"]["PIP_AUDIT_IGNORED_VULNERABILITY"] == (
        "CVE-2026-24049"
    )
    assert "--ignore-vuln ${{ env.PIP_AUDIT_IGNORED_VULNERABILITY }}" in platform_script


@pytest.mark.parametrize(
    ("package_name", "advisory"),
    [
        ("braces", "GHSA-vfj7-8cjw-p6xm"),
        ("http-cache-semantics", "GHSA-ch52-4w7c-c8xp"),
        ("undici", "GHSA-rfgv-xxqx-mfg5"),
    ],
)
def test_release_audit_rejects_vulnerabilities_in_every_dependency_location(
    package_name: str,
    advisory: str,
) -> None:
    """Reject known high findings in bundled, active, and newly added locations."""

    script = """
import { unresolvedReleaseFindings } from './scripts/release-dependency-audit.mjs';
const packageName = process.argv[1];
const finding = {source: 1124334, url: `https://github.com/advisories/${process.argv[2]}`};
const bundle = `node_modules/npm/node_modules/${packageName}`;
const active = `node_modules/${packageName}`;
const results = [[bundle], [bundle, active], [active], [], ['node_modules/unknown']]
 .map(nodes => unresolvedReleaseFindings({auditReportVersion:2, vulnerabilities:{
  [packageName]:{name:packageName, severity:'high', nodes, via:[finding]},
 }}).length);
process.stdout.write(JSON.stringify(results));
"""
    result = run_node(
        ("--input-type=module", "-e", script, package_name, advisory),
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [1, 1, 1, 1, 1]


def test_release_lock_contains_no_vulnerable_release_engines() -> None:
    """Keep the removed vulnerable graph out of reproducible installations."""

    lock = json.loads((PROJECT_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    forbidden = {
        "braces",
        "http-cache-semantics",
        "npm",
        "micromatch",
        "semantic-release",
    }
    assert not {
        name
        for name in lock["packages"]
        if name.rsplit("node_modules/", 1)[-1] in forbidden
    }


@pytest.mark.parametrize(
    "report",
    [
        None,
        {},
        {"error": {"code": "network"}},
        {"auditReportVersion": 2, "vulnerabilities": []},
        {"auditReportVersion": 2, "vulnerabilities": {"unsafe": {"severity": "high"}}},
    ],
)
def test_release_audit_fails_closed_on_missing_or_malformed_evidence(
    report: object,
) -> None:
    """Reject unusable audit output rather than accepting an empty finding set."""

    script = """
import { unresolvedReleaseFindings } from './scripts/release-dependency-audit.mjs';
try { unresolvedReleaseFindings(JSON.parse(process.argv[1])); process.exitCode = 1; }
catch (error) { process.stdout.write(error.message); }
"""
    result = run_node(
        ("--input-type=module", "-e", script, json.dumps(report)), cwd=PROJECT_ROOT
    )
    assert result.returncode == 0, result.stderr
    assert "npm audit" in result.stdout


def test_python_audit_exception_remains_tied_to_photoshop_constraint() -> None:
    """Retain the reviewed wheel exception only while Photoshop forces that version."""

    runtime_requirements = (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    )
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "platform-tests.yml"
    ).read_text(encoding="utf-8")

    assert "PIP_AUDIT_IGNORED_VULNERABILITY: CVE-2026-24049" in workflow
    assert 'photoshop==0.21.9; sys_platform == "win32"' in runtime_requirements
    assert "requires wheel<0.42" in workflow
    assert "never invokes the affected" in workflow


def test_dependency_review_rejects_new_moderate_vulnerabilities() -> None:
    """Review dependency changes with an immutable official action revision."""

    owner = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "dependency-review.yml").read_text(
            encoding="utf-8"
        )
    )
    orchestrator = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    job = owner["jobs"]["dependency-review"]
    action_step = next(
        step
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/dependency-review-action@")
    )

    dependency_call = orchestrator["jobs"]["dependency-review"]
    assert dependency_call["if"] == "github.event_name == 'pull_request'"
    assert dependency_call["uses"] == "./.github/workflows/dependency-review.yml"
    action, revision = action_step["uses"].rsplit("@", maxsplit=1)
    assert action == "actions/dependency-review-action"
    assert re.fullmatch(r"[0-9a-f]{40}", revision)
    assert action_step["with"]["fail-on-severity"] == "moderate"


def test_dependency_audits_run_without_repository_changes() -> None:
    """Schedule the complete authoritative suite to catch newly disclosed risks."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )

    assert workflow[True]["schedule"] == [{"cron": "17 13 * * 1"}]


def test_release_and_dependabot_branches_run_one_authoritative_suite() -> None:
    """Run topic-branch matrices through their pull request only."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )

    assert "push" not in workflow[True]


def _job_script(job: dict[str, object]) -> str:
    """Combine one workflow job's command steps for policy assertions."""

    steps = job.get("steps")
    if not isinstance(steps, list):
        return ""
    return "\n".join(
        str(step.get("run", "")) for step in steps if isinstance(step, dict)
    )
