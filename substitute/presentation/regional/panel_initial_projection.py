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

"""Initialize regional panel widgets from their durable workflow authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from substitute.domain.workflow import WorkflowState
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)
from substitute.presentation.regional.mask_editor_projection import (
    RegionalMaskEditorProjector,
)


def project_regional_panel_widget(
    widget: Any,
    panel: Any,
    *,
    cube_alias: str | None,
    node_name: str,
) -> bool:
    """Project a newly mounted regional editor from its panel's workflow."""

    if not isinstance(widget, RegionalMaskBatchEditor) or cube_alias is None:
        return False
    workflow = _panel_workflow(panel)
    if workflow is None:
        return False
    return RegionalMaskEditorProjector().project_editor(
        widget,
        workflow,
        (cube_alias, node_name),
    )


def _panel_workflow(panel: object) -> WorkflowState | None:
    """Resolve the workflow owning a panel without relying on active routing."""

    mainwindow = getattr(panel, "mainwindow", None)
    editor_panels = getattr(mainwindow, "editor_panels", None)
    session_service = getattr(mainwindow, "workflow_session_service", None)
    workflows = getattr(session_service, "workflows", None)
    if not isinstance(editor_panels, Mapping) or not isinstance(workflows, Mapping):
        return None
    workflow_id = next(
        (
            str(candidate_id)
            for candidate_id, candidate_panel in editor_panels.items()
            if candidate_panel is panel
        ),
        None,
    )
    workflow = workflows.get(workflow_id) if workflow_id is not None else None
    return workflow if isinstance(workflow, WorkflowState) else None


__all__ = ["project_regional_panel_widget"]
