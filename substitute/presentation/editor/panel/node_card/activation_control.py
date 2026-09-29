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

"""Apply node-card activation-switch policy to workflow state."""

from __future__ import annotations

from typing import Any

from substitute.application.node_behavior import NodeDisplayDecision
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle


def activation_override_for_switch_state(
    decision: NodeDisplayDecision,
    next_checked: bool,
) -> bool | None:
    """Return the explicit activation override represented by a switch state."""

    if next_checked:
        return None if decision.policy_default_enabled else True
    return False


def apply_node_activation_change(
    panel: Any,
    services: EditorPanelServiceBundle,
    cube_state: Any,
    node_name: str,
    display_decision: NodeDisplayDecision,
    checked: bool,
) -> None:
    """Persist one title-switch activation change through the panel service."""

    services.node_behavior_service.set_node_activation_override(
        cube_state,
        node_name,
        activation_override_for_switch_state(display_decision, checked),
    )
    panel.refresh_node_behavior_state(reason="node_activation_changed")


__all__ = ["activation_override_for_switch_state", "apply_node_activation_change"]
