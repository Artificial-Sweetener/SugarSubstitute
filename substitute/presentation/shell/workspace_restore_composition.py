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

"""Compose workspace restoration with durable mask recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from substitute.infrastructure.persistence.workflow_mask_asset_recovery import (
    WorkflowMaskAssetRecovery,
)
from substitute.presentation.shell.workspace_restore_image_adapter import (
    WorkspaceRestoreImageAdapter,
)


def build_workspace_restore_image_adapter(shell: Any) -> WorkspaceRestoreImageAdapter:
    """Build image restoration against the shell's authoritative project root."""

    return WorkspaceRestoreImageAdapter(
        shell,
        mask_asset_recovery=WorkflowMaskAssetRecovery(
            projects_dir=Path(shell.path_bundle.projects_dir)
        ),
    )


__all__ = ["build_workspace_restore_image_adapter"]
