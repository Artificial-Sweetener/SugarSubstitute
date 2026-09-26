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

"""Build truthful node cards for saved nodes missing live Comfy metadata."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.application.node_behavior import DegradedNodeBehavior

from .runtime_issue_card import build_runtime_issue_card


def build_degraded_node_card(
    node: DegradedNodeBehavior,
    *,
    parent: QWidget | None = None,
) -> QWidget:
    """Build a red-washed card from persisted identity and missing facts only."""

    issue_lines = tuple(
        app_text("Missing definition: %1", class_type)
        for class_type in node.missing_definition_classes
    ) + tuple(
        app_text("Missing field: %1", field_name) for field_name in node.missing_fields
    )
    return build_runtime_issue_card(
        issue_lines,
        title_text=node.title,
        object_name="DegradedNodeCard",
        parent=parent,
    )


__all__ = ["build_degraded_node_card"]
