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

from typing import Any

from substitute.presentation.editor.panel.panel_workflow_projection import (
    workflow_for_panel,
)
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
    workflow = workflow_for_panel(panel)
    if workflow is None:
        return False
    _normalize_prompt_names(panel, cube_alias, node_name)
    projected = RegionalMaskEditorProjector().project_editor(
        widget,
        workflow,
        (cube_alias, node_name),
    )
    if projected:
        _bind_active_node_previews(panel)
    return projected


def _bind_active_node_previews(panel: object) -> None:
    """Bind this exact panel after projection makes its rows addressable."""

    mainwindow = getattr(panel, "mainwindow", None)
    preview_coordinator = getattr(mainwindow, "input_node_preview_coordinator", None)
    bind_panel = getattr(preview_coordinator, "bind_panel", None)
    if callable(bind_panel):
        bind_panel(panel)


def _normalize_prompt_names(panel: object, cube_alias: str, node_name: str) -> None:
    """Normalize related canonical prompt values before projecting mask labels."""

    mainwindow = getattr(panel, "mainwindow", None)
    coordinator = getattr(mainwindow, "regional_interaction_coordinator", None)
    normalize = getattr(coordinator, "normalize_prompt_names_for_mask", None)
    if callable(normalize):
        normalize(panel, cube_alias, node_name)


__all__ = ["project_regional_panel_widget"]
