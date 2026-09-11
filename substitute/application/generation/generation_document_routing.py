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

"""Classify workflow documents at the generation boundary."""

from __future__ import annotations

from substitute.domain.comfy_workflow import DirectWorkflowState


def direct_generation_document(workflow: object) -> DirectWorkflowState | None:
    """Return only ordinary direct workflows handled by Comfy's prompt route."""

    if getattr(workflow, "is_graph_backed_cube_workflow", False) is True:
        return None
    document = getattr(workflow, "direct_workflow", None)
    return document if isinstance(document, DirectWorkflowState) else None


def uses_graph_backed_cube_execution(workflow: object) -> bool:
    """Return whether execution must preserve a canonical Cube-owning graph."""

    return getattr(workflow, "is_graph_backed_cube_workflow", False) is True


__all__ = ["direct_generation_document", "uses_graph_backed_cube_execution"]
