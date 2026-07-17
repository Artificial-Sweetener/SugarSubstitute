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
import subprocess

import yaml  # type: ignore[import-untyped]


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
        "quality",
        "determine-version",
        "build-windows",
        "build-macos",
        "build-linux",
        "release",
    }
    for job_name in ("build-windows", "build-macos", "build-linux"):
        job = jobs[job_name]
        assert job["needs"] == "determine-version"
        assert "needs.determine-version.outputs.version" in _job_script(job)
    assert jobs["build-macos"]["runs-on"] == "macos-latest"
    assert jobs["build-linux"]["runs-on"] == "ubuntu-24.04"
    assert set(jobs["release"]["needs"]) == {
        "determine-version",
        "build-windows",
        "build-macos",
        "build-linux",
    }


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


def test_pyinstaller_specs_share_virtual_environment_uv_discovery() -> None:
    """Every native launcher build should resolve uv through one owner."""

    spec_paths = tuple((PROJECT_ROOT / "launcher").glob("*.spec"))

    assert len(spec_paths) == 7
    for spec_path in spec_paths:
        spec_text = spec_path.read_text(encoding="utf-8")
        assert (
            "from tools.pyinstaller_support import resolve_uv_executable" in spec_text
        )
        assert "uv_path = resolve_uv_executable()" in spec_text
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
            for step in job["steps"]
            if step.get("uses") == "actions/upload-artifact@v6"
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
        "Installer-Windows-x64.exe",
        "Installer-macOS-Apple-Silicon.dmg",
        "Installer-Linux-x86_64.AppImage",
        "Installer-Linux-amd64.deb",
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
    assert f"{asset_root}/SugarSubstitute-Installer-Windows-x64.exe" in notes
    assert f"{asset_root}/SugarSubstitute-Installer-macOS-Apple-Silicon.dmg" in notes
    assert f"{asset_root}/SugarSubstitute-Installer-Linux-x86_64.AppImage" in notes
    assert f"{asset_root}/SugarSubstitute-Installer-Linux-amd64.deb" in notes
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
