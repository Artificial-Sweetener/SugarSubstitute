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

"""Verify authored-bypass checkpoint activation through the behavior service."""

from __future__ import annotations

from tests.support.node_behavior import build_behavior_snapshot, cube_state


def _checkpoint_cube(
    *,
    enabled: bool | None = None,
    revealed: bool = False,
    bypassed: bool = False,
) -> object:
    """Build one checkpoint-loader cube with optional editor metadata."""

    node: dict[str, object] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "model.safetensors"},
    }
    if bypassed:
        node["mode"] = 4
    if enabled is not None:
        node["enabled"] = enabled
    if revealed:
        node["revealed"] = True
    return cube_state(nodes={"ckpt": node})


def test_bypass_authored_checkpoint_is_hidden_and_disabled_by_default() -> None:
    """Start an authored-bypass checkpoint hidden and inactive."""

    snapshot = build_behavior_snapshot(
        cube_states={"A": _checkpoint_cube(), "B": _checkpoint_cube(bypassed=True)},
        stack_order=["A", "B"],
    )

    decision = snapshot.card_decisions_by_alias["B"]["ckpt"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.reason == "policy:authored-bypass"
    assert decision.revealable is True


def test_revealing_bypass_authored_checkpoint_makes_it_visible_but_disabled() -> None:
    """Show an authored-bypass checkpoint without activating it."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": _checkpoint_cube(),
            "B": _checkpoint_cube(bypassed=True, revealed=True),
        },
        stack_order=["A", "B"],
    )

    decision = snapshot.card_decisions_by_alias["B"]["ckpt"]
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.explicit_override is None
    assert decision.explicit_revealed is True
    assert decision.reveal_checked is True


def test_revealed_bypass_authored_checkpoint_can_be_enabled_explicitly() -> None:
    """Require reveal visibility before activating an authored-bypass checkpoint."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": _checkpoint_cube(),
            "B": _checkpoint_cube(bypassed=True, enabled=True, revealed=True),
        },
        stack_order=["A", "B"],
    )

    decision = snapshot.card_decisions_by_alias["B"]["ckpt"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.explicit_override is True
    assert decision.explicit_revealed is True


def test_enabled_bypass_authored_checkpoint_without_reveal_stays_hidden() -> None:
    """Prevent an enabled-but-hidden authored-bypass checkpoint state."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": _checkpoint_cube(),
            "B": _checkpoint_cube(bypassed=True, enabled=True),
        },
        stack_order=["A", "B"],
    )

    decision = snapshot.card_decisions_by_alias["B"]["ckpt"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.explicit_override is True
    assert decision.reveal_checked is False
