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

"""Qualify deterministic dependency environments and disposable CI caches."""

from __future__ import annotations

import re
from typing import cast

import yaml  # type: ignore[import-untyped]

from tests.qualification.release.workflow.support import (
    PROJECT_ROOT,
    WORKFLOW_PATHS,
    action_path,
)


_PYTHON_CONSUMERS = {
    "comfy-pin-update.yml",
    "comfy-runtime-compatibility.yml",
    "comfy-update-compatibility.yml",
    "cross-platform-build.yml",
    "installed-app-smoke.yml",
    "managed-comfy-install.yml",
    "native-appearance-screenshots.yml",
    "platform-tests.yml",
    "quality-gates.yml",
    "release-build.yml",
    "release-current-install-qualification.yml",
    "release-update-qualification.yml",
}
_NODE_CONSUMERS = {
    "cross-platform-build.yml",
    "quality-gates.yml",
    "release-build.yml",
    "release-candidate.yml",
    "release-publication.yml",
    "release-version.yml",
}
_LINUX_QT_CONSUMERS = {
    "cross-platform-build.yml",
    "installed-app-smoke.yml",
    "native-appearance-screenshots.yml",
    "platform-tests.yml",
    "release-current-install-qualification.yml",
    "release-update-qualification.yml",
}
_MANAGED_CACHE_CONSUMERS = {
    "managed-comfy-install.yml",
    "release-current-install-qualification.yml",
}
_LINUX_QT_PACKAGES = {
    "libegl1",
    "libfontconfig1",
    "libgl1",
    "libpulse0",
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-util1",
    "libxcb-xkb1",
    "libxkbcommon-x11-0",
    "libxkbcommon0",
    "xvfb",
}
_TRUSTED_CACHE_EVENTS = ("push", "workflow_dispatch", "repository_dispatch", "schedule")
_DIRECT_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^;\s]+)")


def _action(name: str) -> dict[str, object]:
    """Load one local action owner."""

    return cast(
        dict[str, object],
        yaml.safe_load(action_path(name).read_text(encoding="utf-8")),
    )


def _steps(action: dict[str, object]) -> list[dict[str, object]]:
    """Return typed composite action steps."""

    runs = action["runs"]
    assert isinstance(runs, dict)
    steps = runs["steps"]
    assert isinstance(steps, list)
    return steps


def _step(action: dict[str, object], name: str) -> dict[str, object]:
    """Return one named composite action step."""

    return next(step for step in _steps(action) if step["name"] == name)


def _workflow_consumers(action_reference: str) -> set[str]:
    """Return workflows delegating to one local environment owner."""

    return {
        path.name
        for path in WORKFLOW_PATHS
        if action_reference in path.read_text(encoding="utf-8")
    }


def _assert_trusted_cache_policy(
    action: dict[str, object],
    trusted_step_name: str,
    untrusted_step_name: str,
) -> None:
    """Require allowlisted writes and restore-only untrusted cache access."""

    trusted = _step(action, trusted_step_name)
    untrusted = _step(action, untrusted_step_name)
    trusted_if = str(trusted["if"])
    untrusted_if = str(untrusted["if"])

    assert trusted["uses"] == ("actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae")
    assert untrusted["uses"] == (
        "actions/cache/restore@27d5ce7f107fe9357f9df03efb73ab90386fccae"
    )
    for event in _TRUSTED_CACHE_EVENTS:
        assert f"github.event_name == '{event}'" in trusted_if
        assert f"github.event_name != '{event}'" in untrusted_if
    assert "pull_request" not in trusted_if


def test_python_environment_owner_has_complete_consumers() -> None:
    """Keep dependency-bearing jobs on the single verified Python owner."""

    assert _workflow_consumers("./.github/actions/setup-python-toolchain") == (
        _PYTHON_CONSUMERS
    )
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOW_PATHS
    )
    assert "python -m venv" not in workflow_text
    assert "pip install" not in workflow_text
    direct_setup_owners = {
        path.name
        for path in WORKFLOW_PATHS
        if "actions/setup-python@" in path.read_text(encoding="utf-8")
    }
    assert direct_setup_owners == {"release-qualification.yml"}

    for path in WORKFLOW_PATHS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            steps = job.get("steps", ())
            command_text = "\n".join(str(step.get("run", "")) for step in steps)
            if re.search(
                r"(?<![\w.-])(?:python|pip|uv)(?:\.exe)?(?:\s|$)",
                command_text,
                re.IGNORECASE,
            ):
                assert any(
                    "setup-python" in str(step.get("uses", "")) for step in steps
                ), path.name


def test_python_cache_identity_covers_every_compatibility_input() -> None:
    """Separate package caches by every runtime and runner compatibility input."""

    action = _action("setup-python-toolchain")
    identity = str(_step(action, "Resolve package-cache identity")["run"])

    for fragment in (
        "$env:CACHE_EPOCH",
        "$env:CACHE_SCOPE",
        "${{ runner.os }}",
        "${{ runner.arch }}",
        "$env:ImageOS",
        "$env:ImageVersion",
        "$env:PYTHON_VERSION",
        "uv0.12.3",
        "$lockHash",
    ):
        assert fragment in identity
    assert '"restore-key=$prefix-"' in identity
    assert '"primary-key=$prefix-$lockHash"' in identity


def test_python_cache_writes_are_trusted_and_untrusted_restores_are_read_only() -> None:
    """Prevent externally influenced jobs from publishing trusted cache state."""

    action = _action("setup-python-toolchain")
    _assert_trusted_cache_policy(
        action,
        "Restore trusted package cache",
        "Restore untrusted package cache read-only",
    )


def test_python_environment_is_fresh_exact_and_cache_recoverable() -> None:
    """Recreate exact environments and recover only from disposable cache damage."""

    action = _action("setup-python-toolchain")
    sync = _step(action, "Synchronize fresh verified environment")
    script = str(sync["run"])

    assert "uv venv --clear" in script
    assert "uv pip sync" in script
    assert "--require-hashes --strict" in script
    assert "--no-python-downloads" in script
    assert '$env:CACHE_RESTORED -eq "true"' in script
    assert "uv cache clean" in script
    assert "--refresh" in script
    assert "uv pip check" in script
    assert ".venv" not in str(_step(action, "Restore trusted package cache")["with"])

    cache_result = str(_step(action, "Record package-cache result")["run"])
    assert ".sugarsubstitute-verified-cache-v1" in cache_result
    assert "$cacheRestored = $exactHit -or" in cache_result
    assert "Get-ChildItem" not in cache_result


def test_node_environment_owner_uses_exact_clean_lock_installation() -> None:
    """Keep release packages on one lock-addressed Node owner."""

    assert _workflow_consumers("./.github/actions/setup-node-toolchain") == (
        _NODE_CONSUMERS
    )
    action = _action("setup-node-toolchain")
    setup = _step(action, "Set up exact hosted Node.js")
    install = _step(action, "Install exact release dependencies")

    assert setup["uses"] == (
        "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020"
    )
    setup_inputs = setup["with"]
    assert isinstance(setup_inputs, dict)
    assert "inputs.install-dependencies == 'true'" in str(setup_inputs["cache"])
    assert "'npm'" in str(setup_inputs["cache"])
    assert "inputs.install-dependencies == 'true'" in str(
        setup_inputs["cache-dependency-path"]
    )
    assert "'package-lock.json'" in str(setup_inputs["cache-dependency-path"])
    install_script = str(install["run"])
    assert "packageManager" in install_script
    assert "npm@$(corepack npm --version)" in install_script
    assert "corepack npm ci" in install_script
    assert "node_modules" not in action_path("setup-node-toolchain").read_text(
        encoding="utf-8"
    )

    for path in WORKFLOW_PATHS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            steps = job.get("steps", ())
            command_text = "\n".join(str(step.get("run", "")) for step in steps)
            if re.search(r"\b(?:node|npm|npx)\b", command_text):
                assert any(
                    step.get("uses") == "./.github/actions/setup-node-toolchain"
                    for step in steps
                ), path.name


def test_linux_qt_owner_skips_complete_runner_images() -> None:
    """Own the native Qt package set and avoid redundant package-manager work."""

    assert _workflow_consumers("./.github/actions/setup-linux-qt") == (
        _LINUX_QT_CONSUMERS
    )
    action = _action("setup-linux-qt")
    install_script = str(
        _step(action, "Install missing Linux Qt runtime packages")["run"]
    )
    package_block = install_script.split("packages=(", maxsplit=1)[1].split(
        ")", maxsplit=1
    )[0]
    assert set(package_block.split()) == _LINUX_QT_PACKAGES
    assert "dpkg-query" in install_script
    assert "missing_packages" in install_script
    assert "apt-get update" in install_script
    assert 'apt-get install -y "${missing_packages[@]}"' in install_script

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOW_PATHS
    )
    assert "LINUX_QT_PACKAGES" not in workflow_text
    assert "sudo apt-get update" not in workflow_text


def test_managed_runtime_cache_has_one_secure_checksum_owner() -> None:
    """Keep managed-runtime dependency reuse exact and untrusted read-only."""

    assert _workflow_consumers("./.github/actions/restore-managed-comfy-cache") == (
        _MANAGED_CACHE_CONSUMERS
    )
    action = _action("restore-managed-comfy-cache")
    identity = str(_step(action, "Resolve managed-runtime cache identity")["run"])
    for fragment in (
        "$env:CACHE_EPOCH",
        "${{ runner.os }}",
        "${{ runner.arch }}",
        "$variant",
        "$pinHash",
    ):
        assert fragment in identity
    assert '"restore-key=$prefix-"' in identity
    assert '"primary-key=$prefix-$pinHash"' in identity
    _assert_trusted_cache_policy(
        action,
        "Restore trusted managed-runtime cache",
        "Restore untrusted managed-runtime cache read-only",
    )

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOW_PATHS
    )
    assert "uses: actions/cache@" not in workflow_text
    assert "uses: actions/cache/restore@" not in workflow_text


def test_python_locks_cover_direct_requirements_with_hashes() -> None:
    """Keep every declared direct dependency exact in its generated lock."""

    profiles = (
        (
            ("requirements.txt", "requirements-toolchain.txt"),
            "requirements-toolchain.txt",
            "requirements-toolchain.lock",
        ),
        (
            ("requirements-automation.txt",),
            "requirements-automation.txt",
            "requirements-automation.lock",
        ),
    )
    for source_names, compiled_source, lock_name in profiles:
        source = "\n".join(
            (PROJECT_ROOT / source_name).read_text(encoding="utf-8")
            for source_name in source_names
        )
        lock = (PROJECT_ROOT / lock_name).read_text(encoding="utf-8")
        locked_versions = _locked_versions(lock)
        direct_versions = {
            match.group(1).lower().replace("_", "-"): match.group(2)
            for line in source.splitlines()
            if (match := _DIRECT_REQUIREMENT.match(line)) is not None
        }

        assert direct_versions.items() <= locked_versions.items()
        assert f"uv pip compile {compiled_source} --universal --generate-hashes" in lock
        _assert_every_locked_requirement_has_a_hash(lock)


def _locked_versions(lock: str) -> dict[str, str]:
    """Return canonical locked package versions."""

    return {
        match.group(1).lower().replace("_", "-"): match.group(2)
        for line in lock.splitlines()
        if (match := _DIRECT_REQUIREMENT.match(line)) is not None
    }


def _assert_every_locked_requirement_has_a_hash(lock: str) -> None:
    """Require at least one distribution hash for every locked package block."""

    lines = lock.splitlines()
    requirement_indexes = [
        index
        for index, line in enumerate(lines)
        if _DIRECT_REQUIREMENT.match(line) is not None
    ]
    for position, start in enumerate(requirement_indexes):
        end = (
            requirement_indexes[position + 1]
            if position + 1 < len(requirement_indexes)
            else len(lines)
        )
        assert any("--hash=sha256:" in line for line in lines[start:end])


def test_dependency_caches_exclude_release_and_sensitive_state() -> None:
    """Limit persistent cache paths to exact disposable dependency inputs."""

    python_action = _action("setup-python-toolchain")
    cache_inputs = _step(python_action, "Restore trusted package cache")["with"]
    assert isinstance(cache_inputs, dict)
    assert cache_inputs == {
        "path": "${{ steps.cache-path.outputs.path }}",
        "key": "${{ steps.identity.outputs.primary-key }}",
        "restore-keys": "${{ steps.identity.outputs.restore-key }}",
    }
    cached_path = str(cache_inputs["path"])
    forbidden = (
        ".venv",
        "node_modules",
        ".local-release-channel",
        "build/release",
        "artifact",
        "candidate",
        "credential",
        "secret",
        "signing",
    )

    assert all(fragment not in cached_path.lower() for fragment in forbidden)

    managed_action = _action("restore-managed-comfy-cache")
    managed_inputs = managed_action["inputs"]
    assert isinstance(managed_inputs, dict)
    managed_path = managed_inputs["cache-path"]
    assert isinstance(managed_path, dict)
    assert managed_path["default"] == "build/managed-comfy-cache"
    assert all(
        fragment not in str(managed_path["default"]).lower() for fragment in forbidden
    )
