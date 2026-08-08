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

"""Project workflow-owned mask opacity into newly mounted node controls."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.panel_workflow_projection import (
    workflow_for_panel,
)


def project_mask_visual_opacity(
    widget: object,
    panel: object,
    *,
    cube_alias: str | None,
    node_name: str,
) -> bool:
    """Initialize one compatible mask widget from its workflow authority."""

    setter = getattr(widget, "set_visual_opacity", None)
    if cube_alias is None or not callable(setter):
        return False
    workflow = workflow_for_panel(panel)
    if workflow is None:
        return False
    cast(Callable[[float], None], setter)(
        workflow.canvas.mask_visual_opacity((cube_alias, node_name))
    )
    return True


def project_mask_visual_opacity_value(
    panel: object,
    *,
    cube_alias: str,
    node_name: str,
    opacity: float,
) -> bool:
    """Project a restored history value into one mounted mask node control."""

    find_children = getattr(panel, "findChildren", None)
    if not callable(find_children):
        return False
    for widget in find_children(QWidget):
        metadata = widget.property("input_metadata")
        setter = getattr(widget, "set_visual_opacity", None)
        if (
            isinstance(metadata, dict)
            and metadata.get("cube_alias") == cube_alias
            and metadata.get("node_name") == node_name
            and callable(setter)
        ):
            cast(Callable[[float], None], setter)(opacity)
            return True
    return False


__all__ = [
    "project_mask_visual_opacity",
    "project_mask_visual_opacity_value",
]
