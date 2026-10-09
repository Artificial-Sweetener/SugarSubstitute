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

"""Constrain reviewed release-tool exceptions without masking new audit findings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.execution.node_runtime import run_node


PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = """
import { readFileSync } from 'node:fs';
import { unresolvedReleaseFindings } from './scripts/release-dependency-audit.mjs';
const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'));
function direct(name, id, path = `node_modules/${name}`) {
  return { name, severity: 'high', nodes: [path], via: [{
    source: 1240992, name, dependency: name,
    url: `https://github.com/advisories/${id}`, severity: 'high', range: '*',
  }] };
}
const braces = direct('braces', 'GHSA-vfj7-8cjw-p6xm');
const cache = direct('http-cache-semantics', 'GHSA-ch52-4w7c-c8xp',
  'node_modules/npm/node_modules/http-cache-semantics');
const report = {auditReportVersion: 2, vulnerabilities: {
  braces, 'http-cache-semantics': cache,
}};
function audit() {
  try { return unresolvedReleaseFindings(report, lock).map(item => item.name).sort(); }
  catch (error) { return {error: error.message}; }
}
"""


def _evaluate(script: str) -> object:
    """Exercise the real audit owner using inert npm report records."""

    result = run_node(
        ("--input-type=module", "-e", _SCRIPT + script),
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_release_audit_accepts_only_reviewed_advisories_in_locked_tooling() -> None:
    """Accept the two maintainer-reviewed CI risks without claiming they are fixed."""

    assert _evaluate("process.stdout.write(JSON.stringify(audit()));") == []


def test_release_audit_accepts_an_empty_valid_report() -> None:
    """Permit a clean audit without depending on the continued presence of risks."""

    assert (
        _evaluate(
            "report.vulnerabilities = {}; process.stdout.write(JSON.stringify(audit()));"
        )
        == []
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "braces.nodes = ['node_modules/npm/node_modules/braces'];",
        "braces.nodes.push('node_modules/other/node_modules/braces');",
        "lock.packages['node_modules/braces'].version = '3.0.4';",
        "lock.packages['node_modules/braces'].dev = false;",
        "lock.packages['node_modules/npm'].version = '11.21.1';",
        "lock.packages['node_modules/@semantic-release/npm'].version = '13.2.0';",
        "lock.packages[''].dependencies = {braces: '3.0.3'};",
        "lock.packages[''].devDependencies.unreviewed = '1.0.0';",
        "lock.packages[''].devDependencies['semantic-release'] = '25.0.10';",
        "braces.via[0].url = 'https://github.com/advisories/GHSA-2222-3333-4444';",
        "braces.via[0].severity = braces.severity = 'critical';",
        "braces.via.push({...braces.via[0], url: 'https://github.com/advisories/GHSA-2222-3333-4444'});",
        "cache.nodes = ['node_modules/http-cache-semantics'];",
        "lock.packages['node_modules/npm/node_modules/http-cache-semantics'].version = '4.2.1';",
    ],
)
def test_release_audit_rejects_scope_drift(mutation: str) -> None:
    """Expire exceptions when advisory, version, location, or release scope changes."""

    result = _evaluate(mutation + "process.stdout.write(JSON.stringify(audit()));")
    assert result != []


def test_release_audit_handles_grounded_semantic_release_cycles() -> None:
    """Resolve plugin peer cycles only when every cause reaches an approved leaf."""

    script = """
report.vulnerabilities.micromatch = {name: 'micromatch', severity: 'high',
  nodes: ['node_modules/micromatch'], via: ['braces']};
report.vulnerabilities['semantic-release'] = {name: 'semantic-release', severity: 'high',
  nodes: ['node_modules/semantic-release'], via: ['@semantic-release/commit-analyzer', 'micromatch']};
report.vulnerabilities['@semantic-release/commit-analyzer'] = {
  name: '@semantic-release/commit-analyzer', severity: 'high',
  nodes: ['node_modules/@semantic-release/commit-analyzer'], via: ['semantic-release']};
const reviewed = audit();
braces.via.push({...braces.via[0], url: 'https://github.com/advisories/GHSA-2222-3333-4444'});
const unreviewed = audit();
process.stdout.write(JSON.stringify([reviewed, unreviewed]));
"""
    assert _evaluate(script) == [
        [],
        [
            "@semantic-release/commit-analyzer",
            "braces",
            "micromatch",
            "semantic-release",
        ],
    ]


def test_release_audit_rejects_ungrounded_cycles_and_dangling_causes() -> None:
    """Never interpret recursion or absent causal evidence as approval."""

    script = """
report.vulnerabilities['semantic-release'] = {name: 'semantic-release', severity: 'high',
  nodes: ['node_modules/semantic-release'], via: ['semantic-release']};
const cycle = audit();
report.vulnerabilities['semantic-release'].via = ['missing'];
const dangling = audit();
process.stdout.write(JSON.stringify([cycle, dangling]));
"""
    result = _evaluate(script)
    assert isinstance(result, list)
    assert result[0] != []
    assert isinstance(result[1], dict) and "error" in result[1]


@pytest.mark.parametrize(
    "mutation",
    [
        "delete report.auditReportVersion;",
        "report.error = {code: 'network'};",
        "report.vulnerabilities = [];",
        "report.metadata = {vulnerabilities: {}};",
        "delete lock.packages;",
        "lock.packages[''] = null;",
        "lock.lockfileVersion = 2;",
        "braces.nodes.push(braces.nodes[0]);",
        "report.vulnerabilities.braces = null;",
        "braces.name = 'unknown';",
        "braces.nodes = [];",
        "braces.nodes = [null];",
        "braces.via = [];",
        "braces.via = [null];",
        "braces.via = [false];",
        "delete braces.via[0].url;",
        "delete braces.via[0].severity;",
        "delete braces.via[0].dependency;",
        "delete braces.via[0].range;",
        "delete braces.via[0].source;",
        "braces.via[0].source = -1;",
    ],
)
def test_release_audit_fails_closed_on_malformed_evidence(mutation: str) -> None:
    """Reject malformed findings before considering any advisory exceptions."""

    result = _evaluate(mutation + "process.stdout.write(JSON.stringify(audit()));")
    assert isinstance(result, dict) and "error" in result
    assert "npm audit" in str(result["error"])


def test_release_audit_preserves_unrelated_bundled_findings() -> None:
    """Keep older bundled-npm issues blocking unless separately authorized."""

    script = """
report.vulnerabilities.undici = direct('undici', 'GHSA-rfgv-xxqx-mfg5',
  'node_modules/npm/node_modules/undici');
process.stdout.write(JSON.stringify(audit()));
"""
    assert _evaluate(script) == ["undici"]


def test_semantic_release_remains_the_pinned_publication_owner() -> None:
    """Prevent another custom publisher or runtime dependency waiver from replacing it."""

    manifest = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((PROJECT_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert manifest["private"] is True
    assert manifest["scripts"]["release"] == "semantic-release"
    assert manifest["devDependencies"]["semantic-release"] == "25.0.9"
    assert lock["packages"]["node_modules/handlebars"]["version"] == "4.7.10"
    assert lock["packages"]["node_modules/npm"]["version"] == "11.21.0"
