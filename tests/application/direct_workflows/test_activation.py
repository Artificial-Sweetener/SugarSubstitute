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

"""Verify direct-workflow node activation semantics."""

from __future__ import annotations

from pathlib import Path

from substitute.application.node_behavior import NodeBehaviorService
from substitute.domain.comfy_workflow import ComfyWorkflowConverter, DirectWorkflowState


class _NoNodeDefinitions:
    """Satisfy node behavior construction for activation-only tests."""

    def get_node_definition(self, class_type: str) -> dict[str, object]:
        """Return no live definition for the unused class lookup."""
        _ = class_type
        return {}

    def get_required_node_definition(self, class_type: str) -> dict[str, object]:
        """Return no required live definition for the unused class lookup."""
        _ = class_type
        return {}


def _direct_state(*, mode: int | None = None) -> DirectWorkflowState:
    """Build a direct workflow containing one executable node."""
    node: dict[str, object] = {
        "id": 9,
        "type": "PreviewImage",
        "inputs": [],
        "outputs": [],
        "widgets_values": [],
    }
    if mode is not None:
        node["mode"] = mode
    source_workflow: dict[str, object] = {"nodes": [node], "links": []}
    return DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow=source_workflow,
        buffer=ComfyWorkflowConverter().convert(source_workflow),
    )


def test_direct_workflow_activation_uses_comfy_mode() -> None:
    """Persist disabled direct state with Comfy's bypass mode."""
    state = _direct_state()

    state.set_node_activation("9", enabled=False)

    assert state.buffer["nodes"]["9"]["mode"] == 4  # type: ignore[index]
    assert state.source_workflow["nodes"][0]["mode"] == 4  # type: ignore[index]
    assert state.dirty is True


def test_shared_node_behavior_toggle_uses_direct_comfy_bypass_mode() -> None:
    """Avoid writing Sugar enabled fields through shared toggle orchestration."""
    state = _direct_state(mode=0)
    service = NodeBehaviorService(node_definition_gateway=_NoNodeDefinitions())

    service.toggle_node_activation_override(state, "9")

    node = state.buffer["nodes"]["9"]  # type: ignore[index]
    assert node["mode"] == 4
    assert "enabled" not in node
    assert state.source_workflow["nodes"][0]["mode"] == 4  # type: ignore[index]

    service.toggle_node_activation_override(state, "9")

    assert node["mode"] == 0
    assert state.source_workflow["nodes"][0]["mode"] == 0  # type: ignore[index]
