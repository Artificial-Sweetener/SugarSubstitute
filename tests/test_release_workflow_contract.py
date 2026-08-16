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

"""Validate cross-platform release workflow and packaging ownership contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess

import yaml  # type: ignore[import-untyped]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_ACTIONS = frozenset(
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
_WORKFLOW_PATHS = tuple((PROJECT_ROOT / ".github" / "workflows").glob("*.yml"))
_DOCUMENTATION_PATH_FILTER = ["**/*.md"]


def test_documentation_only_changes_skip_automatic_ci() -> None:
    """Keep Markdown-only pushes and pull requests out of automated gates."""

    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in _WORKFLOW_PATHS
    }
    triggers = {name: workflow[True] for name, workflow in workflows.items()}

    assert "push" not in triggers["tests.yml"]
    assert triggers["tests.yml"]["pull_request"]["paths-ignore"] == (
        _DOCUMENTATION_PATH_FILTER
    )
    assert triggers["comfy-compatibility.yml"]["push"]["paths-ignore"] == (
        _DOCUMENTATION_PATH_FILTER
    )
    assert (
        triggers["comfy-compatibility.yml"]["pull_request"]["paths-ignore"]
        == _DOCUMENTATION_PATH_FILTER
    )
    assert triggers["release.yml"]["push"]["paths-ignore"] == (
        _DOCUMENTATION_PATH_FILTER
    )


def test_default_ci_runs_complete_partitioned_suite_on_every_platform() -> None:
    """Require every supported operating system to run parallel and serial tests."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    platform_job = workflow["jobs"]["platform-tests"]
    matrix = platform_job["strategy"]["matrix"]["include"]

    assert {entry["os"] for entry in matrix} == {
        "windows-latest",
        "ubuntu-24.04",
        "macos-15",
    }
    assert {entry["os"]: entry["python-version"] for entry in matrix} == {
        "windows-latest": "3.12.10",
        "ubuntu-24.04": "3.12.13",
        "macos-15": "3.12.10",
    }
    job_script = _job_script(platform_job)
    assert '-m "not serial"' in job_script
    assert "tools.ci.run_serial_test_modules" in job_script
    assert "--junitxml=" in job_script


def test_ci_uses_exact_language_and_package_toolchains() -> None:
    """Keep every workflow on the shared verified Python and Node toolchains."""

    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in _WORKFLOW_PATHS
    }

    assert all(
        workflow["env"]["PYTHON_VERSION"] == "3.12.10"
        for workflow in workflows.values()
    )
    assert all(
        workflow["env"]["LINUX_PYTHON_VERSION"] == "3.12.13"
        for workflow in workflows.values()
    )
    assert workflows["release.yml"]["env"]["NODE_VERSION"] == "22.14.0"

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in _WORKFLOW_PATHS
    )
    assert "requirements-toolchain.txt" in workflow_text
    assert "pip install -r requirements.txt" not in workflow_text
    assert "pip install --upgrade pip" not in workflow_text
    assert "uv==" not in workflow_text


def test_strategy_matrices_use_literal_toolchain_versions() -> None:
    """Avoid expression contexts that GitHub rejects while expanding matrices."""

    expected_versions = {
        "windows-latest": "3.12.10",
        "ubuntu-24.04": "3.12.13",
        "macos-15": "3.12.10",
    }
    observed_entries = 0
    for workflow_path in _WORKFLOW_PATHS:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            strategy = job.get("strategy", {})
            matrix = strategy.get("matrix", {})
            for entry in matrix.get("include", ()):
                if "python-version" not in entry:
                    continue
                assert entry["python-version"] == expected_versions[entry["os"]]
                assert "${{" not in entry["python-version"]
                observed_entries += 1

    assert observed_entries == 24


def test_ci_actions_use_immutable_verified_revisions() -> None:
    """Prevent mutable action tags from changing the CI toolchain silently."""

    observed_revisions: dict[str, set[str]] = {}
    for workflow_path in _WORKFLOW_PATHS:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", ()):
                action_reference = step.get("uses", "")
                if not action_reference.startswith("actions/"):
                    continue
                action, revision = action_reference.rsplit("@", maxsplit=1)
                assert re.fullmatch(r"[0-9a-f]{40}", revision)
                observed_revisions.setdefault(action, set()).add(revision)

    assert observed_revisions.keys() == _EXPECTED_ACTIONS
    assert all(len(revisions) == 1 for revisions in observed_revisions.values())


def test_pre_commit_hooks_use_an_immutable_verified_revision() -> None:
    """Prevent local commit gates from changing without repository review."""

    configuration = (PROJECT_ROOT / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )

    assert "rev: 2c9f875913ee60ca25ce70243dc24d5b6415598c # v4.6.0" in configuration


def test_release_node_dependencies_use_exact_verified_versions() -> None:
    """Keep semantic-release packages reproducible through the npm lockfile."""

    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((PROJECT_ROOT / "package-lock.json").read_text(encoding="utf-8"))

    assert re.fullmatch(r"npm@\d+\.\d+\.\d+", package["packageManager"])
    assert package["devDependencies"].keys() == {
        "@semantic-release/changelog",
        "@semantic-release/commit-analyzer",
        "@semantic-release/exec",
        "@semantic-release/git",
        "@semantic-release/github",
        "@semantic-release/release-notes-generator",
        "semantic-release",
    }
    assert all(
        re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version)
        for version in package["devDependencies"].values()
    )
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
    for dependency, version in package["devDependencies"].items():
        assert lock["packages"][f"node_modules/{dependency}"]["version"] == version


def test_main_release_requires_the_authoritative_cross_platform_suite() -> None:
    """Prevent version resolution until the exact release commit passes all tests."""

    release_workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    tests_workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "tests.yml"
    ).read_text(encoding="utf-8")

    jobs = release_workflow["jobs"]
    assert jobs["tests"]["name"] == "Required cross-platform tests"
    assert jobs["tests"]["uses"] == "./.github/workflows/tests.yml"
    assert jobs["tests"]["if"] == (
        "github.event_name != 'workflow_dispatch' || "
        "github.event.inputs.dry_run != 'true' || "
        "github.event.inputs.qualification_scope == 'full'"
    )
    assert jobs["determine-version"]["needs"] == "tests"
    assert "  workflow_call:" in tests_workflow_text
    assert "  push:" not in tests_workflow_text.split("permissions:", maxsplit=1)[0]


def test_push_and_pull_request_runs_share_commit_concurrency() -> None:
    """Opening or updating a PR must cancel its duplicate branch-push run."""

    for workflow_name in ("tests.yml", "comfy-compatibility.yml"):
        workflow = yaml.safe_load(
            (PROJECT_ROOT / ".github" / "workflows" / workflow_name).read_text(
                encoding="utf-8"
            )
        )
        concurrency = workflow["concurrency"]

        assert (
            "github.event.pull_request.head.sha || github.sha" in concurrency["group"]
        )
        assert concurrency["cancel-in-progress"] is True


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
    assert "releases/download/canary" in release_text
    assert '"canary-v$version"' not in release_text
    assert "release-qualification.yml" in release_text
    assert "'canary-fast'" in release_text
    assert "Upload temporary non-release candidate channel" in release_text
    assert "validate-candidate-artifact:" in (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")
    promotion = release_text.split("  promote-release:", maxsplit=1)[1]
    assert "Download qualified Canary candidate" in promotion
    assert "gh release upload canary" in promotion
    assert 'gh release upload canary "$channel_dir/manifest.json"' in promotion
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
  fallback: versions.nextPatchVersion(['v0.19.2', 'v0.20.1', 'v0.20.0']),
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
        "fallback": "0.20.2",
    }


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
    assert "releases/download/canary/SugarSubstitute-0.21.0-canary.42" in notes


def test_cross_platform_validation_requires_explicit_invocation() -> None:
    """Keep prerelease publication behind an explicit workflow dispatch."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml"
    ).read_text(encoding="utf-8")

    assert "  workflow_dispatch:" in workflow_text
    assert "  push:" not in workflow_text


def test_managed_comfy_pin_automation_opens_pr_before_qualification() -> None:
    """New upstream pins should always create reviewable PRs without auto-merge."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "comfy-pin-update.yml"
    ).read_text(encoding="utf-8")

    assert "  schedule:" in workflow_text
    assert "gh pr create" in workflow_text
    assert "gh workflow run tests.yml" in workflow_text
    assert "gh workflow run managed-comfy-install.yml" in workflow_text
    assert "gh pr merge" not in workflow_text
    assert "auto-merge" not in workflow_text


def test_managed_comfy_install_uses_exact_pin_and_artifact_cache() -> None:
    """The compatibility gate should launch pinned Comfy without reinstalling Torch."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "managed-comfy-install.yml"
    ).read_text(encoding="utf-8")

    assert "actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae" in workflow_text
    assert "standalone_environment_pin.json" in workflow_text
    assert "verify_managed_comfy_install.py" in workflow_text
    assert "--variant win-cpu" in workflow_text
    assert "pip install torch" not in workflow_text


def test_release_qualification_covers_clean_launch_and_upgrade_depth() -> None:
    """Release candidates must prove exact installers before stable promotion."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")

    assert "verify_installer_lifecycle.py clean" in workflow_text
    assert "verify_installer_lifecycle.py upgrade" in workflow_text
    assert "python -m tools.ci.resolve_upgrade_sources" in workflow_text
    assert '--historical-published-at "${{ matrix.history.published_at }}"' in (
        workflow_text
    )
    assert "Windows x64" in workflow_text
    assert "Linux x64" in workflow_text
    assert "macOS Apple Silicon" in workflow_text
    assert '@("windows", "linux", "macos")' in workflow_text
    assert "update_platforms" in workflow_text
    assert "./.github/workflows/managed-comfy-install.yml" in workflow_text
    assert "gh release edit" not in workflow_text
    lifecycle_text = (
        PROJECT_ROOT / "tools" / "ci" / "verify_installer_lifecycle.py"
    ).read_text(encoding="utf-8")
    ui_qualification_text = (
        PROJECT_ROOT / "tools" / "ci" / "installer_ui_qualification.py"
    ).read_text(encoding="utf-8")
    historical_qualification_text = (
        PROJECT_ROOT / "tools" / "ci" / "historical_install_qualification.py"
    ).read_text(encoding="utf-8")
    assert "run_current_installer_ui" in lifecycle_text
    assert "install_candidate_over_historical_install" in lifecycle_text
    assert "INSTALLER_QUALIFICATION_PLAN_ENV" in ui_qualification_text
    current_installer_path = ui_qualification_text.split(
        "def run_current_installer_ui", maxsplit=1
    )[1].split("\ndef ", maxsplit=1)[0]
    assert '"--headless-install"' not in current_installer_path
    assert "prepare_portable_historical_install" in lifecycle_text
    assert '"--headless-install"' in historical_qualification_text
    assert "Download real historical installer" in workflow_text
    assert '"SugarSubstitute-Installer-Windows-x64.exe"' in workflow_text
    assert '"SugarSubstitute-Installer-Linux-x86_64.AppImage"' in workflow_text
    assert '"SugarSubstitute-Installer-macOS-Apple-Silicon.dmg"' in workflow_text
    assert "Reconstitute exact historical macOS install channel" in workflow_text
    assert "python -m tools.ci.reconstitute_historical_macos_release" in workflow_text
    assert workflow_text.count("QT_QPA_PLATFORM: cocoa") == 2
    assert (
        "QT_QPA_PLATFORM: ${{ matrix.platform == 'macos' && 'cocoa' || 'offscreen' }}"
    ) in workflow_text
    assert '"--historical-release-root"' in workflow_text
    assert '--candidate-installer "$env:CANDIDATE_INSTALLER"' in workflow_text
    assert "CANDIDATE_INSTALLER=" in workflow_text
    assert "Build version-pinned historical Windows setup" not in workflow_text
    assert "SugarSubstitute-Local-Test-Installer" not in workflow_text


def test_release_dry_run_qualifies_temporary_bytes_without_publishing() -> None:
    """Manual dry runs should exercise release qualification without a release."""

    release_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    qualification_text = (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")
    preparation_text = (
        PROJECT_ROOT / "scripts" / "prepare-release-assets.mjs"
    ).read_text(encoding="utf-8")

    assert "SUGAR_SUBSTITUTE_ASSET_BASE_URL: https://localhost:44443" in release_text
    assert "include-hidden-files: true" in release_text
    assert "SUGAR_SUBSTITUTE_QUALIFICATION_VERSION:" in release_text
    assert "format('9999.0.{0}', github.run_number)" in release_text
    assert "name: non-release-candidate-channel" in release_text
    assert "candidate_artifact_name:" in release_text
    assert "github.event.inputs.dry_run != 'true'" in release_text
    assert '--candidate-release-root "build/candidate"' in qualification_text
    assert "Provide exactly one candidate_tag or candidate_artifact_name" in (
        qualification_text
    )
    assert "process.env.SUGAR_SUBSTITUTE_ASSET_BASE_URL" in preparation_text
    assert 'startsWith("https://")' in preparation_text
    assert "qualification_timeout_seconds" in qualification_text
    assert "qualification_timeout_seconds:" in release_text
    assert (
        "qualification_timeout_seconds: ${{ inputs.dry_run == 'true' && "
        "inputs.qualification_scope != 'full' && "
        "inputs.qualification_timeout_seconds || '3600' }}"
    ) in release_text
    assert "Published and full qualification require the canonical" in (
        qualification_text
    )
    assert qualification_text.count("timeout-minutes: 75") == 2
    assert qualification_text.count("Upload clean-install diagnostics") == 2
    assert "Upload historical-update diagnostics" in qualification_text
    assert "historical-update-diagnostics-${{ matrix.platform }}-" in qualification_text
    assert "historical-managed-comfy-startup.log" in qualification_text
    assert "launcher/locks/application-launch.lock" in qualification_text
    assert "appdata/runtime_state/**" in qualification_text
    assert ".historical-certificate/requests.jsonl" in qualification_text
    historical_proof = qualification_text.split(
        "- name: Prove historical update, splash, and main shell",
        maxsplit=1,
    )[1].split("- name: Upload historical-update diagnostics", maxsplit=1)[0]
    assert '--timeout-seconds "$env:QUALIFICATION_TIMEOUT_SECONDS"' in historical_proof
    assert "clean-install-diagnostics-${{ runner.os }}" in qualification_text
    assert (
        qualification_text.count("Restore checksum-addressed standalone artifact") == 2
    )
    assert qualification_text.count("cache_managed_comfy_artifacts.py") == 2
    assert "managed-comfy-${{ matrix.standalone_variant }}-" in qualification_text
    assert "managed-comfy-mac-mps-" in qualification_text
    assert qualification_text.count("--managed-artifact-cache-root") == 4
    assert qualification_text.count("appdata/runtime_state/setup_transaction.json") == 2
    assert qualification_text.count(".SugarSubstitute-clean-standalone-cache.json") == 2


def test_focused_release_qualification_cannot_skip_publishing_gates() -> None:
    """Only manual non-publishing runs may bypass unchanged repository gates."""

    release_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    qualification_text = (
        PROJECT_ROOT / ".github" / "workflows" / "release-qualification.yml"
    ).read_text(encoding="utf-8")

    tests_guard = release_text.split("  tests:", maxsplit=1)[1].split(
        "  determine-version:", maxsplit=1
    )[0]
    assert "github.event_name != 'workflow_dispatch'" in tests_guard
    assert "github.event.inputs.dry_run != 'true'" in tests_guard
    assert "github.event.inputs.qualification_scope == 'full'" in tests_guard
    assert (
        "candidate_run_id: ${{ needs.stage-candidate.outputs.candidate_run_id }}"
        in (release_text)
    )
    assert "  actions: read\n  contents: write" in release_text
    assert "steps.release-version.outputs.should_release ||" in release_text
    assert "format('9999.0.{0}', github.run_number) || ''" in release_text
    assert release_text.count("github.event.inputs.qualification_scope != 'full'") == 6
    assert release_text.count("always() &&") >= 6
    assert "release_input_run_id:" in release_text
    assert "qualification_candidate_run_id:" in release_text
    assert "qualification_candidate_version:" in release_text
    assert "github.event.inputs.release_input_run_id != ''" in release_text
    assert (
        "run-id: ${{ github.event.inputs.release_input_run_id || github.run_id }}"
        in (release_text)
    )
    assert "needs.stage-candidate.result == 'success'" in release_text
    assert "Reuse exact temporary candidate channel" in release_text
    assert "needs.stage-candidate.outputs.candidate_run_id" in release_text
    assert "github.event.inputs.qualification_candidate_version ||" in release_text
    assert "qualification-all" in release_text
    assert "upgrade_selection:" in release_text
    assert (
        "upgrade_selection: ${{ inputs.dry_run == 'true' && "
        "inputs.qualification_scope != 'full' && inputs.upgrade_selection || "
        "'complete' }}"
    ) in release_text
    assert '--selection "${{ inputs.upgrade_selection }}"' in qualification_text
    assert "inputs.qualification_scope == 'qualification-all' && 'all'" not in (
        release_text
    )
    assert (
        "qualification-all" in qualification_text.split("permissions:", maxsplit=1)[0]
    )
    assert '@("all", "qualification-all", "clean-all")' in qualification_text
    assert '@("all", "qualification-all", "updates-all")' in qualification_text
    assert "select-qualification:" in qualification_text
    assert "clean_matrix" in qualification_text
    assert "update_platforms" in qualification_text
    assert "run-id: ${{ inputs.candidate_run_id" in qualification_text
    assert "managed_comfy_enabled" in qualification_text


def test_cross_platform_validation_proves_packaged_linux_system_trust() -> None:
    """Require the frozen Linux installer to verify releases across distro families."""

    workflow = yaml.safe_load(
        (
            PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml"
        ).read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["linux-distro-trust"]
    matrix = job["strategy"]["matrix"]["include"]

    assert {entry["image"] for entry in matrix} == {
        "ubuntu:24.04",
        "fedora:44",
        "archlinux:base",
        "opensuse/leap:16.0",
    }
    assert {entry["ca_path"] for entry in matrix} == {
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
        "/etc/ssl/cert.pem",
        "/etc/ssl/ca-bundle.pem",
    }
    job_script = _job_script(job)
    assert "--verify-release-connectivity" in job_script
    assert "--manifest-url" in job_script
    assert "APPIMAGE_EXTRACT_AND_RUN=1" in job_script


def test_release_workflow_builds_every_published_platform_after_version_resolution() -> (
    None
):
    """Native builders should share one semantic-release version decision."""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
    )
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "tests",
        "determine-version",
        "build-windows",
        "build-macos",
        "build-linux",
        "stage-candidate",
        "qualify-candidate",
        "promote-release",
    }
    for job_name in ("build-windows", "build-macos", "build-linux"):
        job = jobs[job_name]
        assert job["needs"] == "determine-version"
        assert "needs.determine-version.outputs.version" in _job_script(job)
    assert jobs["build-macos"]["runs-on"] == "macos-latest"
    assert jobs["build-linux"]["runs-on"] == "ubuntu-24.04"
    assert set(jobs["stage-candidate"]["needs"]) == {
        "determine-version",
        "build-windows",
        "build-macos",
        "build-linux",
    }
    assert jobs["qualify-candidate"]["uses"] == (
        "./.github/workflows/release-qualification.yml"
    )
    assert set(jobs["promote-release"]["needs"]) == {
        "stage-candidate",
        "qualify-candidate",
    }


def test_release_stages_then_promotes_the_same_candidate_bytes() -> None:
    """Stable publication must be promotion after qualification, never a rebuild."""

    workflow_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "--prerelease" in workflow_text
    assert "release-qualification.yml" in workflow_text
    assert "--prerelease=false --latest" in workflow_text
    assert "SUGAR_SUBSTITUTE_STAGE_ONLY" in workflow_text
    promotion = workflow_text.split("  promote-release:", maxsplit=1)[1]
    assert "prepare-release-assets" not in promotion
    assert "PyInstaller" not in promotion


def test_first_release_publishes_version_090_without_adding_a_commit() -> None:
    """The flattened root release should publish directly from its existing tree."""

    workflow_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    resolver_text = (
        PROJECT_ROOT / "scripts" / "resolve-next-release-version.mjs"
    ).read_text(encoding="utf-8")

    assert 'const FIRST_RELEASE_VERSION = "0.9.0"' in resolver_text
    assert "result?.nextRelease?.version" in resolver_text
    assert "first_release=${firstRelease}" in resolver_text
    assert "gh release create" in workflow_text
    assert "prepare-release-assets.mjs" in workflow_text
    assert "prime-first-release-tag" not in workflow_text


def test_version_resolution_excludes_publishing_plugins() -> None:
    """Version calculation should not require GitHub publishing authentication."""

    script = """
const releaseConfig = require('./.releaserc.cjs');
const {selectVersionResolutionPlugins} = require(
  './scripts/release-version-plugins.cjs',
);
process.stdout.write(JSON.stringify(selectVersionResolutionPlugins(releaseConfig)));
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
    plugins = json.loads(result.stdout)
    assert len(plugins) == 1
    assert plugins[0][0] == "@semantic-release/commit-analyzer"
    assert plugins[0][1]["releaseRules"]


def test_macos_release_requires_no_paid_apple_credentials() -> None:
    """macOS artifacts should use verifiable ad-hoc signatures without notarization."""

    workflow_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "codesign --force --deep --sign -" in workflow_text
    assert "codesign --verify --deep --strict" in workflow_text
    assert "secrets.APPLE_" not in workflow_text
    assert "notarytool" not in workflow_text
    assert "stapler" not in workflow_text


def test_pyinstaller_specs_share_launcher_runtime_data_ownership() -> None:
    """Every native launcher build should use one complete runtime-data owner."""

    spec_paths = tuple((PROJECT_ROOT / "launcher").glob("*.spec"))

    assert len(spec_paths) == 7
    for spec_path in spec_paths:
        spec_text = spec_path.read_text(encoding="utf-8")
        assert "from tools.pyinstaller_support import build_launcher_data_files" in (
            spec_text
        )
        assert "build_launcher_data_files(" in spec_text
        assert "shutil.which" not in spec_text


def test_linux_workflow_pins_appimagetool_and_builds_both_native_formats() -> None:
    """Linux packaging should verify its tool and publish AppImage plus Debian."""

    workflow_text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "a6d71e2b6cd66f8e8d16c37ad164658985e0cf5fcaa950c90a482890cb9d13e0" in (
        workflow_text
    )
    assert "SugarSubstitute-Installer-Linux-x86_64.AppImage" in workflow_text
    assert "SugarSubstitute-Installer-Linux-amd64.deb" in workflow_text
    assert "sha256sum --check" in workflow_text


def test_linux_workflows_retry_appimagetool_transport_failures() -> None:
    """Production and validation builds should recover from reset downloads."""

    workflow_paths = (
        PROJECT_ROOT / ".github" / "workflows" / "release.yml",
        PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml",
    )
    for workflow_path in workflow_paths:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        assert "--retry 5 --retry-all-errors --connect-timeout 30" in workflow_text


def test_linux_qt_workflows_install_multimedia_runtime() -> None:
    """Provide PulseAudio wherever Linux imports Qt Multimedia widgets."""

    workflow_paths = (
        PROJECT_ROOT / ".github" / "workflows" / "tests.yml",
        PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml",
        PROJECT_ROOT / ".github" / "workflows" / "native-appearance-screenshots.yml",
    )
    for workflow_path in workflow_paths:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        assert "libpulse0" in workflow["env"]["LINUX_QT_PACKAGES"].split()


def test_large_workflow_artifacts_expire_after_handoff() -> None:
    """Large native build handoffs should not consume long-term Actions storage."""

    workflow_limits = (
        (PROJECT_ROOT / ".github" / "workflows" / "release.yml", 1),
        (
            PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml",
            1,
        ),
        (
            PROJECT_ROOT
            / ".github"
            / "workflows"
            / "native-appearance-screenshots.yml",
            7,
        ),
    )
    for workflow_path, maximum_retention_days in workflow_limits:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        upload_steps = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", ())
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ]
        assert upload_steps
        assert all(
            int(step["with"]["retention-days"]) <= maximum_retention_days
            for step in upload_steps
        )


def test_native_build_workflows_do_not_cache_large_python_wheels() -> None:
    """Native matrices should reinstall dependencies instead of retaining huge caches."""

    workflow_paths = (
        PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml",
        PROJECT_ROOT / ".github" / "workflows" / "native-appearance-screenshots.yml",
    )
    for workflow_path in workflow_paths:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        assert "cache: pip" not in workflow_text


def test_release_publisher_includes_installer_and_managed_payload_artifacts() -> None:
    """Semantic release should attach public installers and managed payloads."""

    config = (PROJECT_ROOT / ".releaserc.cjs").read_text(encoding="utf-8")
    expected_fragments = (
        "SugarSubstitute-*-Windows-x64-Setup.exe",
        "SugarSubstitute-*-macOS-Apple-Silicon.dmg",
        "SugarSubstitute-*-Linux-x86_64.AppImage",
        "SugarSubstitute-*-Linux-amd64.deb",
        "installer-payload-windows-x64-v*.zip",
        "installer-payload-macos-arm64-v*.zip",
        "installer-payload-linux-x64-v*.zip",
    )
    assert all(fragment in config for fragment in expected_fragments)


def test_release_notes_link_directly_to_tagged_platform_installers(
    tmp_path: Path,
) -> None:
    """Release descriptions should route users to immutable installer assets."""

    output_path = tmp_path / "release-notes.md"
    result = subprocess.run(
        [
            "node",
            "scripts/release-notes-preamble.cjs",
            "--repository",
            "Artificial-Sweetener/Substitute-Test",
            "--version",
            "1.2.3",
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
    asset_root = (
        "https://github.com/Artificial-Sweetener/Substitute-Test/"
        "releases/download/v1.2.3"
    )
    assert f"{asset_root}/SugarSubstitute-1.2.3-Windows-x64-Setup.exe" in notes
    assert f"{asset_root}/SugarSubstitute-1.2.3-macOS-Apple-Silicon.dmg" in notes
    assert f"{asset_root}/SugarSubstitute-1.2.3-Linux-x86_64.AppImage" in notes
    assert f"{asset_root}/SugarSubstitute-1.2.3-Linux-amd64.deb" in notes
    icon_root = (
        "https://raw.githubusercontent.com/Artificial-Sweetener/Substitute-Test/"
        "v1.2.3/docs/release/platforms"
    )
    assert "Download the installer for your platform:" in notes
    assert notes.count("<img ") == 3
    assert f'{icon_root}/windows.svg"' in notes
    assert f'{icon_root}/apple.svg"' in notes
    assert f'{icon_root}/linux.svg"' in notes
    assert "Choose the installer for your platform." not in notes
    assert "not notarized" in notes
    assert "checks for application updates when it starts" in notes
    assert "releases/latest/download" not in notes


def test_release_notes_plugin_preserves_conventional_notes() -> None:
    """GitHub guidance should prepend without changing generated history notes."""

    script = """
const context = {
  nextRelease: {version: '1.2.3', notes: '## Features\\n\\n* Added Cubes.'},
};
const publisher = require('./scripts/github-release-publisher.cjs');
const presented = publisher.withInstallerReleaseNotes(
  {repository: 'Artificial-Sweetener/Substitute-Test'},
  context,
);
process.stdout.write(JSON.stringify({
  original: context.nextRelease.notes,
  presented: presented.nextRelease.notes,
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
    notes = json.loads(result.stdout)
    assert notes["presented"].index("## Install SugarSubstitute") < notes[
        "presented"
    ].index("## Features")
    assert notes["presented"].endswith("## Features\n\n* Added Cubes.")
    assert notes["original"] == "## Features\n\n* Added Cubes."


def test_semantic_release_stage_mode_does_not_publish_stable() -> None:
    """Semantic release should prepare its commit and tag while GitHub stays staged."""

    script = """
process.env.SUGAR_SUBSTITUTE_STAGE_ONLY = 'true';
const publisher = require('./scripts/github-release-publisher.cjs');
publisher.publish(
  {repository: 'Artificial-Sweetener/Substitute-Test'},
  {nextRelease: {version: '1.2.3'}},
).then((result) => process.stdout.write(JSON.stringify(result)));
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
    staged = json.loads(result.stdout)
    assert staged["name"] == "Staged SugarSubstitute 1.2.3"
    assert staged["url"].endswith("/releases/tag/v1.2.3")


def test_release_notes_generator_rejects_unsafe_versions(tmp_path: Path) -> None:
    """Release guidance should reject values that could escape the asset URL."""

    output_path = tmp_path / "release-notes.md"
    result = subprocess.run(
        [
            "node",
            "scripts/release-notes-preamble.cjs",
            "--repository",
            "Artificial-Sweetener/Substitute-Test",
            "--version",
            "../unexpected",
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "Expected a semantic release version" in result.stderr
    assert not output_path.exists()


def test_release_pipeline_uses_one_notes_owner_and_updates_the_changelog() -> None:
    """Every release path should share installer notes and conventional history."""

    config = (PROJECT_ROOT / ".releaserc.cjs").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    github_publisher = '"./scripts/github-release-publisher.cjs"'
    conventional_notes = '"@semantic-release/release-notes-generator"'
    changelog_plugin = '"@semantic-release/changelog"'
    assert config.index(conventional_notes) < config.index(changelog_plugin)
    assert config.index(changelog_plugin) < config.index(github_publisher)
    assert 'changelogFile: "CHANGELOG.md"' in config
    assert "release-notes-preamble.cjs" in workflow
    assert "--generate-notes" in workflow
    assert "--notes $releaseNotes" in workflow
    assert (PROJECT_ROOT / "CHANGELOG.md").is_file()


def test_readme_routes_beta_downloads_and_explains_automatic_updates() -> None:
    """Install guidance should route new and returning users appropriately."""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "[Download the latest beta](#install-it)" in readme
    assert "checks for application updates when it starts" in readme
    assert "usually once per day" in readme
    assert "Download the installer for your platform:" not in readme
    assert (
        '### <img src="docs/release/platforms/windows.svg" width="22" '
        'height="22" alt=""> Windows x64'
    ) in readme
    assert (
        '### <img src="docs/release/platforms/apple.svg" width="22" '
        'height="22" alt=""> macOS Apple Silicon'
    ) in readme
    assert (
        '### <img src="docs/release/platforms/linux.svg" width="22" '
        'height="22" alt=""> Linux x64'
    ) in readme
    assert '- <img src="docs/release/platforms/' not in readme


def test_readme_test_badge_tracks_authoritative_main_workflow() -> None:
    """Report the workflow that proves the complete suite on current main."""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    badge = (
        '<a href="https://github.com/Artificial-Sweetener/SugarSubstitute/'
        'actions/workflows/release.yml"><img src="https://img.shields.io/github/'
        "actions/workflow/status/Artificial-Sweetener/SugarSubstitute/"
        'release.yml?branch=main&label=Tests" alt="Test status"></a>'
    )
    assert badge in readme
    assert "actions/workflows/tests.yml/badge.svg" not in readme


def test_all_readme_release_badges_exclude_prereleases() -> None:
    """Release badges must display and navigate only to the latest Stable release."""

    expected_image = (
        "https://img.shields.io/github/v/release/Artificial-Sweetener/SugarSubstitute"
    )
    expected_target = (
        "https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest"
    )
    for readme_path in sorted(PROJECT_ROOT.glob("README*.md")):
        readme = readme_path.read_text(encoding="utf-8")
        release_badge_line = next(
            line for line in readme.splitlines() if expected_image in line
        )

        assert f'href="{expected_target}"' in release_badge_line
        assert f'src="{expected_image}"' in release_badge_line
        assert "include_prereleases" not in release_badge_line


def test_readme_explains_comfy_setup_modes_and_remote_requirements() -> None:
    """Keep setup ownership and remote requirements visible to installers."""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    setup_link = (
        "[choose how SugarSubstitute should use ComfyUI](#choose-your-comfyui-setup)"
    )
    assert readme.count(setup_link) == 3
    assert "### Choose your ComfyUI setup" in readme
    assert "#### Let SugarSubstitute set up ComfyUI" in readme
    assert "#### Use your existing local ComfyUI" in readme
    assert "#### Connect to remote ComfyUI" in readme
    assert "Remote ComfyUI support has not been tested yet." in readme
    assert readme.index("### From a Git clone") < readme.index(
        "### Choose your ComfyUI setup"
    )
    for node_name in (
        "Substitute BackEnd",
        "SugarCubes",
        "ComfyUI Vectorscope CC",
        "ComfyUI SeedVR2 Video Upscaler",
        "SimpleSyrup",
        "ComfyUI Prompt Control",
    ):
        assert f"- [{node_name}]" in readme


def test_release_configuration_targets_the_active_github_repository() -> None:
    """Test and production repositories should release against their active remote."""

    config = (PROJECT_ROOT / ".releaserc.cjs").read_text(encoding="utf-8")

    assert "process.env.GITHUB_REPOSITORY" in config
    assert "process.env.GITHUB_SERVER_URL" in config
    assert "repositoryUrl," in config
    assert "https://github.com/Artificial-Sweetener/SugarSubstitute.git" in config


def test_windows_quality_workflows_fail_fast_on_native_command_errors() -> None:
    """Dependency and gate failures should stop their PowerShell steps immediately."""

    release_workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    test_workflow = (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )

    fail_fast_setting = "$PSNativeCommandUseErrorActionPreference = $true"
    assert release_workflow.count(fail_fast_setting) >= 2
    assert fail_fast_setting in test_workflow


def test_production_python_contains_no_system_git_command() -> None:
    """Supported runtime paths should never execute a system Git binary."""

    offenders: list[str] = []
    for source_root in (PROJECT_ROOT / "substitute", PROJECT_ROOT / "launcher"):
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
                    continue
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value == "git":
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []


def test_installer_sources_do_not_reference_obsolete_comfy_desktop_repository() -> None:
    """Installer implementation should use Comfy-Desktop, never obsolete desktop."""

    source_paths = (
        PROJECT_ROOT / "launcher",
        PROJECT_ROOT / "substitute" / "infrastructure" / "comfy",
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / ".github" / "workflows",
    )
    obsolete_reference = "Comfy-Org/" + "desktop"
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for source_root in source_paths
        for path in source_root.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".js", ".mjs", ".yml", ".yaml"}
        and obsolete_reference in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert offenders == []


def _job_script(job: dict[str, object]) -> str:
    """Combine one workflow job's run scripts for contract assertions."""

    steps = job.get("steps")
    if not isinstance(steps, list):
        return ""
    return "\n".join(
        str(step.get("run", "")) for step in steps if isinstance(step, dict)
    )
