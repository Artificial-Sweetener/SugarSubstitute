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

"""Prove qualified Stable publication with real Git and a recording GitHub boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.qualification.release.workflow.stable_publication_support import (
    StablePublicationRepository,
)
from tests.qualification.release.workflow.support import PROJECT_ROOT
from tests.support.execution.node_runtime import run_node


def _publish(
    repository: StablePublicationRepository, *, draft: bool = False, fail: str = ""
) -> dict[str, object]:
    """Execute the production transaction while recording only GitHub calls."""

    script = """
import {publishStableRelease,runReleaseCommand} from './scripts/publish-stable-release.mjs';
const release=JSON.parse(process.argv[1]);
const draft=process.argv[2]==='true';
const fail=process.argv[3];
const calls=[];
const run=(command,args,cwd)=>{
 if(command==='git') return runReleaseCommand(command,args,cwd);
 calls.push(args);
 if(args[0]==='api') return JSON.stringify([draft?[{tag_name:'v0.27.2',draft:true,prerelease:false}]:[]]);
 if(args[1]===fail) throw new Error('Controlled GitHub '+fail+' failure');
 return '';
};
let error=null;
try {await publishStableRelease(release,run);} catch(failure) {error=failure.message;}
process.stdout.write(JSON.stringify({calls,error}));
"""
    result = run_node(
        (
            "--input-type=module",
            "-e",
            script,
            json.dumps(repository.release_context()),
            str(draft).lower(),
            fail,
        ),
        cwd=PROJECT_ROOT,
        check=True,
    )
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


def test_stable_publication_pushes_exact_metadata_and_finalizes_complete_assets(
    tmp_path: Path,
) -> None:
    """Commit only release metadata and make the draft public after all asset uploads."""

    repository = StablePublicationRepository(tmp_path)
    result = _publish(repository)
    assert result["error"] is None
    calls = result["calls"]
    assert isinstance(calls, list)
    creation = calls[1]
    assert creation[:3] == ["release", "create", "v0.27.2"]
    assert "--draft" in creation and "--verify-tag" in creation
    assert sorted(
        Path(argument).name
        for argument in creation
        if argument.startswith(str(repository.channel))
        and argument != str(repository.channel / ".release-notes.md")
    ) == sorted(
        path.name
        for path in repository.channel.iterdir()
        if path.name != ".release-notes.md"
    )
    assert calls[-1][-3:] == ["--draft=false", "--prerelease=false", "--latest"]
    assert (
        repository.git("rev-parse", "v0.27.2").strip()
        == repository.git("rev-parse", "HEAD").strip()
    )
    assert repository.git(
        "ls-remote", str(repository.remote), "refs/tags/v0.27.2"
    ).startswith(repository.git("rev-parse", "v0.27.2").strip())
    assert (repository.root / "runtime.txt").read_text() == "corrected\n"
    changelog = (repository.root / "CHANGELOG.md").read_text()
    notes = (repository.channel / ".release-notes.md").read_text()
    assert "Preserved history." in changelog
    assert "## Install SugarSubstitute" not in changelog
    assert notes.index("## Install SugarSubstitute") < notes.index("### Bug Fixes")
    assert notes.endswith(
        changelog.split("\n\n## Previous release", maxsplit=1)[0] + "\n"
    )
    assert (
        json.loads((repository.root / "package.json").read_text())["version"]
        == "0.27.2"
    )


def test_failed_upload_retains_draft_and_retry_reuses_the_exact_remote_tag(
    tmp_path: Path,
) -> None:
    """Resume an interrupted draft without duplicating history or release commits."""

    repository = StablePublicationRepository(tmp_path)
    failure = _publish(repository, fail="create")
    assert "Controlled GitHub create failure" in str(failure["error"])
    assert "--draft=false" not in json.dumps(failure["calls"])
    published_tree = repository.git("rev-parse", "HEAD").strip()
    retried = _publish(repository, draft=True)
    assert retried["error"] is None
    assert repository.git("rev-parse", "HEAD").strip() == published_tree
    assert (repository.root / "CHANGELOG.md").read_text().count("## [0.27.2]") == 1
    assert '"upload"' in json.dumps(retried["calls"])
    assert "--clobber" in json.dumps(retried["calls"])
    assert "--draft=false" in json.dumps(retried["calls"])


@pytest.mark.parametrize(
    "damage", ["checksum", "extra", "missing", "manifest", "version"]
)
def test_invalid_qualified_assets_abort_before_git_or_publication_mutation(
    tmp_path: Path, damage: str
) -> None:
    """Reject corrupted, incomplete, or mismatched channels before committing or uploading."""

    repository = StablePublicationRepository(tmp_path)
    if damage == "checksum":
        (repository.channel / "SugarSubstitute-app-v0.27.2.zip").write_bytes(
            b"corrupted"
        )
    elif damage == "extra":
        (repository.channel / "unexpected.zip").write_bytes(b"unexpected")
    elif damage == "missing":
        (repository.channel / "manifest.signed.json").unlink()
    elif damage == "manifest":
        (repository.channel / "manifest.json").write_text(
            '{"channel":"canary","version":"0.27.2"}'
        )
    else:
        repository.git("commit", "--allow-empty", "-m", "feat: add a new release")
        repository.source_commit = repository.git("rev-parse", "HEAD").strip()
    result = _publish(repository)
    assert result["error"] is not None
    assert repository.git("rev-parse", "HEAD").strip() == repository.source_commit
    assert repository.git("tag", "--list", "v0.27.2") == ""
    calls = result["calls"]
    assert isinstance(calls, list) and len(calls) == 1
