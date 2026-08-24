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

"""Qualify native packaging, release staging, and installer asset contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import yaml  # type: ignore[import-untyped]

from tests.qualification.release.workflow.support import (
    PROJECT_ROOT,
    job_script as workflow_job_script,
    workflow_path,
    workflow_text,
)


def test_cross_platform_validation_proves_packaged_linux_system_trust() -> None:
    """Require the frozen Linux installer to verify releases across distro families."""

    workflow = yaml.safe_load(
        workflow_path("linux-system-trust.yml").read_text(encoding="utf-8")
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
    job_script = workflow_job_script(job)
    assert "--verify-release-connectivity" in job_script
    assert "--manifest-url" in job_script
    assert "APPIMAGE_EXTRACT_AND_RUN=1" in job_script


def test_release_workflow_builds_every_published_platform_after_version_resolution() -> (
    None
):
    """Native builders should share one semantic-release version decision."""

    orchestrator = yaml.safe_load(
        workflow_path("release.yml").read_text(encoding="utf-8")
    )
    build_owner = yaml.safe_load(
        workflow_path("release-build.yml").read_text(encoding="utf-8")
    )
    jobs = orchestrator["jobs"]
    assert set(jobs) == {
        "tests",
        "determine-version",
        "build-release",
        "stage-candidate",
        "qualify-candidate",
        "publish-release",
    }
    assert (
        jobs["determine-version"]["uses"] == "./.github/workflows/release-version.yml"
    )
    assert jobs["build-release"]["uses"] == "./.github/workflows/release-build.yml"
    assert jobs["build-release"]["needs"] == "determine-version"
    for job_name in ("build-windows", "build-macos", "build-linux"):
        assert "inputs.version" in workflow_job_script(build_owner["jobs"][job_name])
    assert build_owner["jobs"]["build-macos"]["runs-on"] == "macos-latest"
    assert build_owner["jobs"]["build-linux"]["runs-on"] == "ubuntu-24.04"
    assert set(jobs["stage-candidate"]["needs"]) == {
        "determine-version",
        "build-release",
    }
    assert jobs["stage-candidate"]["uses"] == (
        "./.github/workflows/release-candidate.yml"
    )
    assert jobs["qualify-candidate"]["uses"] == (
        "./.github/workflows/release-qualification.yml"
    )
    assert set(jobs["publish-release"]["needs"]) == {
        "stage-candidate",
        "qualify-candidate",
    }
    assert jobs["publish-release"]["uses"] == (
        "./.github/workflows/release-publication.yml"
    )


def test_release_stages_then_promotes_the_same_candidate_bytes() -> None:
    """Stable publication must be promotion after qualification, never a rebuild."""

    orchestrator = workflow_text("release.yml")
    candidate = workflow_text("release-candidate.yml")
    publication = workflow_text("release-publication.yml")

    assert "Upload private non-release candidate channel" in candidate
    assert "gh release create" not in candidate
    assert "gh release edit" not in candidate
    assert "release-qualification.yml" in orchestrator
    assert "needs.qualify-candidate.result == 'success'" in orchestrator
    assert "Publish exact qualified Stable release with semantic release" in publication
    assert "prepare-release-assets" not in publication
    assert "PyInstaller" not in publication


def test_first_release_publishes_version_090_without_adding_a_commit() -> None:
    """The flattened root release should publish directly from its existing tree."""

    candidate_text = workflow_text("release-candidate.yml")
    publication_text = workflow_text("release-publication.yml")
    resolver_text = (
        PROJECT_ROOT / "scripts" / "resolve-next-release-version.mjs"
    ).read_text(encoding="utf-8")

    assert 'const FIRST_RELEASE_VERSION = "0.9.0"' in resolver_text
    assert "resolveStableVersion" in resolver_text
    assert "first_release=${firstRelease}" in resolver_text
    assert "prepare-release-assets.mjs" in candidate_text
    assert "npx semantic-release" in publication_text
    assert "prime-first-release-tag" not in candidate_text


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

    build_text = workflow_text("release-build.yml")

    assert "codesign --force --deep --sign -" in build_text
    assert "codesign --verify --deep --strict" in build_text
    assert "secrets.APPLE_" not in build_text
    assert "notarytool" not in build_text
    assert "stapler" not in build_text


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

    build_text = workflow_text("release-build.yml")
    assert "a6d71e2b6cd66f8e8d16c37ad164658985e0cf5fcaa950c90a482890cb9d13e0" in (
        build_text
    )
    assert "SugarSubstitute-Installer-Linux-x86_64.AppImage" in build_text
    assert "SugarSubstitute-Installer-Linux-amd64.deb" in build_text
    assert "sha256sum --check" in build_text


def test_linux_workflows_retry_appimagetool_transport_failures() -> None:
    """Production and validation builds should recover from reset downloads."""

    workflow_paths = (
        workflow_path("release-build.yml"),
        workflow_path("cross-platform-build.yml"),
    )
    for path in workflow_paths:
        owner_text = path.read_text(encoding="utf-8")
        assert "--retry 5 --retry-all-errors --connect-timeout 30" in owner_text


def test_linux_qt_workflows_install_multimedia_runtime() -> None:
    """Provide PulseAudio wherever Linux imports Qt Multimedia widgets."""

    workflow_paths = (
        workflow_path("platform-tests.yml"),
        workflow_path("cross-platform-build.yml"),
        workflow_path("installed-app-smoke.yml"),
        PROJECT_ROOT / ".github" / "workflows" / "native-appearance-screenshots.yml",
    )
    for path in workflow_paths:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "libpulse0" in workflow["env"]["LINUX_QT_PACKAGES"].split()


def test_large_workflow_artifacts_expire_after_handoff() -> None:
    """Large native build handoffs should not consume long-term Actions storage."""

    workflow_limits = (
        (workflow_path("release-build.yml"), 1),
        (workflow_path("release-candidate.yml"), 1),
        (
            workflow_path("cross-platform-build.yml"),
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
    for path, maximum_retention_days in workflow_limits:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        workflow_path("cross-platform-build.yml"),
        PROJECT_ROOT / ".github" / "workflows" / "native-appearance-screenshots.yml",
    )
    for path in workflow_paths:
        owner_text = path.read_text(encoding="utf-8")
        assert "cache: pip" not in owner_text


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
