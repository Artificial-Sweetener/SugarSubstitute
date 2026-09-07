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

"""Tests for onboarding flow failure mapping and readiness-driven recovery copy."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.localization import render_source_application_text
from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
)
from sugarsubstitute_shared.windows_long_paths import WindowsPathComponentTooLongError

import pytest
from sugarsubstitute_shared.model_acquisition import (
    ModelAcquisitionCredentialRequired,
)

from substitute.application.onboarding import (
    OnboardingDraftState,
    OnboardingFlowService,
)
from substitute.domain.onboarding import (
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyTargetMode,
)


def test_flow_service_maps_storage_exhaustion_to_temp_space_copy(
    tmp_path: Path,
) -> None:
    """Storage exhaustion should produce install-drive temporary-space guidance."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=RuntimeError("OSError: [Errno 28] No space left on device"),
    )

    assert failure.headline == "Substitute ran out of temporary install space"
    assert str(tmp_path) in render_source_application_text(failure.remediation_steps[0])
    assert "Python packages" in failure.user_message


def test_flow_service_maps_external_long_path_failure_to_actionable_copy(
    tmp_path: Path,
) -> None:
    """A known third-party path failure should name the boundary and both remedies."""

    long_path = tmp_path / "deep" / "ComfyUI"
    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=long_path,
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=ExternalLongPathCompatibilityError(
            component="7-Zip",
            path=long_path,
            detail="[WinError 206] The filename or extension is too long",
        ),
    )

    assert failure.headline == "A Windows component could not use this long path"
    assert "7-Zip" in render_source_application_text(failure.user_message)
    assert "shorter folder" in failure.remediation_steps[0]
    assert "enable Win32 long paths" in failure.remediation_steps[1]


def test_flow_service_maps_component_limit_to_specific_copy(tmp_path: Path) -> None:
    """An impossible individual name should not be reported as a total-path failure."""

    offending_name = "x" * 256
    path = tmp_path / offending_name
    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=path,
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=WindowsPathComponentTooLongError(
            path=path,
            component=offending_name,
        ),
    )

    assert failure.headline == "A file or folder name is too long for Windows"
    assert "255 characters" in failure.user_message
    assert str(path) in render_source_application_text(failure.remediation_steps[0])


@pytest.mark.parametrize(
    ("reason", "expected_headline"),
    (
        (
            ComfyPythonResolutionFailure.WORKSPACE_INVALID,
            "Choose the folder that contains ComfyUI",
        ),
        (
            ComfyPythonResolutionFailure.AUTOMATIC_DISCOVERY_FAILED,
            "Choose the Python this ComfyUI setup uses",
        ),
        (
            ComfyPythonResolutionFailure.AMBIGUOUS,
            "Choose which Python this ComfyUI setup uses",
        ),
        (
            ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID,
            "Choose a working Python for this ComfyUI setup",
        ),
    ),
)
def test_flow_service_maps_python_resolution_failures_to_browse_guidance(
    tmp_path: Path,
    reason: ComfyPythonResolutionFailure,
    expected_headline: str,
) -> None:
    """Attached Python failures should tell the user where to make the choice."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=tmp_path / "ExternalComfy",
        ),
        target_mode=ComfyTargetMode.ATTACHED_LOCAL,
        error=ComfyPythonResolutionError(reason, "probe detail"),
    )

    assert failure.headline == expected_headline
    if reason is ComfyPythonResolutionFailure.WORKSPACE_INVALID:
        assert "main.py" in failure.remediation_steps[1]
    else:
        assert "Browse beside Python executable" in failure.remediation_steps[1]


@pytest.mark.parametrize(
    ("technical_detail", "expected_headline"),
    (
        (
            "Substitute couldn't download ComfyUI into the selected folder.",
            "Substitute couldn't download ComfyUI",
        ),
        (
            "Substitute couldn't finish installing ComfyUI's Python packages.",
            "Substitute couldn't finish installing ComfyUI",
        ),
        (
            "Substitute couldn't finish preparing the required custom nodes.",
            "Substitute couldn't finish preparing ComfyUI",
        ),
    ),
)
def test_flow_service_maps_specific_managed_failures_to_specific_copy(
    tmp_path: Path,
    technical_detail: str,
    expected_headline: str,
) -> None:
    """Managed install failure classes should not collapse into one generic message."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=RuntimeError(technical_detail),
    )

    assert failure.headline == expected_headline
    assert "try again" in failure.remediation_steps[-1].lower()


def test_flow_service_preserves_plan_with_civitai_credential_recovery(
    tmp_path: Path,
) -> None:
    """Explain how to resume a reviewed model plan after an authenticated response."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=ModelAcquisitionCredentialRequired("CivitAI API key required"),
    )

    assert failure.headline == "This CivitAI model needs an API key"
    assert "still selected" in failure.user_message
    assert failure.remediation_steps == (
        "Go back to Integrations.",
        "Add your CivitAI API key.",
        "Return to setup and try again.",
    )
