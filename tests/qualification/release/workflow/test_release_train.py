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

"""Qualify Canary release-train policy and version construction."""

from __future__ import annotations

import json
from pathlib import Path

from tests.qualification.release.workflow.support import PROJECT_ROOT, workflow_text
from tests.support.execution.node_runtime import run_node


def test_canary_isolated_release_train_contract() -> None:
    """Canary must validate exact bytes before updating one isolated public feed."""

    release_text = workflow_text("release.yml", "release-prepublication.yml")
    version_text = workflow_text("release-version.yml")
    candidate_text = workflow_text("release-candidate.yml")
    publication_text = workflow_text("release-publication.yml")
    policy_text = (
        PROJECT_ROOT / ".github" / "workflows" / "main-promotion-policy.yml"
    ).read_text(encoding="utf-8")
    dependabot_text = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text(
        encoding="utf-8"
    )

    assert "      - main\n      - canary" in release_text
    assert "SUGAR_SUBSTITUTE_CANARY_RUN_NUMBER:" in version_text
    assert "format('9999.1.{0}', github.run_number)" not in release_text
    assert "SUGAR_SUBSTITUTE_RELEASE_CHANNEL: ${{ inputs.channel }}" in candidate_text
    assert "canary-latest" in publication_text
    assert "releases/download/canary/" not in publication_text
    prepare_assets_text = (
        PROJECT_ROOT / "scripts" / "prepare-release-assets.mjs"
    ).read_text(encoding="utf-8")
    assert 'channel === "canary" ? "canary-latest"' in prepare_assets_text
    assert '"canary-v$version"' not in publication_text
    assert "release-qualification.yml" in release_text
    assert "'canary-fast'" in release_text
    assert "Upload private non-release candidate channel" in candidate_text
    assert "validate-candidate-artifact:" in (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "Download qualified Canary candidate" in publication_text
    assert "gh release upload canary-latest" in publication_text
    assert (
        'gh release upload canary-latest "$channel_dir/manifest.json"'
        in publication_text
    )
    assert "git/refs/tags/canary-latest" in publication_text
    assert 'git/refs/tags/canary"' not in publication_text
    assert "--clobber" in publication_text
    assert 'canary_release_title="Canary ${CANDIDATE_VERSION/-canary./.}"' in (
        publication_text
    )
    assert "${CANDIDATE_VERSION/-canary-/.}" not in publication_text
    assert "github.ref_name == 'main'" in publication_text
    assert "HEAD_BRANCH: ${{ github.head_ref }}" in policy_text
    assert '[ "$HEAD_BRANCH" != "canary" ]' in policy_text
    assert policy_text.count("branches:\n      - main") == 1
    assert dependabot_text.count("target-branch: canary") == 3


def test_publication_resolves_the_stable_version_from_complete_history() -> None:
    """Keep final Stable version resolution backed by every release commit."""

    publication_text = workflow_text("release-publication.yml")

    checkout = publication_text.split(
        "      - name: Checkout publication source", maxsplit=1
    )[1].split("\n\n", maxsplit=1)[0]
    assert "          fetch-depth: 0" in checkout
    assert "&& 0 || 1" not in checkout


def test_release_version_script_embeds_canary_channel(tmp_path: Path) -> None:
    """Native Canary installers must receive immutable build-channel metadata."""

    package_payload = {"version": "0.20.1"}
    lock_payload = {
        "version": "0.20.1",
        "packages": {"": {"version": "0.20.1"}},
    }
    fixture_files = {
        "package.json": json.dumps(package_payload),
        "package-lock.json": json.dumps(lock_payload),
        "launcher/sugarsubstitute_launcher/__init__.py": '__version__ = "0.20.1"\n',
        "launcher/sugarsubstitute_launcher/build_metadata.py": (
            'RELEASE_CHANNEL = "stable"\n'
        ),
        "substitute/_version.py": '__version__ = "0.20.1"\n',
    }
    for relative_path, content in fixture_files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    script_url = (PROJECT_ROOT / "scripts" / "update-release-versions.mjs").as_uri()
    root_url = f"{tmp_path.as_uri()}/"
    javascript = (
        f"import {{ updateReleaseVersions }} from {json.dumps(script_url)}; "
        f"updateReleaseVersions(new URL({json.dumps(root_url)}), "
        '"0.21.0-canary.42", "canary");'
    )

    run_node(
        ("--input-type=module", "--eval", javascript),
        check=True,
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
    )

    assert (
        tmp_path / "launcher" / "sugarsubstitute_launcher" / "build_metadata.py"
    ).read_text(encoding="utf-8") == 'RELEASE_CHANNEL = "canary"\n'
    assert (
        json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))["version"]
        == "0.21.0-canary.42"
    )


def test_canary_version_derives_from_next_stable_release() -> None:
    """Canary versions should identify their future Stable base and CI build."""

    script = """
const versions = require('./scripts/canary-release-version.cjs');
process.stdout.write(JSON.stringify({
  canary: versions.createCanaryVersion('0.21.0', '142'),
  latest: versions.latestStableTag(['v0.19.2', 'v0.20.1', 'v0.20.0']),
  patch: versions.nextStableVersion(['v0.19.2', 'v0.20.1'], 'patch'),
  minor: versions.nextStableVersion(['v0.19.2', 'v0.20.1'], 'minor'),
}));
"""
    result = run_node(
        ("-e", script),
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "canary": "0.21.0-canary.142",
        "latest": "v0.20.1",
        "patch": "0.20.2",
        "minor": "0.21.0",
    }


def test_canary_version_resolution_does_not_probe_ambiguous_remote_ref() -> None:
    """Canary analysis must work while the legacy Canary tag still exists."""

    resolver_text = (
        PROJECT_ROOT / "scripts" / "resolve-next-release-version.mjs"
    ).read_text(encoding="utf-8")

    assert "analyzeCommits" in resolver_text
    assert "branches:" not in resolver_text


def test_read_only_version_resolution_never_probes_remote_push_permission() -> None:
    """Keep pre-publication version calculation independent of repository writes."""

    resolver_text = (
        PROJECT_ROOT / "scripts" / "resolve-next-release-version.mjs"
    ).read_text(encoding="utf-8")
    orchestrator = workflow_text("release-prepublication.yml")
    version_owner = workflow_text("release-version.yml")

    assert 'import("semantic-release")' not in resolver_text
    assert "contents: write" not in version_owner
    assert "contents: read" in version_owner
    determine_call = orchestrator.split("  determine-version:", maxsplit=1)[1].split(
        "  build-release:", maxsplit=1
    )[0]
    assert "permissions:" not in determine_call


def test_canary_release_notes_direct_normal_users_to_stable(tmp_path: Path) -> None:
    """Canary notes should immediately route ordinary users to Stable."""

    output_path = tmp_path / "release-notes.md"
    result = run_node(
        (
            "scripts/release-notes-preamble.cjs",
            "--repository",
            "Artificial-Sweetener/Substitute-Test",
            "--version",
            "0.21.0-canary.42",
            "--channel",
            "canary",
            "--output",
            str(output_path),
        ),
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    notes = output_path.read_text(encoding="utf-8")
    stable_url = (
        "https://github.com/Artificial-Sweetener/Substitute-Test/releases/latest"
    )
    assert notes.startswith("> [!WARNING]\n")
    assert f"[Download the latest Stable release instead]({stable_url})" in notes
    assert "DO NOT download this Canary build for normal use" in notes
    assert "Canary builds are intended only for testers" in notes
    assert "releases/download/canary-latest/SugarSubstitute-0.21.0-canary.42" in notes
