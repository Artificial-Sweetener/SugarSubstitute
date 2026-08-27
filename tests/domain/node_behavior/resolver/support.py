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

"""Provide concise contexts for layered resolver tests."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    NodeBehaviorContext,
    NodeBehaviorPatch,
    PackageBehaviorPatch,
)


def context(
    *,
    node_name: str = "node",
    class_type: str = "CustomNode",
    declarative_patch: PackageBehaviorPatch | None = None,
    hook_patch: PackageBehaviorPatch | None = None,
    runtime_patch: NodeBehaviorPatch | None = None,
) -> NodeBehaviorContext:
    """Return one standard layered resolver context."""

    return NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name=node_name,
        class_type=class_type,
        node_title=None,
        live_node_definition=None,
        declarative_patch=declarative_patch,
        hook_patch=hook_patch,
        workflow_overrides={},
        node_instance_patch=runtime_patch,
    )


__all__ = ["context"]
