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

"""Build and reveal onboarding-family startup surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService

from substitute.application.onboarding import OnboardingFlowService
from substitute.application.onboarding.flow_contracts import OnboardingBundleFactory
from substitute.application.model_recommendations import (
    ExistingModelFamilyScanner,
    ModelInstallService,
    ModelOnboardingApplicationService,
)
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationService,
)
from substitute.application.onboarding.setup_model_installer import (
    OnboardingModelInstaller,
)
from substitute.application.onboarding.comfy_environment_service import (
    ComfyEnvironmentService,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.application_readiness import (
    schedule_application_readiness_receipt,
)
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.app.bootstrap.onboarding_execution import (
    OnboardingExecutionRuntime,
    create_onboarding_environment_submitter,
    create_onboarding_model_submitter,
    create_onboarding_provisioning_submitter_factory,
)
from substitute.app.bootstrap.persistent_cache_composition import (
    build_recommendation_thumbnail_cache,
)
from substitute.app.bootstrap.persistent_cache_runtime import (
    prepare_persistent_cache_runtime,
)
from substitute.domain.onboarding import (
    InstallationContext,
    ReadinessAssessment,
    SetupTransactionMode,
)
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface
from substitute.infrastructure.comfy.attached_install import (
    prepare_verified_attached_comfy_setup,
)
from substitute.infrastructure.comfy.local_process_gateway import (
    PsutilLocalComfyProcessGateway,
)
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.workspace_python_discovery import (
    WorkspacePythonGateway,
)
from substitute.infrastructure.model_recommendations import (
    CachedRecommendationThumbnailFetcher,
    CivitaiFamilyRecommendationGateway,
    CivitaiThumbnailFetcher,
)
from substitute.infrastructure.onboarding.setup_transcript import (
    OnboardingSetupTranscript,
)
from substitute.presentation.onboarding import (
    OnboardingController,
    OnboardingFlowMode,
    OnboardingWindow,
)
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)


def show_onboarding_surface(
    *,
    context: InstallationContext,
    readiness_assessment: ReadinessAssessment,
    flow_mode: OnboardingFlowMode,
    entrypoint_path: Path,
    initial_geometry: tuple[int, int, int, int] | None = None,
    execution_runtime: object | None = None,
) -> OnboardingWindow:
    """Build, show, and publish readiness for onboarding-family windows."""

    owned_execution_runtime: ExecutionRuntime | None = None
    active_execution_runtime = execution_runtime
    if active_execution_runtime is None:
        owned_execution_runtime = ExecutionRuntime()
        active_execution_runtime = owned_execution_runtime
    persistent_cache_runtime = prepare_persistent_cache_runtime(
        context.cache_dir,
        installation_root=context.install_root,
    )
    recommendation_thumbnails = build_recommendation_thumbnail_cache(
        persistent_cache_runtime
    )
    setup_transcript = OnboardingSetupTranscript.open(context.logs_dir)
    onboarding_bundle_factory = cast(
        OnboardingBundleFactory,
        build_onboarding_service_bundle,
    )
    flow_service = OnboardingFlowService(
        service_bundle_factory=onboarding_bundle_factory,
        managed_workspace_provisioner=ensure_managed_comfy_setup,
        entrypoint_path=entrypoint_path,
        attached_workspace_provisioner=prepare_verified_attached_comfy_setup,
        transaction_mode=_transaction_mode_for_flow(flow_mode),
        model_installer=OnboardingModelInstaller(
            lambda model_root, api_key: ModelInstallService(
                primary_acquisition=ModelAcquisitionService(
                    allowed_roots=(model_root,),
                    api_key_provider=lambda: (
                        api_key
                        or build_onboarding_service_bundle(
                            context.install_root
                        ).civitai_credential_service.load_api_key()
                    ),
                ),
            )
        ),
    )
    controller = OnboardingController(
        initial_install_root=context.install_root,
        flow_mode=flow_mode,
        readiness_assessment=readiness_assessment,
        flow_service=flow_service,
        preparation_service=OnboardingPreparationService(
            service_bundle_factory=onboarding_bundle_factory,
            managed_workspace_provisioner=ensure_managed_comfy_setup,
            attached_workspace_provisioner=prepare_verified_attached_comfy_setup,
        ),
        submitter_factory=create_onboarding_provisioning_submitter_factory(
            cast(OnboardingExecutionRuntime, active_execution_runtime)
        ),
    )
    environment_submitter = create_onboarding_environment_submitter(
        cast(OnboardingExecutionRuntime, active_execution_runtime),
        controller,
    )
    environment_coordinator = ComfyEnvironmentCoordinator(
        service=ComfyEnvironmentService(
            process_gateway=PsutilLocalComfyProcessGateway(),
            python_gateway=WorkspacePythonGateway(),
        ),
        submitter=environment_submitter,
        close_submitter=environment_submitter.close,
        parent=controller,
    )
    model_submitter = create_onboarding_model_submitter(
        cast(OnboardingExecutionRuntime, active_execution_runtime),
        controller,
    )
    model_coordinator = ModelOnboardingCoordinator(
        service=ModelOnboardingApplicationService(
            scanner=ExistingModelFamilyScanner(),
            gateway=CivitaiFamilyRecommendationGateway(
                api_key_provider=lambda: build_onboarding_service_bundle(
                    context.install_root
                ).civitai_credential_service.load_api_key()
            ),
            thumbnail_fetcher=CachedRecommendationThumbnailFetcher(
                fetcher=CivitaiThumbnailFetcher(),
                preparer=recommendation_thumbnails.preparer,
                asset_store=recommendation_thumbnails.assets,
            ),
        ),
        submitter=model_submitter,
        close_submitter=model_submitter.close,
        parent=controller,
    )
    window = OnboardingWindow(
        controller=controller,
        environment_coordinator=environment_coordinator,
        model_coordinator=model_coordinator,
        install_root_locked=resolve_app_layout(context.install_root).installed_payload,
        initial_geometry=initial_geometry,
        diagnostic_log_sink=(setup_transcript.append if setup_transcript else None),
    )
    if owned_execution_runtime is not None:
        window.destroyed.connect(lambda _obj=None: owned_execution_runtime.shutdown())
    window.destroyed.connect(lambda _obj=None: persistent_cache_runtime.close())
    if setup_transcript is not None:
        window.destroyed.connect(lambda _obj=None: setup_transcript.close())
    window.show()
    schedule_application_readiness_receipt(
        surface=ApplicationReadinessSurface.ONBOARDING
    )
    from substitute.presentation.onboarding.installer_qualification import (
        schedule_onboarding_qualification,
    )

    schedule_onboarding_qualification(window)
    return window


def _transaction_mode_for_flow(
    flow_mode: OnboardingFlowMode,
) -> SetupTransactionMode:
    """Map one UI flow entry mode to durable setup transaction intent."""

    if flow_mode is OnboardingFlowMode.FIRST_RUN:
        return SetupTransactionMode.FIRST_RUN
    if flow_mode is OnboardingFlowMode.RECONFIGURE:
        return SetupTransactionMode.RECONFIGURE
    return SetupTransactionMode.REPAIR


__all__ = ["show_onboarding_surface"]
