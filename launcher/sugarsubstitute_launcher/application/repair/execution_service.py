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

"""Execute a prepared application repair as one validated transaction."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery

from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationOwnership,
    installation_mutation,
)

from pathlib import Path
from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgressObserver,
    RepairProgressTracker,
    RepairStage,
)

from launcher.sugarsubstitute_launcher.application.installation.models import (
    RuntimeProvisioner,
    RuntimeProvisioningOutcome,
)
from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    directory_tree_sha256,
    verify_directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
    RepairReplacement,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.application.repair.payload_version import (
    inspect_app_payload_version,
)
from launcher.sugarsubstitute_launcher.application.repair.plan_service import (
    RepairPlanService,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.managed_comfy_repair import (
    SubprocessManagedComfyRepairer,
)
from launcher.sugarsubstitute_launcher.payload_staging import validate_app_payload
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.repair_ownership import load_comfy_ownership
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from launcher.sugarsubstitute_launcher.application.repair.launcher_activation import (
    PreparedLauncherRepair,
)
from launcher.sugarsubstitute_launcher.repair_attempt_artifacts import (
    stage_repair_attempt,
)
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)


from launcher.sugarsubstitute_launcher.application.repair.execution_result import (
    RepairExecutionError,
    CompletedRepair,
)
from launcher.sugarsubstitute_launcher.application.repair.managed_comfy_contract import (
    ManagedComfyRepairer,
)
from launcher.sugarsubstitute_launcher.application.repair.installation_state_writer import (
    RepairInstallationStateWriter,
    FreshRepairInstallationStateWriter,
)


class RepairExecutionService:
    """Validate, apply, and prove one exact-version application repair."""

    def __init__(
        self,
        *,
        runtime_provisioner: RuntimeProvisioner,
        comfy_repairer: ManagedComfyRepairer | None = None,
        state_writer: RepairInstallationStateWriter | None = None,
        transaction: RepairTransaction | None = None,
        progress_observer: RepairProgressObserver | None = None,
    ) -> None:
        """Store repair adapters whose side effects remain transaction-bound."""

        self._runtime_provisioner = runtime_provisioner
        self._comfy_repairer = comfy_repairer or SubprocessManagedComfyRepairer()
        self._state_writer = state_writer or FreshRepairInstallationStateWriter()
        self._transaction = transaction or RepairTransaction()
        self._progress_observer = progress_observer

    def execute_application(
        self,
        request: PreparedRepairRequest,
        *,
        mutation: InstallationMutationOwnership | None = None,
    ) -> CompletedRepair:
        """Commit one prepared application repair or restore the prior install."""

        with installation_mutation(
            request.install_root, ownership=mutation
        ) as operation:
            if request.scope not in {
                RepairScope.APPLICATION,
                RepairScope.FULL_MANAGED_COMFY,
            }:
                raise RepairExecutionError(
                    f"Application executor cannot run scope: {request.scope.value}"
                )
            target = launcher_target_for_key(request.target_key)
            layout = InstallLayout.from_root(request.install_root, target=target)
            InstallationRecovery(layout).recover(ownership=operation)
            launcher_target = launcher_bundle_target_for_key(request.target_key)
            ownership = load_comfy_ownership(layout)
            repair_owned_nodes = _is_exact_managed_ownership(layout, ownership)
            progress = RepairProgressTracker(
                repair_nodes=repair_owned_nodes,
                full_comfy=request.scope is RepairScope.FULL_MANAGED_COMFY,
                observer=self._progress_observer,
            )
            progress.begin(RepairStage.VALIDATE_INPUT)
            self._validate_staging(request=request, launcher_target=launcher_target)
            request = stage_repair_attempt(request)
            plan = RepairPlanService().build_application_plan(
                layout=layout,
                comfy_ownership=ownership if repair_owned_nodes else None,
            )
            replacements = [
                RepairReplacement(
                    destination=layout.app_dir,
                    staged_path=request.staged_app_dir,
                )
            ]
            launcher_repair = PreparedLauncherRepair.prepare(request)
            replacements.append(launcher_repair.replacement)
            update_check = self._state_writer.capture_update_preferences(layout)
            runtime_result: list[RuntimeProvisioningOutcome] = []

            def apply_repair() -> None:
                """Provision every candidate component before final validation."""

                progress.begin(RepairStage.PREPARE_RUNTIME)
                runtime_result.append(
                    self._runtime_provisioner.provision(layout=layout)
                )
                if repair_owned_nodes:
                    assert ownership is not None
                    progress.begin(RepairStage.RESTORE_NODES)
                    self._comfy_repairer.repair_owned_nodes(
                        layout=layout,
                        ownership=ownership,
                    )
                progress.begin(RepairStage.SAVE_STATE)
                self._state_writer.write(
                    layout=layout, request=request, update_check=update_check
                )

            def validate_repair() -> None:
                """Prove the promoted release before the transaction can commit."""

                progress.begin(RepairStage.VALIDATE_APPLICATION)
                if (
                    len(runtime_result) != 1
                    or not runtime_result[0].python_executable.is_file()
                ):
                    raise RepairExecutionError(
                        "Repaired runtime Python is unavailable."
                    )
                validate_app_payload(layout.app_dir)
                if inspect_app_payload_version(layout.app_dir) != request.version:
                    raise RepairExecutionError(
                        "Promoted application version does not match the repair request."
                    )
                if repair_owned_nodes:
                    assert ownership is not None
                    self._comfy_repairer.validate_owned_nodes(
                        layout=layout,
                        ownership=ownership,
                    )
                self._state_writer.validate(
                    layout=layout, request=request, update_check=update_check
                )
                launcher_repair.validate()

            progress.begin(RepairStage.RESTORE_APPLICATION)
            quarantine = self._transaction.execute(
                plan=plan,
                replacements=tuple(replacements),
                apply_repair=apply_repair,
                validate_repair=validate_repair,
                ownership=operation,
            )
            comfy_quarantine = (
                self._execute_full_managed_comfy(
                    layout=layout,
                    ownership=ownership,
                    progress=progress,
                    candidate=request.staged_app_dir.parent / "full-comfy",
                    mutation=operation,
                )
                if request.scope is RepairScope.FULL_MANAGED_COMFY
                else None
            )
            progress.complete()
            return CompletedRepair(
                version=request.version,
                quarantine_root=quarantine,
                repaired_managed_comfy_nodes=repair_owned_nodes,
                comfy_quarantine_root=comfy_quarantine,
            )

    def _execute_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership | None,
        progress: RepairProgressTracker,
        candidate: Path,
        mutation: InstallationMutationOwnership,
    ) -> Path:
        """Stage fresh core/runtime, then atomically preserve and promote boundaries."""

        if not _is_exact_managed_ownership(layout, ownership):
            raise RepairExecutionError(
                "Full managed Comfy repair requires exact installer ownership."
            )
        assert ownership is not None
        progress.begin(RepairStage.PREPARE_COMFY)
        self._comfy_repairer.stage_full_managed_comfy(
            layout=layout,
            ownership=ownership,
            destination=candidate,
        )
        candidate_digest = directory_tree_sha256(candidate)
        verify_directory_tree_sha256(candidate, expected=candidate_digest)
        protected = {"user", "models", "input", "output", "custom_nodes"}
        replacement_names = frozenset(
            child.name for child in candidate.iterdir() if child.name not in protected
        )
        plan = RepairPlanService().build_full_managed_comfy_plan(
            layout=layout,
            comfy_ownership=ownership,
            replacement_names=replacement_names | {".venv"},
        )
        active = ownership.workspace_root
        assert active is not None
        replacements = [
            RepairReplacement(
                destination=active / name,
                staged_path=candidate / name,
            )
            for name in sorted(replacement_names - {".venv"})
        ]
        for node_name in ("substitute-backend", "SugarCubes"):
            replacements.append(
                RepairReplacement(
                    destination=active / "custom_nodes" / node_name,
                    staged_path=candidate / "custom_nodes" / node_name,
                )
            )

        def provision_comfy() -> None:
            """Create path-bound runtime files only after their master is promoted."""

            self._comfy_repairer.provision_full_managed_comfy(
                layout=layout,
                ownership=ownership,
            )

        def validate_comfy() -> None:
            """Report verification only after all managed replacements are promoted."""
            progress.begin(RepairStage.VALIDATE_COMFY)
            self._comfy_repairer.validate_full_managed_comfy(
                layout=layout,
                ownership=ownership,
            )

        progress.begin(RepairStage.RESTORE_COMFY)
        return self._transaction.execute(
            plan=plan,
            replacements=tuple(replacements),
            apply_repair=provision_comfy,
            validate_repair=validate_comfy,
            ownership=mutation,
        )

    @staticmethod
    def _validate_staging(
        *,
        request: PreparedRepairRequest,
        launcher_target: LauncherBundleTarget,
    ) -> None:
        """Revalidate immutable staging receipts and exact artifact contracts."""

        verify_directory_tree_sha256(
            request.staged_app_dir,
            expected=request.staged_app_sha256,
        )
        verify_directory_tree_sha256(
            request.staged_launcher_dir,
            expected=request.staged_launcher_sha256,
        )
        validate_app_payload(request.staged_app_dir)
        if inspect_app_payload_version(request.staged_app_dir) != request.version:
            raise RepairExecutionError(
                "Staged application version does not match the repair request."
            )
        validate_launcher_bundle(
            bundle_dir=request.staged_launcher_dir,
            target=launcher_target,
        )


def _is_exact_managed_ownership(
    layout: InstallLayout,
    ownership: ManagedComfyOwnership | None,
) -> bool:
    """Return whether persisted evidence proves this installation's Comfy root."""

    return (
        ownership is not None
        and ownership.target_mode == "managed_local"
        and ownership.install_owned
        and ownership.workspace_root is not None
        and ownership.workspace_root.resolve() == (layout.root / "comfyui").resolve()
    )
