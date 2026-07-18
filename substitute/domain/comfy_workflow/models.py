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

"""Define mutable direct-workflow state consumed by shared editor services."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from substitute.domain.common import JsonObject


class NodeActivationStorage(StrEnum):
    """Describe how an editable graph persists node activation changes."""

    ENABLED_OVERRIDE = "enabled_override"
    COMFY_MODE = "comfy_mode"


@dataclass
class DirectWorkflowState:
    """Store one normalized Comfy workflow as a complete editor document."""

    source_path: Path
    source_workflow: JsonObject
    buffer: JsonObject
    ui: dict[str, object] = field(default_factory=dict)
    dirty: bool = False

    @property
    def activation_storage(self) -> NodeActivationStorage:
        """Use Comfy node modes as the authoritative activation state."""

        return NodeActivationStorage.COMFY_MODE

    @property
    def shows_cube_section_title(self) -> bool:
        """Hide cube title chrome because this state represents a whole document."""

        return False

    @property
    def uses_node_titles_as_card_labels(self) -> bool:
        """Render preserved Comfy node titles instead of numeric graph identifiers."""

        return True

    def set_node_activation(self, node_name: str, enabled: bool) -> None:
        """Persist an editor switch change using Comfy active and bypass modes."""

        nodes = self.buffer.get("nodes")
        if not isinstance(nodes, dict):
            return
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            return
        next_mode = 0 if enabled else 4
        if node.get("mode", 0) == next_mode:
            return
        node["mode"] = next_mode
        self.dirty = True

    def duplicate(self) -> DirectWorkflowState:
        """Return an independent authoring copy without live editor runtime objects."""

        return DirectWorkflowState(
            source_path=self.source_path,
            source_workflow=deepcopy(self.source_workflow),
            buffer=deepcopy(self.buffer),
            ui={
                key: deepcopy(value)
                for key, value in self.ui.items()
                if key != "node_behavior_runtime"
            },
            dirty=self.dirty,
        )
