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

"""Define how editable Comfy workflow nodes participate in API execution."""

from __future__ import annotations

from enum import StrEnum


class WorkflowNodeExecutionRole(StrEnum):
    """Describe one editor node's lowering behavior for Comfy execution."""

    EXECUTABLE = "executable"
    VALUE_PROXY = "value_proxy"
    ROUTING = "routing"
    ANNOTATION = "annotation"
    UNRESOLVED = "unresolved"


_KNOWN_ROLES_BY_CLASS: dict[str, WorkflowNodeExecutionRole] = {
    "MarkdownNote": WorkflowNodeExecutionRole.ANNOTATION,
    "Note": WorkflowNodeExecutionRole.ANNOTATION,
    "PrimitiveNode": WorkflowNodeExecutionRole.VALUE_PROXY,
    "Reroute": WorkflowNodeExecutionRole.ROUTING,
}


def known_execution_role(class_type: str) -> WorkflowNodeExecutionRole:
    """Return the built-in execution role for one serialized Comfy class."""

    return _KNOWN_ROLES_BY_CLASS.get(
        class_type,
        WorkflowNodeExecutionRole.EXECUTABLE,
    )


__all__ = ["WorkflowNodeExecutionRole", "known_execution_role"]
