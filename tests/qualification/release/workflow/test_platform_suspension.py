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

"""Verify the temporary Windows-only CI and publication boundary."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from tests.qualification.release.workflow.support import PROJECT_ROOT, workflow_path


def test_active_app_matrices_only_schedule_windows() -> None:
    """Keep app validation on Windows while retaining all Comfy version cases."""
    for name in (
        "platform-tests.yml",
        "installed-app-smoke.yml",
        "native-appearance-screenshots.yml",
        "managed-comfy-install.yml",
        "comfy-runtime-compatibility.yml",
        "comfy-update-compatibility.yml",
    ):
        workflow = yaml.safe_load(workflow_path(name).read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            matrix = job.get("strategy", {}).get("matrix", {})
            for entry in matrix.get("include", ()):
                assert entry["os"] == "windows-latest", (name, entry)
            if "os" in matrix:
                assert matrix["os"] == ["windows-latest"]


def test_suspended_builds_and_artifact_downloads_do_not_run() -> None:
    """Pause native jobs before runner allocation and omit missing release inputs."""
    for name, jobs in (
        ("release-build.yml", ("build-linux", "build-macos")),
        ("linux-system-trust.yml", ("linux-distro-trust",)),
        ("cross-platform-validation.yml", ("linux-system-trust",)),
        ("release-current-install-qualification.yml", ("clean-install-macos",)),
    ):
        workflow = yaml.safe_load(workflow_path(name).read_text(encoding="utf-8"))
        for job in jobs:
            assert workflow["jobs"][job]["if"] == "${{ false }}"
    candidate = yaml.safe_load(
        workflow_path("release-candidate.yml").read_text(encoding="utf-8")
    )
    steps = {step["name"]: step for step in candidate["jobs"]["stage"]["steps"]}
    for platform in ("Linux", "Apple Silicon"):
        assert steps[f"Download {platform} release inputs"]["if"] == "${{ false }}"
    assert steps["Download Windows release inputs"]["if"] != "${{ false }}"


@pytest.mark.platforms("windows")
@pytest.mark.parametrize(
    "scope",
    [
        "all",
        "qualification-all",
        "clean-all",
        "updates-all",
        "canary-fast",
        "clean-linux",
        "clean-macos",
        "updates-linux",
        "updates-macos",
    ],
)
def test_qualification_selection_never_requests_suspended_assets(
    tmp_path: Path, scope: str
) -> None:
    """Execute the release selector on its supported Windows PowerShell host."""
    workflow = yaml.safe_load(
        workflow_path("release-qualification.yml").read_text(encoding="utf-8")
    )
    script = workflow["jobs"]["select-qualification"]["steps"][0]["run"]
    output = tmp_path / "outputs.txt"
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        env={
            **os.environ,
            "QUALIFICATION_SCOPE": scope,
            "CANDIDATE_VERSION": "1.2.3",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if scope in {"clean-linux", "clean-macos", "updates-linux", "updates-macos"}:
        assert result.returncode != 0
        assert "temporarily suspended" in result.stderr
        assert not output.exists()
        return
    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert values["macos_clean_enabled"] == "false"
    assert all(
        row["os"] == "windows-latest" for row in json.loads(values["clean_matrix"])
    )
    assert set(json.loads(values["update_platforms"])) <= {"windows"}
    if scope == "all":
        assert values["clean_enabled"] == values["updates_enabled"] == "true"


def test_all_readme_locales_remove_suspended_downloads() -> None:
    """Keep every release-enabled README aligned with the available installers."""
    registry = json.loads(
        (
            PROJECT_ROOT
            / "sugarsubstitute_shared/localization/resources/languages.json"
        ).read_text(encoding="utf-8")
    )
    for language in registry["languages"]:
        if not language["release_enabled"]:
            continue
        name = "README.md" if language["id"] == "en" else f"README.{language['id']}.md"
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        assert "Installer-Windows-x64.exe" in text
        assert "Installer-macOS" not in text
        assert "Installer-Linux" not in text
        assert "```bash" not in text
