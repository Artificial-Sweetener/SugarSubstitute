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


import pytest

from substitute.application.onboarding import (
    OnboardingDraftState,
    OnboardingFlowService,
    OnboardingProvisioningFailure,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyPythonBinding,
    ComfyTargetMode,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
)

from .preference_support import _Bundle, _ExternalModelLibraryConfigurator
from .runtime_support import (
    _FakeRuntimeLaunchService,
    _FakeSetupTransactionService,
    _StaticManagedRuntimeService,
    _StaticOnboardingService,
    _StaticReadinessService,
    _build_context,
    _python_binding,
)


def test_flow_service_prepares_existing_local_comfy_without_endpoint_probe(
    tmp_path: Path,
) -> None:
    """Existing-local setup should prepare the folder without requiring a live endpoint."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    provisioner_kwargs: list[dict[str, object]] = []
    workspace = tmp_path / "ExternalComfy"
    custom_models = tmp_path / "WebUI" / "models"
    external_models = _ExternalModelLibraryConfigurator()

    def _record_provisioning(**kwargs: object) -> ComfyPythonBinding:
        """Record existing-local workspace preparation arguments."""

        provisioner_kwargs.append(kwargs)
        return _python_binding(tmp_path / "ExternalComfy")

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=_record_provisioning,
        entrypoint_path=tmp_path / "main.py",
        external_model_library_configurator=external_models,
    )
    result = service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=workspace,
            attached_python_binding=_python_binding(workspace),
            managed_model_root=custom_models,
            managed_model_root_uses_default=False,
        ),
        restart_required=False,
        on_status=lambda message: None,
        on_log=lambda line: None,
    )

    assert result.context is context
    assert provisioner_kwargs[0]["workspace"] == workspace
    assert provisioner_kwargs[0]["python_binding"] == _python_binding(workspace)
    assert provisioner_kwargs[0]["model_root"] == custom_models
    assert provisioner_kwargs[0]["configure_model_root"] is True
    assert external_models.calls == [(workspace, custom_models)]


def test_flow_service_rejects_existing_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Existing-local setup should require a ComfyUI folder before provisioning."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=lambda **kwargs: _python_binding(tmp_path),
        entrypoint_path=tmp_path / "main.py",
    )

    with pytest.raises(OnboardingProvisioningFailure) as error:
        service.provision(
            draft=OnboardingDraftState(
                installation_root=tmp_path,
                target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
                endpoint_host="127.0.0.1",
                endpoint_port=8188,
                managed_workspace_path=tmp_path / "comfyui",
                attached_workspace_path=None,
            ),
            restart_required=False,
            on_status=lambda message: None,
            on_log=lambda line: None,
        )

    assert error.value.headline == "Choose your existing ComfyUI folder"
    assert "needs the folder" in error.value.user_message


def test_flow_service_maps_missing_attached_workspace_to_user_copy(
    tmp_path: Path,
) -> None:
    """Attached-local missing-folder readiness should explain how to recover."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    missing_workspace = tmp_path / "missing-comfyui"
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(
                    route=BootstrapRoute.REPAIR,
                    issues=(
                        ReadinessIssue(
                            code=ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING,
                            summary="The saved ComfyUI folder could not be found.",
                            detail=(
                                "Attached ComfyUI folder does not exist: "
                                f"{missing_workspace}"
                            ),
                        ),
                    ),
                )
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=lambda **kwargs: _python_binding(tmp_path),
        entrypoint_path=tmp_path / "main.py",
    )

    with pytest.raises(OnboardingProvisioningFailure) as error:
        service.provision(
            draft=OnboardingDraftState(
                installation_root=tmp_path,
                target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
                endpoint_host="127.0.0.1",
                endpoint_port=8190,
                managed_workspace_path=tmp_path / "comfyui",
                attached_workspace_path=missing_workspace,
                attached_python_binding=_python_binding(missing_workspace),
            ),
            restart_required=False,
            on_status=lambda message: None,
            on_log=lambda line: None,
        )

    assert error.value.headline == "The ComfyUI folder couldn't be found"
    assert "local ComfyUI folder you entered" in error.value.user_message
    assert "contains ComfyUI's main.py" in error.value.remediation_steps[1]
