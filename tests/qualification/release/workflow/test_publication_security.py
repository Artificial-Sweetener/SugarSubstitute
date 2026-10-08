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

"""Qualify publication guidance, repository configuration, and release security."""

from __future__ import annotations

from pathlib import Path

from tests.qualification.release.workflow.support import (
    PROJECT_ROOT,
    action_path,
    workflow_text,
)
from tests.support.execution.node_runtime import run_node


def test_release_notes_generator_rejects_unsafe_versions(tmp_path: Path) -> None:
    """Release guidance should reject values that could escape the asset URL."""

    output_path = tmp_path / "release-notes.md"
    result = run_node(
        (
            "scripts/release-notes-preamble.cjs",
            "--repository",
            "Artificial-Sweetener/Substitute-Test",
            "--version",
            "../unexpected",
            "--output",
            str(output_path),
        ),
        cwd=PROJECT_ROOT,
        timeout_seconds=30,
        check=False,
    )

    assert result.returncode != 0
    assert "Expected a release version" in result.stderr
    assert not output_path.exists()


def test_release_pipeline_uses_one_notes_owner_and_updates_the_changelog() -> None:
    """Every release path should share installer notes and conventional history."""

    config = (PROJECT_ROOT / "scripts" / "prepare-stable-release.mjs").read_text(
        encoding="utf-8"
    )
    candidate_workflow = workflow_text("release-candidate.yml")
    publication_workflow = workflow_text("release-publication.yml")

    assert "generateReleaseNotes(commits" in config
    assert "createInstallerReleaseNotes(repository, version)" in config
    assert 'join(root, "CHANGELOG.md")' in config
    assert "release-notes-preamble.cjs" in candidate_workflow
    assert "node scripts/publish-stable-release.mjs" in publication_workflow
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
    assert "Linux and macOS — temporarily suspended" in readme
    assert "no restart date yet" in readme
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

    release_badge_endpoint = (
        "https://img.shields.io/github/v/release/Artificial-Sweetener/SugarSubstitute"
    )
    expected_image = f"{release_badge_endpoint}?filter=v%2A"
    expected_target = (
        "https://github.com/Artificial-Sweetener/SugarSubstitute/releases/latest"
    )
    for readme_path in sorted(PROJECT_ROOT.glob("README*.md")):
        readme = readme_path.read_text(encoding="utf-8")
        release_badge_line = next(
            line for line in readme.splitlines() if release_badge_endpoint in line
        )

        assert f'href="{expected_target}"' in release_badge_line
        assert f'src="{expected_image}"' in release_badge_line
        assert f'src="{release_badge_endpoint}"' not in release_badge_line


def test_readme_explains_comfy_setup_modes_and_remote_requirements() -> None:
    """Keep setup ownership and remote requirements visible to installers."""

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    setup_link = (
        "[choose how SugarSubstitute should use ComfyUI](#choose-your-comfyui-setup)"
    )
    assert readme.count(setup_link) == 1
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

    config = (PROJECT_ROOT / "scripts" / "publish-stable-release.mjs").read_text(
        encoding="utf-8"
    )

    assert "process.env.GITHUB_REPOSITORY" in config
    assert "process.env.GITHUB_SERVER_URL" in config
    assert 'repository: process.env.GITHUB_REPOSITORY ?? ""' in config


def test_stable_release_push_uses_the_authorized_deploy_key() -> None:
    """Keep generated Stable commits on the narrowly authorized push identity."""

    publication_workflow = workflow_text("release-publication.yml")
    release_config = (
        PROJECT_ROOT / "scripts" / "publish-stable-release.mjs"
    ).read_text(encoding="utf-8")

    assert "Configure authorized Stable release push" in publication_workflow
    assert "secrets.STABLE_RELEASE_DEPLOY_KEY" in publication_workflow
    assert "SUGAR_SUBSTITUTE_RELEASE_REPOSITORY_URL:" in publication_workflow
    assert "git@github.com:${{ github.repository }}.git" in publication_workflow
    assert "process.env.SUGAR_SUBSTITUTE_RELEASE_REPOSITORY_URL" in release_config


def test_stable_release_commits_are_attributed_to_daisy() -> None:
    """Keep generated release authorship independent of deploy-key authentication."""

    publication_workflow = workflow_text("release-publication.yml")
    publish_step = publication_workflow.split(
        "      - name: Publish exact qualified Stable release",
        maxsplit=1,
    )[1].split("      - name:", maxsplit=1)[0]

    assert "GIT_AUTHOR_NAME: Daisy" in publish_step
    assert "GIT_AUTHOR_EMAIL: daisy@artificialsweetener.ai" in publish_step
    assert "GIT_COMMITTER_NAME: Daisy" in publish_step
    assert "GIT_COMMITTER_EMAIL: daisy@artificialsweetener.ai" in publish_step


def test_failed_qualification_cannot_leave_a_public_stable_prerelease() -> None:
    """Keep every Stable tag and release mutation after successful qualification."""

    orchestrator = workflow_text("release.yml", "release-prepublication.yml")
    candidate_workflow = workflow_text("release-candidate.yml")
    publication_workflow = workflow_text("release-publication.yml")

    assert "contents: write" not in candidate_workflow
    assert "gh release create" not in candidate_workflow
    assert "gh release edit" not in candidate_workflow
    assert "publish-stable-release.mjs" not in candidate_workflow
    publish_call = workflow_text("release.yml").split("  publish-release:", maxsplit=1)[
        1
    ]
    assert "needs.prepare-release.result == 'success'" in publish_call
    assert "needs.prepare-release.outputs.staged == 'true'" in publish_call
    assert "qualify-candidate:" in orchestrator
    assert publish_call.index("contents: write") < publish_call.index(
        "./.github/workflows/release-publication.yml"
    )
    assert "Publish exact qualified Stable release" in (publication_workflow)


def test_windows_quality_workflows_fail_fast_on_native_command_errors() -> None:
    """Dependency and gate failures should stop their PowerShell steps immediately."""

    owner_text = workflow_text(
        "release-build.yml",
        "release-candidate.yml",
        "quality-gates.yml",
    )
    node_owner_text = action_path("setup-node-toolchain").read_text(encoding="utf-8")

    fail_fast_setting = "$PSNativeCommandUseErrorActionPreference = $true"
    assert fail_fast_setting in owner_text
    assert fail_fast_setting in node_owner_text


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
