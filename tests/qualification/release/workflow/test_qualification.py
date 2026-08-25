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

"""Qualify release candidate and managed-Comfy qualification boundaries."""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]

from tests.qualification.release.workflow.support import (
    PROJECT_ROOT,
    action_path,
    workflow_path,
    workflow_text,
)


def test_prepublication_burn_in_is_complete_and_structurally_read_only() -> None:
    """Exercise every release gate without exposing a publication call path."""

    burn_in = yaml.safe_load(workflow_text("cross-platform-validation.yml"))
    production = yaml.safe_load(workflow_text("release.yml"))
    prepublication_text = workflow_text("release-prepublication.yml")
    burn_in_text = workflow_text("cross-platform-validation.yml")
    jobs = burn_in["jobs"]

    assert burn_in["name"] == "release prepublication burn-in"
    assert not workflow_path("validation-release-cleanup.yml").exists()
    assert burn_in["permissions"] == {"actions": "read", "contents": "read"}
    assert production["jobs"]["prepare-release"]["uses"] == (
        "./.github/workflows/release-prepublication.yml"
    )
    assert jobs["stable-prepublication"]["uses"] == (
        "./.github/workflows/release-prepublication.yml"
    )
    assert jobs["canary-prepublication"]["uses"] == (
        "./.github/workflows/release-prepublication.yml"
    )
    stable_inputs = jobs["stable-prepublication"]["with"]
    canary_inputs = jobs["canary-prepublication"]["with"]
    assert stable_inputs["run_tests"] is True
    assert stable_inputs["force_candidate"] is True
    assert stable_inputs["qualification_scope"] == "all"
    assert canary_inputs["run_tests"] is False
    assert canary_inputs["force_candidate"] is True
    assert canary_inputs["qualification_scope"] == "canary-fast"
    assert (
        stable_inputs["candidate_artifact_name"]
        != (canary_inputs["candidate_artifact_name"])
    )
    assert (
        stable_inputs["release_input_artifact_suffix"]
        != (canary_inputs["release_input_artifact_suffix"])
    )
    assert "./.github/workflows/comfy-runtime-compatibility.yml" in burn_in_text
    assert "./.github/workflows/comfy-update-compatibility.yml" in burn_in_text
    assert "release-publication.yml" not in burn_in_text
    assert "release-publication.yml" not in prepublication_text
    assert "contents: write" not in burn_in_text
    assert "contents: write" not in prepublication_text
    assert "secrets: inherit" not in burn_in_text


def test_prepublication_downstream_proof_consumes_the_exact_stable_candidate() -> None:
    """Keep trust and installed-app proof attached to the qualified Stable bytes."""

    burn_in = yaml.safe_load(workflow_text("cross-platform-validation.yml"))
    jobs = burn_in["jobs"]
    for job_name in ("linux-system-trust", "installed-app-smoke"):
        job = jobs[job_name]
        assert job["needs"] == "stable-prepublication"
        assert job["with"]["candidate_artifact_name"] == (
            "${{ needs.stable-prepublication.outputs.candidate_artifact_name }}"
        )
        assert job["with"]["candidate_run_id"] == (
            "${{ needs.stable-prepublication.outputs.candidate_run_id }}"
        )

    installed_text = workflow_text("installed-app-smoke.yml")
    trust_text = workflow_text("linux-system-trust.yml")
    for owner_text in (installed_text, trust_text):
        assert "run-id: ${{ inputs.candidate_run_id }}" in owner_text
        assert "github-token: ${{ github.token }}" in owner_text
    assert "build/candidate" in trust_text
    assert "${CANDIDATE_VERSION}-Linux-x86_64.AppImage" in trust_text
    assert not workflow_path("cross-platform-build.yml").exists()


def test_cross_platform_validation_requires_explicit_invocation() -> None:
    """Keep manual validation private and behind an explicit dispatch."""

    orchestrator_text = (
        PROJECT_ROOT / ".github" / "workflows" / "cross-platform-validation.yml"
    ).read_text(encoding="utf-8")
    validation_text = workflow_text(
        "cross-platform-validation.yml",
        "release-prepublication.yml",
        "release-build.yml",
        "release-candidate.yml",
        "release-qualification.yml",
        "linux-system-trust.yml",
        "installed-app-smoke.yml",
    )

    assert "  workflow_dispatch:" in orchestrator_text
    assert "  push:" not in orchestrator_text
    assert "contents: write" not in validation_text
    assert "gh release create" not in validation_text
    assert "gh release edit" not in validation_text
    assert "prepublication-stable-candidate" in validation_text
    assert "prepublication-canary-candidate" in validation_text
    assert "candidate_artifact_name" in validation_text


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
    """Cold compatibility should qualify every supported managed runtime."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "managed-comfy-install.yml"
    ).read_text(encoding="utf-8")
    cache_owner_text = action_path("restore-managed-comfy-cache").read_text(
        encoding="utf-8"
    )

    assert "./.github/actions/restore-managed-comfy-cache" in workflow_text
    assert "variant: win-cpu" in workflow_text
    assert "variant: linux-nvidia" in workflow_text
    assert "variant: mac-mps" in workflow_text
    assert workflow_text.count("${{ matrix.variant }}") == 2
    assert "windows-latest" in workflow_text
    assert "ubuntu-24.04" in workflow_text
    assert "macos-15" in workflow_text
    assert "actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae" in (
        cache_owner_text
    )
    assert "standalone_environment_pin.json" in cache_owner_text
    assert "verify_managed_comfy_install.py" in workflow_text
    assert '--variant "${{ matrix.variant }}"' in workflow_text
    assert "pip install torch" not in workflow_text


def test_managed_comfy_cold_proof_is_change_triggered_and_scheduled() -> None:
    """Keep the required check fast while selecting compatibility reconstruction."""

    workflow_text = (
        PROJECT_ROOT / ".github" / "workflows" / "managed-comfy-install.yml"
    ).read_text(encoding="utf-8")
    pull_request_trigger = workflow_text.split("  pull_request:", maxsplit=1)[1].split(
        "  schedule:", maxsplit=1
    )[0]
    selection = workflow_text.split("  select-cold-runtime:", maxsplit=1)[1].split(
        "  cold-runtime:", maxsplit=1
    )[0]

    assert "    branches:\n      - main\n      - canary\n" in pull_request_trigger
    assert "paths:" not in pull_request_trigger
    for owner in (
        "standalone_environment_pin",
        "substitute/infrastructure/comfy/standalone_environment/",
        "verify_managed_comfy_install",
        "restore-managed-comfy-cache/",
    ):
        assert owner in selection
    assert 'cron: "17 8 * * 1"' in workflow_text
    assert "pull-requests: read" not in workflow_text
    assert "compare/$env:BASE_SHA...$env:HEAD_SHA" in workflow_text
    assert "CHANGED_FILE_COUNT -gt 300" in workflow_text
    assert "needs.select-cold-runtime.outputs.enabled == 'true'" in workflow_text
    assert "name: Pinned managed Comfy (Windows CPU)" in workflow_text
    assert "if: always()" in workflow_text
    assert 'COLD_ENABLED -eq "true"' in workflow_text


def test_release_qualification_covers_clean_launch_and_upgrade_depth() -> None:
    """Release candidates must prove exact installers before stable promotion."""

    orchestration_text = workflow_text("release-qualification.yml")
    current_text = workflow_text("release-current-install-qualification.yml")
    update_text = workflow_text("release-update-qualification.yml")
    qualification_text = workflow_text(
        "release-qualification.yml",
        "release-current-install-qualification.yml",
        "release-update-qualification.yml",
    )
    assert "verify_installer_lifecycle.py clean" in current_text
    assert "verify_installer_lifecycle.py upgrade" in update_text
    assert "python -m tools.ci.resolve_upgrade_sources" in orchestration_text
    assert '--historical-published-at "${{ matrix.history.published_at }}"' in (
        update_text
    )
    assert "Windows x64" in orchestration_text
    assert "Linux x64" in orchestration_text
    assert "macOS Apple Silicon" in current_text
    assert '@("windows", "linux", "macos")' in orchestration_text
    assert "update_platforms" in orchestration_text
    assert "./.github/workflows/managed-comfy-install.yml" in orchestration_text
    assert '$managedComfyEnabled = if ($scope -eq "managed-comfy")' in (
        orchestration_text
    )
    assert '$scope -in @("all", "managed-comfy")' not in orchestration_text
    assert "gh release edit" not in qualification_text
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
    assert "Download real historical installer" in update_text
    assert '"SugarSubstitute-*-Windows-x64*.exe"' in update_text
    assert '"SugarSubstitute-*-Windows-x64.exe"' not in update_text
    assert '"SugarSubstitute-*-Linux-x86_64.AppImage"' in update_text
    assert '"SugarSubstitute-*-macOS-Apple-Silicon.dmg"' in update_text
    assert "Reconstitute exact historical macOS install channel" in update_text
    assert "python -m tools.ci.reconstitute_historical_macos_release" in update_text
    assert qualification_text.count("QT_QPA_PLATFORM: cocoa") == 2
    assert (
        "QT_QPA_PLATFORM: ${{ matrix.platform == 'macos' && 'cocoa' || 'offscreen' }}"
    ) in update_text
    assert '"--historical-release-root"' in update_text
    assert '--candidate-installer "$env:CANDIDATE_INSTALLER"' in update_text
    assert "CANDIDATE_INSTALLER=" in update_text
    assert "Build version-pinned historical Windows setup" not in update_text
    assert "SugarSubstitute-Local-Test-Installer" not in update_text


def test_release_dry_run_qualifies_temporary_bytes_without_publishing() -> None:
    """Manual dry runs should exercise release qualification without a release."""

    release_text = workflow_text("release.yml")
    version_text = workflow_text("release-version.yml")
    candidate_text = workflow_text("release-candidate.yml")
    qualification_text = workflow_text(
        "release-qualification.yml",
        "release-current-install-qualification.yml",
        "release-update-qualification.yml",
    )
    current_install_text = workflow_text("release-current-install-qualification.yml")
    preparation_text = (
        PROJECT_ROOT / "scripts" / "prepare-release-assets.mjs"
    ).read_text(encoding="utf-8")

    assert "SUGAR_SUBSTITUTE_ASSET_BASE_URL" not in candidate_text
    assert "Prepare private release candidate assets" in candidate_text
    assert "include-hidden-files: true" in candidate_text
    assert "SUGAR_SUBSTITUTE_QUALIFICATION_VERSION:" in version_text
    assert "format('9999.0.{0}', github.run_number)" in release_text
    assert 'default: "non-release-candidate-channel"' in candidate_text
    assert "candidate_artifact_name:" in candidate_text
    assert 'default: "non-release-candidate-channel"' in release_text
    assert (
        "candidate_artifact_name: ${{ inputs.candidate_artifact_name || "
        "'non-release-candidate-channel' }}"
    ) in release_text
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
    assert qualification_text.count("timeout-minutes: 30") == 2
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
    assert current_install_text.count(".candidate-certificate/requests.jsonl") == 2
    assert "Restore checksum-addressed standalone artifact" not in qualification_text
    assert "cache_managed_comfy_artifacts.py" not in qualification_text
    assert "standalone_variant" not in qualification_text
    assert "--managed-artifact-cache-root" not in qualification_text
    assert "appdata/runtime_state/setup_transaction.json" not in qualification_text
    assert ".SugarSubstitute-clean-standalone-cache.json" not in qualification_text
    lifecycle_text = (
        PROJECT_ROOT / "tools" / "ci" / "verify_installer_lifecycle.py"
    ).read_text(encoding="utf-8")
    shell_evidence_text = (
        PROJECT_ROOT / "tools" / "ci" / "installer_ui_qualification.py"
    ).read_text(encoding="utf-8")
    assert 'target_mode="remote"' in lifecycle_text
    assert "require_governed_setup_record=False" in lifecycle_text
    assert "assert_real_managed_comfy" in shell_evidence_text
    assert 'evidence.plan.target_mode == "managed_local"' in shell_evidence_text


def test_focused_release_qualification_cannot_skip_publishing_gates() -> None:
    """Only manual non-publishing runs may bypass unchanged repository gates."""

    release_text = workflow_text("release.yml")
    prepublication_text = workflow_text("release-prepublication.yml")
    version_text = workflow_text("release-version.yml")
    candidate_text = workflow_text("release-candidate.yml")
    publication_text = workflow_text("release-publication.yml")
    qualification_text = workflow_text("release-qualification.yml")
    update_text = workflow_text("release-update-qualification.yml")

    prepare_call = release_text.split("  prepare-release:", maxsplit=1)[1].split(
        "  publish-release:", maxsplit=1
    )[0]
    assert "github.event_name != 'workflow_dispatch'" in prepare_call
    assert "github.event.inputs.dry_run != 'true'" in prepare_call
    assert "github.event.inputs.qualification_scope == 'full'" in prepare_call
    assert "if: inputs.run_tests" in prepublication_text
    assert (
        "candidate_run_id: ${{ needs.stage-candidate.outputs.candidate_run_id }}"
        in prepublication_text
    )
    assert "      actions: read\n      contents: write" in release_text
    assert "permissions:\n  actions: read\n  contents: write" in publication_text
    assert "steps.release-version.outputs.should_release" in version_text
    assert "steps.release-version.outputs.should_release ||" not in version_text
    assert "format('9999.0.{0}', github.run_number)" in release_text
    assert "release_input_run_id:" in release_text
    assert "qualification_candidate_run_id:" in release_text
    assert "qualification_candidate_version:" in release_text
    assert "inputs.release_input_run_id != ''" in prepublication_text
    assert (
        "run-id: ${{ inputs.release_input_run_id || github.run_id }}" in candidate_text
    )
    assert "needs.stage-candidate.result == 'success'" in prepublication_text
    assert "Reuse exact temporary candidate channel" in candidate_text
    assert "needs.stage-candidate.outputs.candidate_run_id" in prepublication_text
    assert "inputs.qualification_candidate_version ||" in prepublication_text
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
    assert "run-id: ${{ inputs.candidate_run_id" in update_text
    assert "managed_comfy_enabled" in qualification_text
