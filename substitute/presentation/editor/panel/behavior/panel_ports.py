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

"""Adapt editor-panel behavior side effects to behavior applier ports."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from typing import Any, cast

from substitute.application.node_behavior import EditorBehaviorSnapshot

from .behavior_applier import (
    EditorBehaviorApplicationPorts,
    EditorBehaviorApplier,
    EditorBehaviorState,
)


def behavior_applier_for_panel(panel: object) -> EditorBehaviorApplier:
    """Return the panel behavior applier with explicit side-effect ports."""

    applier = getattr(panel, "_behavior_applier", None)
    if isinstance(applier, EditorBehaviorApplier):
        return applier
    applier = EditorBehaviorApplier(
        _behavior_state_for_panel(panel),
        EditorBehaviorApplicationPorts(
            card_wrapper=lambda cube_alias, node_name: _behavior_card_wrapper_for_panel(
                panel, cube_alias, node_name
            ),
            apply_hidden_field_keys=lambda hidden_keys: (
                _apply_behavior_hidden_field_keys(panel, hidden_keys)
            ),
            apply_node_card_decisions=lambda decisions: (
                _apply_node_card_behavior_decisions(panel, decisions)
            ),
            publish_behavior_snapshot=lambda snapshot: (
                _publish_behavior_snapshot_for_panel(panel, snapshot)
            ),
            rebuild_cube_visibility_menus=lambda: _rebuild_behavior_visibility_menus(
                panel
            ),
        ),
    )
    setattr(panel, "_behavior_applier", applier)
    return applier


def _behavior_state_for_panel(panel: object) -> EditorBehaviorState:
    """Return panel-owned behavior fallback state for snapshot application."""

    state = getattr(panel, "_behavior_state", None)
    if isinstance(state, EditorBehaviorState):
        return state
    state = EditorBehaviorState(
        last_card_decisions=dict(getattr(panel, "_last_card_decisions", {})),
        last_hidden_field_keys=set(getattr(panel, "_last_hidden_field_keys", set())),
    )
    setattr(panel, "_behavior_state", state)
    setattr(panel, "_last_card_decisions", state.last_card_decisions)
    setattr(panel, "_last_hidden_field_keys", state.last_hidden_field_keys)
    return state


def _behavior_card_wrapper_for_panel(
    panel: object,
    cube_alias: str,
    node_name: str,
) -> object | None:
    """Return the registered node-card wrapper for behavior visibility."""

    card_wrappers = getattr(panel, "card_wrappers", {})
    if not isinstance(card_wrappers, MappingABC):
        return None
    return card_wrappers.get((cube_alias, node_name))


def _apply_behavior_hidden_field_keys(panel: object, hidden_keys: set[object]) -> None:
    """Apply hidden-field state through the panel field-sync boundary."""

    set_hidden_field_keys = getattr(panel, "set_hidden_field_keys", None)
    if callable(set_hidden_field_keys):
        set_hidden_field_keys(set(hidden_keys))


def _apply_node_card_behavior_decisions(
    panel: object,
    decisions_by_alias: MappingABC[str, MappingABC[str, object]],
) -> None:
    """Apply card-mode behavior through the node-card behavior boundary."""

    apply_decisions = getattr(panel, "apply_node_card_behavior_decisions", None)
    if callable(apply_decisions):
        apply_decisions(decisions_by_alias)
        return
    node_card_controller = getattr(panel, "_node_card_mode_controller", None)
    if node_card_controller is not None:
        node_card_controller.apply_decisions(cast(Any, decisions_by_alias))


def _publish_behavior_snapshot_for_panel(
    panel: object,
    snapshot: EditorBehaviorSnapshot | None,
) -> None:
    """Publish the current behavior snapshot through panel prompt-context ownership."""

    set_current_behavior_snapshot = getattr(
        panel, "set_current_behavior_snapshot", None
    )
    if callable(set_current_behavior_snapshot):
        set_current_behavior_snapshot(snapshot)
    else:
        setattr(panel, "_last_behavior_snapshot", snapshot)


def _rebuild_behavior_visibility_menus(panel: object) -> None:
    """Refresh per-cube visibility menus after behavior state changes."""

    rebuild = getattr(panel, "_rebuild_all_cube_visibility_menus", None)
    if callable(rebuild):
        rebuild()
