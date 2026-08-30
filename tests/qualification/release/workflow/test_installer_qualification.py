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

"""Qualify clean-install and historical-migration release workflow contracts."""

from __future__ import annotations

from tests.qualification.release.workflow.support import PROJECT_ROOT, workflow_text


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
    lifecycle_text = "\n".join(
        (
            (PROJECT_ROOT / "tools" / "ci" / "verify_installer_lifecycle.py").read_text(
                encoding="utf-8"
            ),
            (
                PROJECT_ROOT / "tools" / "ci" / "historical_update_qualification.py"
            ).read_text(encoding="utf-8"),
        )
    )
    ui_qualification_text = (
        PROJECT_ROOT / "tools" / "ci" / "installer_ui_qualification.py"
    ).read_text(encoding="utf-8")
    historical_qualification_text = (
        PROJECT_ROOT / "tools" / "ci" / "historical_install_qualification.py"
    ).read_text(encoding="utf-8")
    assert "run_current_installer_ui" in lifecycle_text
    assert "set_update_manifest" in lifecycle_text
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
    assert '"--candidate-manifest-url"' in update_text
    assert '--candidate-channel "${{ inputs.candidate_channel }}"' in update_text
    assert "Build version-pinned historical Windows setup" not in update_text
    assert "SugarSubstitute-Local-Test-Installer" not in update_text
