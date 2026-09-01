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

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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
from launcher.sugarsubstitute_launcher.config import (
    CANARY_RELEASE_CHANNEL,
    DEFAULT_CANARY_RELEASE_MANIFEST_URL,
    DEFAULT_RELEASE_MANIFEST_URL,
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
    ReleaseSourceConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.managed_comfy_repair import (
    SubprocessManagedComfyRepairer,
)
from launcher.sugarsubstitute_launcher.payload_staging import validate_app_payload
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.repair_ownership import load_comfy_ownership
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.staging import validate_staged_bundle
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)


class RepairExecutionError(RuntimeError):
    """Report a prepared repair that cannot be executed or validated safely."""


class ManagedComfyRepairer(Protocol):
    """Restore and validate app-owned content inside proven managed Comfy."""

    def repair_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Restore the exact app-owned custom-node versions."""

    def validate_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Raise unless both app-owned nodepacks are ready."""

    def stage_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
        destination: Path,
    ) -> None:
        """Build a fresh managed workspace outside the active Comfy tree."""

    def validate_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Raise unless the promoted managed workspace is complete."""


class RepairInstallationStateWriter(Protocol):
    """Recreate and validate launcher state inside the transaction boundary."""

    def write(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Write fresh state for the repaired exact version."""

    def validate(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Raise unless persisted state identifies the repaired version."""


class FreshRepairInstallationStateWriter:
    """Own fresh launcher configuration and exact installed-version records."""

    def write(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Create default channel configuration and exact version records."""

        manifest_url = (
            DEFAULT_CANARY_RELEASE_MANIFEST_URL
            if request.channel == CANARY_RELEASE_CHANNEL
            else DEFAULT_RELEASE_MANIFEST_URL
        )
        LauncherConfig.from_layout(
            layout=layout,
            channel=request.channel,
            release_source=ReleaseSourceConfig(
                kind=RELEASE_SOURCE_KIND_GITHUB,
                manifest_url=manifest_url,
            ),
        ).save(layout.config_path)
        LauncherUpdateState().with_installed_payload(
            version=request.version,
            channel=request.channel,
        ).save(layout.state_path)
        LauncherInstallationRecord(
            version=request.version,
            target_key=request.target_key,
        ).save(layout.launcher_installation_path)

    def validate(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Verify config and both exact installed-version records."""

        config = LauncherConfig.load(layout.config_path)
        state = LauncherUpdateState.load(layout.state_path)
        launcher = LauncherInstallationRecord.load(layout.launcher_installation_path)
        if (
            config.install_root.resolve() != layout.root
            or config.channel != request.channel
            or state.installed_app_version != request.version
            or launcher is None
            or launcher.version != request.version
            or launcher.target_key != request.target_key
        ):
            raise RepairExecutionError(
                "Repaired launcher state does not match the prepared release."
            )


@dataclass(frozen=True, slots=True)
class CompletedRepair:
    """Describe one committed repair and its retained rollback quarantine."""

    version: str
    quarantine_root: Path
    repaired_managed_comfy_nodes: bool
    comfy_quarantine_root: Path | None = None


class RepairExecutionService:
    """Validate, apply, and prove one exact-version application repair."""

    def __init__(
        self,
        *,
        runtime_provisioner: RuntimeProvisioner | None = None,
        comfy_repairer: ManagedComfyRepairer | None = None,
        state_writer: RepairInstallationStateWriter | None = None,
        transaction: RepairTransaction | None = None,
    ) -> None:
        """Store repair adapters whose side effects remain transaction-bound."""

        self._runtime_provisioner = runtime_provisioner or UvManagedRuntimeInstaller()
        self._comfy_repairer = comfy_repairer or SubprocessManagedComfyRepairer()
        self._state_writer = state_writer or FreshRepairInstallationStateWriter()
        self._transaction = transaction or RepairTransaction()

    def execute_application(self, request: PreparedRepairRequest) -> CompletedRepair:
        """Commit one prepared application repair or restore the prior install."""

        if request.scope not in {
            RepairScope.APPLICATION,
            RepairScope.FULL_MANAGED_COMFY,
        }:
            raise RepairExecutionError(
                f"Application executor cannot run scope: {request.scope.value}"
            )
        target = launcher_target_for_key(request.target_key)
        layout = InstallLayout.from_root(request.install_root, target=target)
        launcher_target = launcher_bundle_target_for_key(request.target_key)
        self._validate_staging(
            request=request,
            launcher_target=launcher_target,
        )
        ownership = load_comfy_ownership(layout)
        repair_owned_nodes = _is_exact_managed_ownership(layout, ownership)
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
        replacements.extend(
            RepairReplacement(
                destination=layout.root / replacement_root,
                staged_path=request.staged_launcher_dir / replacement_root,
            )
            for replacement_root in launcher_target.replacement_roots
        )
        runtime_result: list[RuntimeProvisioningOutcome] = []

        def apply_repair() -> None:
            """Provision every candidate component before final validation."""

            runtime_result.append(self._runtime_provisioner.provision(layout=layout))
            if repair_owned_nodes:
                assert ownership is not None
                self._comfy_repairer.repair_owned_nodes(
                    layout=layout,
                    ownership=ownership,
                )
            self._state_writer.write(layout=layout, request=request)

        def validate_repair() -> None:
            """Prove the promoted release before the transaction can commit."""

            if (
                len(runtime_result) != 1
                or not runtime_result[0].python_executable.is_file()
            ):
                raise RepairExecutionError("Repaired runtime Python is unavailable.")
            validate_app_payload(layout.app_dir)
            if inspect_app_payload_version(layout.app_dir) != request.version:
                raise RepairExecutionError(
                    "Promoted application version does not match the repair request."
                )
            for replacement_root in launcher_target.replacement_roots:
                if not (layout.root / replacement_root).exists():
                    raise RepairExecutionError(
                        f"Promoted launcher root is missing: {replacement_root}"
                    )
            if repair_owned_nodes:
                assert ownership is not None
                self._comfy_repairer.validate_owned_nodes(
                    layout=layout,
                    ownership=ownership,
                )
            self._state_writer.validate(layout=layout, request=request)

        quarantine = self._transaction.execute(
            plan=plan,
            replacements=tuple(replacements),
            apply_repair=apply_repair,
            validate_repair=validate_repair,
        )
        comfy_quarantine = (
            self._execute_full_managed_comfy(
                layout=layout,
                ownership=ownership,
                version=request.version,
            )
            if request.scope is RepairScope.FULL_MANAGED_COMFY
            else None
        )
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
        version: str,
    ) -> Path:
        """Stage fresh core/runtime, then atomically preserve and promote boundaries."""

        if not _is_exact_managed_ownership(layout, ownership):
            raise RepairExecutionError(
                "Full managed Comfy repair requires exact installer ownership."
            )
        assert ownership is not None
        candidate = layout.root / ".repair" / "staging" / version / "full-comfy"
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
            replacement_names=replacement_names,
        )
        active = ownership.workspace_root
        assert active is not None
        replacements = [
            RepairReplacement(
                destination=active / name,
                staged_path=candidate / name,
            )
            for name in sorted(replacement_names)
        ]
        for node_name in ("substitute-backend", "SugarCubes"):
            replacements.append(
                RepairReplacement(
                    destination=active / "custom_nodes" / node_name,
                    staged_path=candidate / "custom_nodes" / node_name,
                )
            )
        return self._transaction.execute(
            plan=plan,
            replacements=tuple(replacements),
            validate_repair=lambda: self._comfy_repairer.validate_full_managed_comfy(
                layout=layout,
                ownership=ownership,
            ),
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
        validate_staged_bundle(
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


__all__ = [
    "CompletedRepair",
    "FreshRepairInstallationStateWriter",
    "ManagedComfyRepairer",
    "RepairExecutionError",
    "RepairExecutionService",
    "RepairInstallationStateWriter",
]
