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

"""Coordinate onboarding draft loading and provisioning without Qt dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetMode,
    InstallationContext,
)
from substitute.application.onboarding.failure_classifier import (
    OnboardingFailureClassifier,
)
from substitute.application.onboarding.flow_contracts import (
    AttachedWorkspaceProvisioner,
    ExternalModelLibraryConfiguratorProtocol,
    ManagedWorkspaceProvisioner,
    OnboardingBundleFactory,
    OnboardingCompletionResult,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from substitute.application.onboarding.draft_recovery import (
    recover_stale_attached_managed_draft,
)
from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
)
from substitute.application.onboarding.setup_application import (
    OnboardingPreferenceApplication,
    OnboardingRuntimeLaunchPlanner,
)
from substitute.application.onboarding.setup_model_installer import (
    OnboardingModelInstaller,
)
from substitute.application.onboarding.setup_transaction_service import (
    SetupTransactionOptions,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressReporter,
    SetupTaskId,
    SetupTaskState,
    require_setup_current,
)
from substitute.application.onboarding.transaction_failure_recorder import (
    record_setup_transaction_failure,
)
from substitute.application.execution import CancellationToken
from substitute.domain.model_recommendations import ModelInstallPlan
from substitute.application.onboarding.draft_load_support import (
    credential_is_configured,
    load_pending_transaction_safely,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.prompt.features.models import PromptEditorFeature
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("application.onboarding.flow_service")


@dataclass
class OnboardingFlowService:
    """Load onboarding drafts and provision the selected target end-to-end."""

    service_bundle_factory: OnboardingBundleFactory
    managed_workspace_provisioner: ManagedWorkspaceProvisioner
    entrypoint_path: Path
    attached_workspace_provisioner: AttachedWorkspaceProvisioner | None = None
    transaction_mode: SetupTransactionMode = SetupTransactionMode.REPAIR
    preference_application: OnboardingPreferenceApplication = (
        OnboardingPreferenceApplication()
    )
    runtime_launch_planner: OnboardingRuntimeLaunchPlanner = (
        OnboardingRuntimeLaunchPlanner()
    )
    model_installer: OnboardingModelInstaller | None = None
    external_model_library_configurator: (
        ExternalModelLibraryConfiguratorProtocol | None
    ) = None

    def load_draft(self, installation_root: Path) -> OnboardingDraftState:
        """Load onboarding draft state from persisted config or defaults."""

        bundle = self.service_bundle_factory(installation_root)
        context = bundle.onboarding_service.load_draft_context()
        pending_transaction = load_pending_transaction_safely(
            bundle.setup_transaction_service
        )
        if (
            pending_transaction is not None
            and pending_transaction.installation is not None
            and pending_transaction.target is not None
        ):
            context = InstallationContext(
                installation=pending_transaction.installation,
                runtime=pending_transaction.runtime or context.runtime,
                comfy_target=pending_transaction.target,
            )
        managed_runtime = (
            pending_transaction.managed_runtime
            if pending_transaction is not None
            and pending_transaction.managed_runtime is not None
            else None
        ) or bundle.managed_runtime_service.load_draft_configuration()
        managed_workspace_path = (
            context.comfy_target.workspace_path or context.managed_comfy_dir
        )
        model_root_status = bundle.model_root_provider.load(context.comfy_target)
        default_model_root = managed_workspace_path / "models"
        reported_model_root = (
            Path(
                model_root_status.configured_model_root
                or model_root_status.default_model_root
            )
            if model_root_status is not None
            and context.comfy_target.workspace_path is not None
            else None
        )
        output_preferences = bundle.output_preference_service.load_preferences()
        output_root = bundle.output_preference_service.effective_output_root(
            output_preferences
        )
        prompt_preferences = bundle.prompt_editor_preference_service.load_preferences()
        danbooru_preferences = bundle.danbooru_preference_service.load_preferences()
        civitai_preferences = bundle.civitai_preference_service.load_preferences()
        connected_models_root = (
            self.external_model_library_configurator.load_models_root(
                managed_workspace_path
            )
            if self.external_model_library_configurator is not None
            and context.comfy_target.mode is not ComfyTargetMode.REMOTE
            else None
        )
        return OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=managed_workspace_path,
            attached_workspace_path=context.comfy_target.workspace_path,
            attached_python_binding=context.comfy_target.python_binding,
            managed_model_root=(
                connected_models_root or reported_model_root or default_model_root
            ),
            managed_model_root_uses_default=(
                False
                if connected_models_root is not None
                else (
                    model_root_status.uses_default
                    if model_root_status is not None
                    else True
                )
            ),
            output_root=output_root,
            output_root_uses_default=(
                output_preferences.organization.output_root is None
            ),
            danbooru_tag_help_enabled=(
                prompt_preferences.user_allows(PromptEditorFeature.DANBOORU_URL_IMPORT)
                or prompt_preferences.user_allows(
                    PromptEditorFeature.DANBOORU_WIKI_LOOKUP
                )
            ),
            danbooru_safe_previews_enabled=danbooru_preferences.show_wiki_images,
            danbooru_image_rating_policy=danbooru_preferences.allowed_image_ratings.value,
            civitai_model_help_enabled=(
                civitai_preferences.metadata_lookup_enabled
                or civitai_preferences.missing_model_lookup_enabled
            ),
            civitai_downloads_enabled=civitai_preferences.downloads_enabled,
            civitai_safe_thumbnails_enabled=(
                civitai_preferences.thumbnail_downloads_enabled
                and civitai_preferences.thumbnail_safety_policy
                is not CivitaiThumbnailSafetyPolicy.DISABLED
            ),
            civitai_thumbnail_safety_policy=(
                CivitaiThumbnailSafetyPolicy.SFW_ONLY.value
                if civitai_preferences.thumbnail_safety_policy
                is CivitaiThumbnailSafetyPolicy.DISABLED
                else civitai_preferences.thumbnail_safety_policy.value
            ),
            civitai_api_key_configured=credential_is_configured(
                bundle.civitai_credential_service
            ),
            detected_platform=managed_runtime.detected_platform,
            detected_accelerator=managed_runtime.detected_accelerator,
            selected_install_target=managed_runtime.install_target,
            selected_python_version=managed_runtime.python_version,
            selected_comfy_channel=managed_runtime.comfy_channel,
            selected_backend_policy=managed_runtime.backend_policy,
            selected_torch_channel=managed_runtime.torch_release_channel,
            selected_torch_reason=managed_runtime.torch_selection_reason,
            selected_stability=managed_runtime.stability.value,
            force_cpu_mode=managed_runtime.force_cpu_mode,
            prefer_edge_torch=managed_runtime.prefer_edge_torch,
            prefer_edge_comfy_channel=managed_runtime.prefer_edge_comfy_channel,
        )

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[ApplicationText], None],
        on_log: Callable[[ApplicationText], None],
        model_install_plan: ModelInstallPlan | None = None,
        setup_generation: int = 1,
        on_setup_progress: Callable[[SetupProgressEvent], None] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> OnboardingCompletionResult:
        """Provision the selected target and return the completion payload."""
        bundle = self.service_bundle_factory(draft.installation_root)
        draft = recover_stale_attached_managed_draft(
            bundle=bundle,
            draft=draft,
            transaction_mode=self.transaction_mode,
        )
        endpoint = ComfyEndpoint(
            host=draft.endpoint_host.strip(),
            port=int(draft.endpoint_port),
        )
        on_status(app_text("Starting setup."))
        on_log(app_text("Runtime root: %1", draft.installation_root / "runtime"))
        target_mode = ComfyTargetMode(draft.target_mode)
        progress = SetupProgressReporter(setup_generation, on_setup_progress)
        progress.transition(
            SetupTaskId.CONFIGURATION,
            SetupTaskState.RUNNING,
            app_text("Saving and applying setup choices."),
        )
        transaction_id: str | None = None
        try:
            if target_mode is ComfyTargetMode.MANAGED_LOCAL:
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        workspace_path=draft.managed_workspace_path,
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                        force_cpu_mode=draft.force_cpu_mode,
                        prefer_edge_torch=draft.prefer_edge_torch,
                        prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                    ),
                )
                transaction_id = transaction.transaction_id
                pending_context = bundle.onboarding_service.build_managed_local_context(
                    endpoint=endpoint,
                    workspace_path=draft.managed_workspace_path,
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self.preference_application.save_setup(
                    service=bundle.preference_setup_service,
                    selection=draft,
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_RUNTIME_SELECTING,
                )
                managed_runtime = bundle.managed_runtime_service.select_configuration(
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                )
                bundle.setup_transaction_service.record_managed_runtime(
                    transaction.transaction_id,
                    managed_runtime,
                )
                progress.transition(
                    SetupTaskId.CONFIGURATION,
                    SetupTaskState.COMPLETED,
                    app_text("Setup choices are ready."),
                )
                on_status(app_text("Saving your setup choices."))
                on_log(app_text("Managed workspace: %1", draft.managed_workspace_path))
                on_log(
                    app_text(
                        "[ManagedInstall] platform=%1 accelerator=%2 target=%3 "
                        "python=%4 channel=%5 backend=%6 torch_channel=%7 stability=%8",
                        managed_runtime.detected_platform or "unknown",
                        managed_runtime.detected_accelerator or "unknown",
                        managed_runtime.install_target or "unknown",
                        managed_runtime.python_version or "unknown",
                        managed_runtime.comfy_channel or "unknown",
                        managed_runtime.backend_policy or "unknown",
                        managed_runtime.torch_release_channel or "unknown",
                        managed_runtime.stability.value,
                    )
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.RUNNING,
                    app_text("Preparing Substitute's local runtime."),
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.COMPLETED,
                    app_text("Substitute's local runtime is ready."),
                )
                on_status(app_text("Installing ComfyUI and finishing setup."))
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
                )
                managed_model_root = self._managed_model_root_for_save(draft)
                is_repair = self.transaction_mode is SetupTransactionMode.REPAIR
                progress.transition(
                    SetupTaskId.COMFY_WORKSPACE,
                    SetupTaskState.RUNNING,
                    app_text("Preparing ComfyUI."),
                )
                managed_setup = self.managed_workspace_provisioner(
                    workspace=(
                        pending_context.comfy_target.workspace_path
                        or pending_context.managed_comfy_dir
                    ),
                    managed_model_root=managed_model_root,
                    configure_model_root=True,
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                    repair_existing_runtime=is_repair,
                    refresh_core_nodepacks=(
                        frozenset(CoreNodepackId) if is_repair else frozenset()
                    ),
                    on_status=on_status,
                    on_log=on_log,
                )
                bundle.setup_transaction_service.record_managed_runtime(
                    transaction.transaction_id,
                    managed_setup.runtime_configuration,
                )
                self._configure_shared_model_library(
                    pending_context.comfy_target.workspace_path
                    or pending_context.managed_comfy_dir,
                    (
                        draft.managed_model_root
                        if not draft.managed_model_root_uses_default
                        else None
                    ),
                )
                progress.transition(
                    SetupTaskId.COMFY_WORKSPACE,
                    SetupTaskState.COMPLETED,
                    app_text("ComfyUI is ready for final checks."),
                )
                if self.model_installer is not None:
                    self.model_installer.install(
                        plan=model_install_plan,
                        credential_draft=credential_draft,
                        cancellation=cancellation,
                        setup_generation=setup_generation,
                        on_setup_progress=on_setup_progress,
                    )
                elif model_install_plan is not None and model_install_plan.files:
                    raise RuntimeError("Model download service is unavailable.")
                else:
                    progress.transition(
                        SetupTaskId.MODEL_DOWNLOAD,
                        SetupTaskState.SKIPPED,
                        app_text("No model downloads were selected."),
                    )
                current_transaction = bundle.setup_transaction_service.load()
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.RUNNING,
                    app_text("Checking that ComfyUI is ready."),
                )
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                    managed_runtime=(
                        current_transaction.managed_runtime
                        if current_transaction is not None
                        else None
                    ),
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise OnboardingFailureClassifier.from_readiness(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.COMPLETED,
                    app_text("ComfyUI passed its readiness checks."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                require_setup_current(cancellation)
                progress.transition(
                    SetupTaskId.COMMIT,
                    SetupTaskState.RUNNING,
                    app_text("Saving the completed setup."),
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )
            elif target_mode is ComfyTargetMode.ATTACHED_LOCAL:
                if draft.attached_workspace_path is None:
                    raise OnboardingProvisioningFailure(
                        headline=app_text("Choose your existing ComfyUI folder"),
                        user_message=app_text(
                            "Use My Current ComfyUI needs the folder that contains "
                            "your local ComfyUI installation."
                        ),
                        technical_detail="Existing local ComfyUI setup requires a folder path.",
                        remediation_steps=(
                            app_text(
                                "Choose the folder that contains ComfyUI's main.py file."
                            ),
                            app_text("Then run setup again."),
                        ),
                    )
                if self.attached_workspace_provisioner is None:
                    raise RuntimeError("Attached ComfyUI provisioning is unavailable.")
                binding = draft.attached_python_binding
                if binding is None:
                    raise RuntimeError(
                        "Attached ComfyUI Python must be verified before provisioning."
                    )
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        workspace_path=draft.attached_workspace_path,
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                    ),
                )
                transaction_id = transaction.transaction_id
                on_status(app_text("Preparing your existing ComfyUI setup."))
                on_log(
                    app_text("Attached workspace: %1", draft.attached_workspace_path)
                )
                pending_context = (
                    bundle.onboarding_service.build_attached_local_context(
                        endpoint=endpoint,
                        workspace_path=draft.attached_workspace_path,
                        python_binding=binding,
                    )
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self.preference_application.save_setup(
                    service=bundle.preference_setup_service,
                    selection=draft,
                )
                progress.transition(
                    SetupTaskId.CONFIGURATION,
                    SetupTaskState.COMPLETED,
                    app_text("Setup choices are ready."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.RUNNING,
                    app_text("Preparing Substitute's local runtime."),
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.COMPLETED,
                    app_text("Substitute's local runtime is ready."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_RUNTIME_SELECTING,
                )
                managed_runtime = bundle.managed_runtime_service.select_configuration(
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                )
                bundle.setup_transaction_service.record_managed_runtime(
                    transaction.transaction_id,
                    managed_runtime,
                )
                on_status(app_text("Preparing your existing ComfyUI installation."))
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
                )
                progress.transition(
                    SetupTaskId.COMFY_WORKSPACE,
                    SetupTaskState.RUNNING,
                    app_text("Preparing the existing ComfyUI installation."),
                )
                self.attached_workspace_provisioner(
                    workspace=draft.attached_workspace_path,
                    python_binding=binding,
                    model_root=self._managed_model_root_for_save(draft),
                    configure_model_root=True,
                    on_status=on_status,
                    on_log=on_log,
                )
                self._configure_shared_model_library(
                    draft.attached_workspace_path,
                    (
                        draft.managed_model_root
                        if not draft.managed_model_root_uses_default
                        else None
                    ),
                )
                progress.transition(
                    SetupTaskId.COMFY_WORKSPACE,
                    SetupTaskState.COMPLETED,
                    app_text("The existing ComfyUI installation is ready."),
                )
                if self.model_installer is not None:
                    self.model_installer.install(
                        plan=model_install_plan,
                        credential_draft=credential_draft,
                        cancellation=cancellation,
                        setup_generation=setup_generation,
                        on_setup_progress=on_setup_progress,
                    )
                elif model_install_plan is not None and model_install_plan.files:
                    raise RuntimeError("Model download service is unavailable.")
                else:
                    progress.transition(
                        SetupTaskId.MODEL_DOWNLOAD,
                        SetupTaskState.SKIPPED,
                        app_text("No model downloads were selected."),
                    )
                current_transaction = bundle.setup_transaction_service.load()
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.RUNNING,
                    app_text("Checking that ComfyUI is ready."),
                )
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                    managed_runtime=(
                        current_transaction.managed_runtime
                        if current_transaction is not None
                        else None
                    ),
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise OnboardingFailureClassifier.from_readiness(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.COMPLETED,
                    app_text("ComfyUI passed its readiness checks."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                require_setup_current(cancellation)
                progress.transition(
                    SetupTaskId.COMMIT,
                    SetupTaskState.RUNNING,
                    app_text("Saving the completed setup."),
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )
            else:
                if model_install_plan is not None and model_install_plan.files:
                    raise ValueError(
                        "Remote ComfyUI setup cannot install files into a local model root."
                    )
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                    ),
                )
                transaction_id = transaction.transaction_id
                on_status(app_text("Saving your remote ComfyUI connection."))
                on_log(
                    app_text(
                        "Remote endpoint: %1:%2",
                        draft.endpoint_host,
                        draft.endpoint_port,
                    )
                )
                pending_context = bundle.onboarding_service.build_remote_context(
                    endpoint=endpoint,
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self.preference_application.save_setup(
                    service=bundle.preference_setup_service,
                    selection=draft,
                )
                progress.transition(
                    SetupTaskId.CONFIGURATION,
                    SetupTaskState.COMPLETED,
                    app_text("Setup choices are ready."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.RUNNING,
                    app_text("Preparing Substitute's local runtime."),
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                progress.transition(
                    SetupTaskId.RUNTIME,
                    SetupTaskState.COMPLETED,
                    app_text("Substitute's local runtime is ready."),
                )
                progress.transition(
                    SetupTaskId.COMFY_WORKSPACE,
                    SetupTaskState.SKIPPED,
                    app_text(
                        "Remote ComfyUI does not need local workspace preparation."
                    ),
                )
                progress.transition(
                    SetupTaskId.MODEL_DOWNLOAD,
                    SetupTaskState.SKIPPED,
                    app_text("Remote ComfyUI does not use local model downloads."),
                )
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.RUNNING,
                    app_text("Checking the remote ComfyUI connection."),
                )
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise OnboardingFailureClassifier.from_readiness(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                progress.transition(
                    SetupTaskId.VALIDATION,
                    SetupTaskState.COMPLETED,
                    app_text("The remote ComfyUI connection is ready."),
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                require_setup_current(cancellation)
                progress.transition(
                    SetupTaskId.COMMIT,
                    SetupTaskState.RUNNING,
                    app_text("Saving the completed setup."),
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )

            assessment = bundle.readiness_service.assess()
            if assessment.route is not BootstrapRoute.READY:
                raise OnboardingFailureClassifier.from_readiness(
                    draft=draft,
                    target_mode=target_mode,
                    assessment=assessment,
                )
            launch_command = self.runtime_launch_planner.build(
                runtime_service=bundle.runtime_service,
                runtime=context.runtime,
                entrypoint_path=self.entrypoint_path,
            )
            self.preference_application.save_optional_credentials(
                service=bundle.preference_setup_service,
                credential_draft=credential_draft,
                on_log=on_log,
            )
            progress.transition(
                SetupTaskId.COMMIT,
                SetupTaskState.COMPLETED,
                app_text("Setup is saved and ready."),
            )
            return OnboardingCompletionResult(
                context=context,
                restart_required=restart_required,
                launch_command=launch_command,
            )
        except OnboardingProvisioningFailure as error:
            if transaction_id is not None:
                record_setup_transaction_failure(
                    service=bundle.setup_transaction_service,
                    transaction_id=transaction_id,
                    error=error,
                )
            raise replace(
                error,
                transaction_id=transaction_id,
                failed_task=(
                    progress.current_task_id.value
                    if progress.current_task_id is not None
                    else None
                ),
            )
        except Exception as error:
            if transaction_id is not None:
                record_setup_transaction_failure(
                    service=bundle.setup_transaction_service,
                    transaction_id=transaction_id,
                    error=error,
                )
            failure = OnboardingFailureClassifier.from_exception(
                draft=draft,
                target_mode=target_mode,
                error=error,
            )
            raise replace(
                failure,
                transaction_id=transaction_id,
                failed_task=(
                    progress.current_task_id.value
                    if progress.current_task_id is not None
                    else None
                ),
            ) from error

    @staticmethod
    def _managed_model_root_for_save(draft: OnboardingDraftState) -> Path | None:
        """Return the selected managed model root, preserving explicit defaults."""

        if not draft.managed_model_root_uses_default:
            return draft.managed_model_root
        return None

    def _configure_shared_model_library(
        self,
        workspace: Path,
        models_root: Path | None,
    ) -> None:
        """Expose a selected shared model library after Comfy exists."""

        configurator = self.external_model_library_configurator
        if configurator is None:
            return
        configurator.configure(workspace, models_root)
