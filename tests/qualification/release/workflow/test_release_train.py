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
import subprocess

from tests.qualification.release.workflow.support import PROJECT_ROOT


def test_canary_isolated_release_train_contract() -> None:
    """Canary must validate exact bytes before updating one isolated public feed."""

    release_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    policy_text = (
        PROJECT_ROOT / ".github" / "workflows" / "main-promotion-policy.yml"
    ).read_text(encoding="utf-8")
    dependabot_text = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text(
        encoding="utf-8"
    )

    assert "      - main\n      - canary" in release_text
    assert "SUGAR_SUBSTITUTE_CANARY_RUN_NUMBER:" in release_text
    assert "format('9999.1.{0}', github.run_number)" not in release_text
    assert "SUGAR_SUBSTITUTE_RELEASE_CHANNEL: canary" in release_text
    assert "releases/download/canary-latest" in release_text
    assert "releases/download/canary/" not in release_text
    prepare_assets_text = (
        PROJECT_ROOT / "scripts" / "prepare-release-assets.mjs"
    ).read_text(encoding="utf-8")
    assert 'channel === "canary" ? "canary-latest"' in prepare_assets_text
    assert '"canary-v$version"' not in release_text
    assert "release-qualification.yml" in release_text
    assert "'canary-fast'" in release_text
    assert "Upload temporary non-release candidate channel" in release_text
    assert "validate-candidate-artifact:" in (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")
    promotion = release_text.split("  promote-release:", maxsplit=1)[1]
    assert "Download qualified Canary candidate" in promotion
    assert "gh release upload canary-latest" in promotion
    assert 'gh release upload canary-latest "$channel_dir/manifest.json"' in promotion
    assert "git/refs/tags/canary-latest" in promotion
    assert 'git/refs/tags/canary"' not in promotion
    assert promotion.count('gh release edit "$CANDIDATE_TAG"') == 1
    assert "--clobber" in promotion
    assert "--prerelease=false --latest" in promotion
    assert "github.ref_name == 'main'" in promotion
    assert "HEAD_BRANCH: ${{ github.head_ref }}" in policy_text
    assert '[ "$HEAD_BRANCH" != "canary" ]' in policy_text
    assert policy_text.count("branches:\n      - main") == 1
    assert dependabot_text.count("target-branch: canary") == 3


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

    subprocess.run(
        ["node", "--input-type=module", "--eval", javascript],
        check=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
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
    result = subprocess.run(
        ["node", "-e", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
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

    canary_resolver = resolver_text.split(
        "async function resolveCanaryStableVersion", maxsplit=1
    )[1].split("async function resolveStableVersion", maxsplit=1)[0]
    assert "analyzeCommits" in canary_resolver
    assert "semanticRelease" not in canary_resolver
    assert "branches:" not in canary_resolver


def test_canary_release_notes_direct_normal_users_to_stable(tmp_path: Path) -> None:
    """Canary notes should immediately route ordinary users to Stable."""

    output_path = tmp_path / "release-notes.md"
    result = subprocess.run(
        [
            "node",
            "scripts/release-notes-preamble.cjs",
            "--repository",
            "Artificial-Sweetener/Substitute-Test",
            "--version",
            "0.21.0-canary.42",
            "--channel",
            "canary",
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
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
