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

"""Expose installer-owned repair planning contracts."""

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    CompletedRepair,
    FreshRepairInstallationStateWriter,
    ManagedComfyRepairer,
    RepairExecutionError,
    RepairExecutionService,
    RepairInstallationStateWriter,
)
from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
    RepairDisposition,
    RepairOperation,
    RepairPlan,
    RepairReplacement,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    RepairArtifactIntegrityError,
    directory_tree_sha256,
    verify_directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.application.repair.plan_service import (
    RepairPlanError,
    RepairPlanService,
)
from launcher.sugarsubstitute_launcher.application.repair.payload_version import (
    RepairPayloadVersionError,
    inspect_app_payload_version,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparation,
    RepairPreparationError,
    RepairPreparationService,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
    PreparedRepairRequestError,
)

__all__ = [
    "CompletedRepair",
    "FreshRepairInstallationStateWriter",
    "ManagedComfyOwnership",
    "ManagedComfyRepairer",
    "RepairArtifactIntegrityError",
    "RepairDisposition",
    "RepairExecutionError",
    "RepairExecutionService",
    "RepairInstallationStateWriter",
    "RepairOperation",
    "RepairPlan",
    "RepairPlanError",
    "RepairPlanService",
    "RepairPayloadVersionError",
    "RepairPreparation",
    "RepairPreparationError",
    "RepairPreparationService",
    "RepairReplacement",
    "RepairScope",
    "directory_tree_sha256",
    "inspect_app_payload_version",
    "PreparedRepairRequest",
    "PreparedRepairRequestError",
    "verify_directory_tree_sha256",
]
