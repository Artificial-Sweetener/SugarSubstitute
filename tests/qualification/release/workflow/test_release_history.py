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

"""Prove canonical beta analysis and conventional history through installed libraries."""

from __future__ import annotations

import json

import pytest

from tests.qualification.release.workflow.support import PROJECT_ROOT
from tests.support.execution.node_runtime import run_node


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("feat(cubes): add shape", "minor"),
        ("FEAT: add shape", "minor"),
        ("fix: restore launcher", "patch"),
        ("FIX: restore launcher", "patch"),
        ("perf: reduce redraw", "patch"),
        ("docs: update guide", None),
        ("chore: update tools", None),
        ("feat!: revise API", None),
        ("docs: revise API\n\nBREAKING CHANGE: pass bounds", "minor"),
        ('Revert "feat: add shape"\n\nThis reverts commit ' + "a" * 40 + ".", "patch"),
        ("", None),
    ],
)
def test_beta_release_rules_preserve_characterized_results(
    message: str, expected: str | None
) -> None:
    """Retain fixed results characterized against the original release analyzer."""

    script = """
import {analyzeCommits} from './scripts/release-history.mjs';
process.stdout.write(JSON.stringify(analyzeCommits([{hash:'b'.repeat(40), message:process.argv[1]}])));
"""
    result = run_node(
        ("--input-type=module", "-e", script, message), cwd=PROJECT_ROOT, check=True
    )
    assert json.loads(result.stdout) == expected


def test_reverted_history_uses_full_commit_identities_for_one_release_decision() -> (
    None
):
    """Remove a reverted feature while retaining an independent surviving fix."""

    script = """
import {analyzeCommits} from './scripts/release-history.mjs';
const original={hash:'a'.repeat(40),message:'feat: add shape'};
const revert={hash:'b'.repeat(40),message:'Revert "feat: add shape"\\n\\nThis reverts commit '+original.hash+'.'};
process.stdout.write(JSON.stringify([
 analyzeCommits([revert,original]),
 analyzeCommits([{hash:'c'.repeat(40),message:'fix: preserve image'},revert,original]),
]));
"""
    result = run_node(
        ("--input-type=module", "-e", script), cwd=PROJECT_ROOT, check=True
    )
    assert json.loads(result.stdout) == [None, "patch"]


def test_conventional_history_preserves_hashes_issues_and_comparison_links() -> None:
    """Use the existing Angular writer's fixed Markdown contract."""

    script = """
import {generateReleaseNotes} from './scripts/release-history.mjs';
const notes=await generateReleaseNotes([
 {hash:'a'.repeat(40),message:'feat(cubes): add shape (#12)'},
 {hash:'b'.repeat(40),message:'fix: restore launcher'},
],{version:'0.28.0',repository:'Artificial-Sweetener/Substitute-Test',serverUrl:'https://github.com',
 previousTag:'v0.27.1',packageData:{},date:'2026-10-07'});
process.stdout.write(notes);
"""
    result = run_node(
        ("--input-type=module", "-e", script), cwd=PROJECT_ROOT, check=True
    )
    base = "https://github.com/Artificial-Sweetener/Substitute-Test"
    assert result.stdout == (
        f"# [0.28.0]({base}/compare/v0.27.1...v0.28.0) (2026-10-07)\n\n\n"
        "### Bug Fixes\n\n"
        f"* restore launcher ([bbbbbbb]({base}/commit/{'b' * 40}))\n\n\n"
        "### Features\n\n"
        f"* **cubes:** add shape ([#12]({base}/issues/12)) ([aaaaaaa]({base}/commit/{'a' * 40}))\n"
    )


def test_deeply_nested_commit_metadata_remains_data() -> None:
    """Analyze malicious nesting without loading the removed recursive walkers."""

    script = """
import {analyzeCommits,generateReleaseNotes} from './scripts/release-history.mjs';
const nested='{'.repeat(12000)+'a,b'+'}'.repeat(12000);
const commits=[{hash:'a'.repeat(40),message:'fix('+nested+'): preserve image'}];
const notes=await generateReleaseNotes(commits,{version:'0.27.2',repository:'Owner/Repo',
 serverUrl:'https://github.com',previousTag:'v0.27.1',packageData:{}});
process.stdout.write(JSON.stringify({type:analyzeCommits(commits),hasScope:notes.includes(nested)}));
"""
    result = run_node(
        ("--input-type=module", "-e", script), cwd=PROJECT_ROOT, check=True
    )
    assert json.loads(result.stdout) == {"type": "patch", "hasScope": True}
