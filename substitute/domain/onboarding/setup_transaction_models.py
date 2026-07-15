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

"""Define pending setup transaction state for interruption-safe onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
)
from substitute.domain.onboarding.models import (
    ComfyTargetConfiguration,
    InstallationConfiguration,
    RuntimeConfiguration,
)


class SetupTransactionMode(str, Enum):
    """Describe why one pending setup transaction exists."""

    FIRST_RUN = "first_run"
    REPAIR = "repair"
    RECONFIGURE = "reconfigure"
    STARTUP_REVALIDATION = "startup_revalidation"


class SetupTransactionStatus(str, Enum):
    """Describe the current durable phase of one setup transaction."""

    CREATED = "created"
    RUNTIME_PROVISIONING = "runtime_provisioning"
    TARGET_PROVISIONING = "target_provisioning"
    MANAGED_RUNTIME_SELECTING = "managed_runtime_selecting"
    MANAGED_WORKSPACE_PROVISIONING = "managed_workspace_provisioning"
    MANAGED_WORKSPACE_VALIDATING = "managed_workspace_validating"
    READY_TO_COMMIT = "ready_to_commit"
    FAILED = "failed"


@dataclass(frozen=True)
class SetupTransactionFailure:
    """Capture a recoverable setup failure without mutating active state."""

    code: str
    message: str
    recoverable: bool
    diagnostic_detail: str | None = None


@dataclass(frozen=True)
class SetupTransaction:
    """Capture pending setup state that has not been promoted to active config."""

    schema_version: int
    transaction_id: str
    mode: SetupTransactionMode
    status: SetupTransactionStatus
    created_at: datetime
    updated_at: datetime
    installation: InstallationConfiguration | None = None
    runtime: RuntimeConfiguration | None = None
    target: ComfyTargetConfiguration | None = None
    managed_runtime: ManagedRuntimeConfiguration | None = None
    workspace_path: Path | None = None
    endpoint_host: str | None = None
    endpoint_port: int | None = None
    force_cpu_mode: bool = False
    prefer_edge_torch: bool = False
    prefer_edge_comfy_channel: bool = False
    failure: SetupTransactionFailure | None = None


__all__ = [
    "SetupTransaction",
    "SetupTransactionFailure",
    "SetupTransactionMode",
    "SetupTransactionStatus",
]
