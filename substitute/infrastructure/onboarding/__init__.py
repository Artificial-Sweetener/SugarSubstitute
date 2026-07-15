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

"""Export filesystem-backed onboarding repositories."""

from substitute.infrastructure.onboarding.file_comfy_target_repository import (
    FileComfyTargetConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_installation_repository import (
    FileInstallationConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_managed_runtime_repository import (
    FileManagedRuntimeConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_setup_transaction_repository import (
    FileSetupTransactionRepository,
)
from substitute.infrastructure.onboarding.file_runtime_repository import (
    FileRuntimeConfigurationRepository,
)
from substitute.infrastructure.onboarding.substitute_runtime_provisioner import (
    SubstituteRuntimeProvisioner,
)
from substitute.infrastructure.onboarding.launcher_managed_runtime_provisioner import (
    LauncherManagedRuntimeProvisioner,
)

__all__ = [
    "FileComfyTargetConfigurationRepository",
    "FileInstallationConfigurationRepository",
    "FileManagedRuntimeConfigurationRepository",
    "FileSetupTransactionRepository",
    "FileRuntimeConfigurationRepository",
    "LauncherManagedRuntimeProvisioner",
    "SubstituteRuntimeProvisioner",
]
