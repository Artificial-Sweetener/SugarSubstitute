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

"""Adapt editor-panel state for one node-card build pass."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodePanelSnapshot:
    """Capture the panel state required by node-card contextual controls."""

    cube_id: str | None
    current_alias: str | None
    cube_states: Mapping[str, Any]
    stack_order: Sequence[str]

    def first_alias_for_class_type(self, node_type: str) -> str | None:
        """Return the first ordered cube alias containing one node class."""

        for alias in self.stack_order:
            cube_state = self.cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", {}) if cube_state is not None else {}
            for node_data in (buffer.get("nodes", {}) or {}).values():
                if (
                    isinstance(node_data, dict)
                    and node_data.get("class_type") == node_type
                ):
                    return alias
        return None


def capture_node_panel_snapshot(
    *,
    panel: object,
    cube_state: object,
    alias: str | None,
) -> NodePanelSnapshot:
    """Capture the stable panel context used while one node card is composed."""

    cube_id = getattr(cube_state, "cube_id", None)
    raw_cube_states = getattr(panel, "_cube_states", None) or {}
    cube_states = raw_cube_states if isinstance(raw_cube_states, Mapping) else {}
    raw_stack_order = getattr(panel, "_stack_order", None) or []
    stack_order = raw_stack_order if isinstance(raw_stack_order, Sequence) else ()
    return NodePanelSnapshot(
        cube_id=cube_id if isinstance(cube_id, str) else None,
        current_alias=alias,
        cube_states=cube_states,
        stack_order=stack_order,
    )


__all__ = ["NodePanelSnapshot", "capture_node_panel_snapshot"]
