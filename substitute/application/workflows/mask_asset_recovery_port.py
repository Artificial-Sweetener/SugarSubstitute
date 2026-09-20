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

"""Define the restore boundary for non-destructive workflow mask recovery."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import InputMaskReference


class WorkflowMaskAssetRecoveryPort(Protocol):
    """Recover one unresolved mask reference without replacing source evidence."""

    def recover_reference(
        self,
        *,
        workflow_id: str,
        workflow: WorkflowState,
        reference: InputMaskReference,
        document_source_path: Path | None,
    ) -> InputMaskReference:
        """Return the original or a verified rebound recovery reference."""


__all__ = ["WorkflowMaskAssetRecoveryPort"]
