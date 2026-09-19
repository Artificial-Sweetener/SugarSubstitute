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

"""Adapt restored snapshot document state to the shell dirty-state owner."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from substitute.domain.workspace_snapshot.models import WorkflowSnapshot


def restore_document_states(
    shell: Any,
    workflows: Sequence[WorkflowSnapshot],
) -> None:
    """Restore durable dirty and source-path state when the owner is available."""

    unsaved_work_service = getattr(shell, "unsaved_work_service", None)
    restore = getattr(unsaved_work_service, "restore", None)
    if not callable(restore):
        return
    for workflow in workflows:
        restore(
            workflow.workflow_id,
            dirty=workflow.document_dirty,
            source_path=workflow.document_source_path,
        )


__all__ = ["restore_document_states"]
