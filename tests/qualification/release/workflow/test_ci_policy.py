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

"""Qualify CI partition, toolchain, and immutable dependency policy."""

from __future__ import annotations

import json
import re

import yaml  # type: ignore[import-untyped]

from tests.qualification.release.workflow.support import (
    DOCUMENTATION_PATH_FILTER,
    EXPECTED_ACTIONS,
    PROJECT_ROOT,
    WORKFLOW_PATHS,
    job_script as workflow_job_script,
    workflow_path,
)


def test_documentation_only_changes_skip_automatic_ci() -> None:
    """Keep Markdown-only pushes and pull requests out of automated gates."""

    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in WORKFLOW_PATHS
    }
    triggers = {name: workflow[True] for name, workflow in workflows.items()}

    assert "push" not in triggers["tests.yml"]
    assert triggers["tests.yml"]["pull_request"]["paths-ignore"] == (
        DOCUMENTATION_PATH_FILTER
    )
    assert triggers["comfy-compatibility.yml"]["push"]["paths-ignore"] == (
        DOCUMENTATION_PATH_FILTER
    )
    assert (
        triggers["comfy-compatibility.yml"]["pull_request"]["paths-ignore"]
        == DOCUMENTATION_PATH_FILTER
    )
    assert triggers["release.yml"]["push"]["paths-ignore"] == (
        DOCUMENTATION_PATH_FILTER
    )


def test_default_ci_runs_complete_partitioned_suite_on_every_platform() -> None:
    """Require every supported operating system to run parallel and serial tests."""

    workflow = yaml.safe_load(
        workflow_path("platform-tests.yml").read_text(encoding="utf-8")
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
    job_script = workflow_job_script(platform_job)
    assert '-m "not serial and not isolated"' in job_script
    assert "tools.ci.run_isolated_test_modules" in job_script
    assert "tools.ci.run_serial_test_modules" in job_script
    assert "--junitxml=" in job_script


def test_ci_uses_exact_language_and_package_toolchains() -> None:
    """Keep every workflow on the shared verified Python and Node toolchains."""

    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in WORKFLOW_PATHS
    }

    python_versions = {
        workflow["env"]["PYTHON_VERSION"]
        for workflow in workflows.values()
        if "PYTHON_VERSION" in workflow.get("env", {})
    }
    linux_versions = {
        workflow["env"]["LINUX_PYTHON_VERSION"]
        for workflow in workflows.values()
        if "LINUX_PYTHON_VERSION" in workflow.get("env", {})
    }
    node_versions = {
        workflow["env"]["NODE_VERSION"]
        for workflow in workflows.values()
        if "NODE_VERSION" in workflow.get("env", {})
    }

    assert python_versions == {"3.12.10"}
    assert linux_versions == {"3.12.13"}
    assert node_versions == {"22.14.0"}
    assert workflows["quality-gates.yml"]["env"]["PYTHON_VERSION"] == "3.12.10"
    assert workflows["platform-tests.yml"]["env"]["LINUX_PYTHON_VERSION"] == ("3.12.13")
    assert workflows["release-version.yml"]["env"]["NODE_VERSION"] == "22.14.0"

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOW_PATHS
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
    for path in WORKFLOW_PATHS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            strategy = job.get("strategy", {})
            matrix = strategy.get("matrix", {})
            for entry in matrix.get("include", ()):
                if "python-version" not in entry:
                    continue
                assert entry["python-version"] == expected_versions[entry["os"]]
                assert "${{" not in entry["python-version"]
                observed_entries += 1

    assert observed_entries == 21


def test_ci_actions_use_immutable_verified_revisions() -> None:
    """Prevent mutable action tags from changing the CI toolchain silently."""

    observed_revisions: dict[str, set[str]] = {}
    for path in WORKFLOW_PATHS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", ()):
                action_reference = step.get("uses", "")
                if not action_reference.startswith("actions/"):
                    continue
                action, revision = action_reference.rsplit("@", maxsplit=1)
                assert re.fullmatch(r"[0-9a-f]{40}", revision)
                observed_revisions.setdefault(action, set()).add(revision)

    assert observed_revisions.keys() == EXPECTED_ACTIONS
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


def test_ci_orchestrators_delegate_to_cohesive_workflow_owners() -> None:
    """Keep event workflows free from platform, packaging, and publication steps."""

    expected_calls = {
        "tests.yml": {
            "./.github/workflows/quality-gates.yml",
            "./.github/workflows/platform-tests.yml",
            "./.github/workflows/dependency-review.yml",
        },
        "comfy-compatibility.yml": {
            "./.github/workflows/comfy-runtime-compatibility.yml",
            "./.github/workflows/comfy-update-compatibility.yml",
        },
        "release.yml": {
            "./.github/workflows/tests.yml",
            "./.github/workflows/release-version.yml",
            "./.github/workflows/release-build.yml",
            "./.github/workflows/release-candidate.yml",
            "./.github/workflows/release-qualification.yml",
            "./.github/workflows/release-publication.yml",
        },
        "cross-platform-validation.yml": {
            "./.github/workflows/tests.yml",
            "./.github/workflows/cross-platform-build.yml",
            "./.github/workflows/linux-system-trust.yml",
            "./.github/workflows/installed-app-smoke.yml",
        },
    }
    for workflow_name, calls in expected_calls.items():
        workflow = yaml.safe_load(
            workflow_path(workflow_name).read_text(encoding="utf-8")
        )
        jobs = workflow["jobs"].values()

        assert {job["uses"] for job in jobs} == calls
        assert all("steps" not in job for job in jobs)


def test_pull_request_runs_share_commit_concurrency() -> None:
    """Updating a pull request must cancel its duplicate test run."""

    workflow = yaml.safe_load(workflow_path("tests.yml").read_text(encoding="utf-8"))
    concurrency = workflow["concurrency"]

    assert "github.event.pull_request.head.sha || github.sha" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is True
