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

"""Verify enabled-switch policy derived from node behavior."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from substitute.application.node_behavior import NodeDisplayDecision, TitleControl
import substitute.presentation.editor.panel.node_card_builder as node_card_builder
from tests.presentation.editor.node_card.support import Panel
from tests.support.node_behavior import build_behavior_snapshot


def test_undecided_resolver_omits_enabled_switch() -> None:
    """Omit enabled-switch controls for nodes without an activation policy."""

    definitions: dict[str, dict[str, object]] = {
        "CustomPatch": {"input": {}, "output": []}
    }
    nodes: dict[str, dict[str, object]] = {
        "patch": {"class_type": "CustomPatch", "inputs": {}}
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    resolved = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class={"CustomPatch": definitions["CustomPatch"]},
    ).resolved_nodes_by_alias["A"]["patch"]

    assert TitleControl.ENABLED_SWITCH not in resolved.card.title_controls


def test_checkpoint_switch_policy_uses_authored_bypass() -> None:
    """Derive checkpoint switch visibility from authored bypass state."""

    panel = Panel()
    cube_a = SimpleNamespace(
        buffer={
            "nodes": {"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            "definitions": {},
        },
        ui={},
    )
    cube_b = SimpleNamespace(
        buffer={
            "nodes": {
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {},
                    "mode": 4,
                }
            },
            "definitions": {},
        },
        ui={},
    )
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )

    assert (
        TitleControl.ENABLED_SWITCH
        not in snapshot.resolved_nodes_by_alias["A"]["ckpt"].card.title_controls
    )
    assert (
        TitleControl.ENABLED_SWITCH
        not in snapshot.resolved_nodes_by_alias["B"]["ckpt"].card.title_controls
    )
    assert snapshot.card_decisions_by_alias["A"]["ckpt"].show_enabled_switch is False
    assert snapshot.card_decisions_by_alias["B"]["ckpt"].show_enabled_switch is True


def test_disabling_revealed_default_disabled_node_keeps_explicit_override() -> None:
    """Preserve an explicit disabled override for a revealed default-disabled node."""

    decision = NodeDisplayDecision(
        visible=True,
        enabled=True,
        reason="explicit:enabled",
        revealable=True,
        reveal_checked=True,
        show_enabled_switch=True,
        policy_default_enabled=False,
        explicit_override=True,
        explicit_revealed=True,
    )
    switch_override_for_next_state = cast(
        Callable[[NodeDisplayDecision, bool], bool],
        getattr(node_card_builder, "_switch_override_for_next_state"),
    )

    assert switch_override_for_next_state(decision, False) is False
