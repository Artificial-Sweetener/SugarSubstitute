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


from substitute.application.onboarding import (
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingFlowService,
    OnboardingPreferenceSetupDraft,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyTargetMode,
    ReadinessAssessment,
)

from .preference_support import (
    _Bundle,
    _PreferenceSetupService,
)
from .runtime_support import (
    _FakeRuntimeLaunchService,
    _FakeSetupTransactionService,
    _StaticManagedRuntimeService,
    _StaticOnboardingService,
    _StaticReadinessService,
    _build_context,
)


def test_flow_service_saves_preferences_model_root_and_credentials(
    tmp_path: Path,
) -> None:
    """Provisioning should persist onboarding choices through their owners."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    preference_setup = _PreferenceSetupService()
    bundle = _Bundle(
        onboarding_service=_StaticOnboardingService(context),
        runtime_service=_FakeRuntimeLaunchService(),
        readiness_service=_StaticReadinessService(
            ReadinessAssessment(route=BootstrapRoute.READY, issues=())
        ),
        managed_runtime_service=_StaticManagedRuntimeService(),
        setup_transaction_service=_FakeSetupTransactionService(context),
        preference_setup_service=preference_setup,
    )
    provisioner_kwargs: list[dict[str, object]] = []

    def _record_provisioning(**kwargs: object) -> Path:
        """Record managed provisioning arguments."""

        provisioner_kwargs.append(kwargs)
        return tmp_path / "unused"

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: bundle,
        managed_workspace_provisioner=_record_provisioning,
        entrypoint_path=tmp_path / "main.py",
    )
    custom_models = tmp_path / "Models"
    custom_outputs = tmp_path / "Images"
    logs: list[str] = []

    service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=None,
            managed_model_root=custom_models,
            managed_model_root_uses_default=False,
            output_root=custom_outputs,
            output_root_uses_default=False,
            danbooru_tag_help_enabled=False,
            danbooru_safe_previews_enabled=True,
            danbooru_image_rating_policy="safe_and_questionable",
            civitai_model_help_enabled=False,
            civitai_downloads_enabled=False,
            civitai_safe_thumbnails_enabled=True,
            civitai_thumbnail_safety_policy="allow_soft",
        ),
        credential_draft=OnboardingCredentialDraft("civitai-secret"),
        restart_required=False,
        on_status=lambda message: None,
        on_log=logs.append,
    )

    assert preference_setup.saved_preferences == [
        OnboardingPreferenceSetupDraft(
            output_root=custom_outputs,
            danbooru_tag_help_enabled=False,
            danbooru_safe_previews_enabled=True,
            danbooru_image_rating_policy="safe_and_questionable",
            civitai_model_help_enabled=False,
            civitai_downloads_enabled=False,
            civitai_safe_thumbnails_enabled=True,
            civitai_thumbnail_safety_policy="allow_soft",
        )
    ]
    assert preference_setup.saved_credentials == [
        OnboardingCredentialDraft("civitai-secret")
    ]
    assert provisioner_kwargs[0]["managed_model_root"] == custom_models
    assert provisioner_kwargs[0]["configure_model_root"] is True
    assert provisioner_kwargs[0]["refresh_core_nodepacks"] == frozenset(CoreNodepackId)
    assert "installer_temp_root" not in provisioner_kwargs[0]
    assert "civitai-secret" not in "\n".join(logs)
