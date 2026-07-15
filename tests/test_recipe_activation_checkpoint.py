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

"""Contract tests for authored-bypass checkpoint activation and reveal behavior."""

from __future__ import annotations

from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def _checkpoint_cube(
    *,
    enabled: bool | None = None,
    revealed: bool = False,
    bypassed: bool = False,
) -> object:
    """Return one cube containing a checkpoint loader with optional editor metadata."""

    node = {
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


def test_checkpoint_loaders_without_authored_bypass_are_visible_and_enabled() -> None:
    """Checkpoint visibility should not depend on stack position."""

    cubes = {
        "A": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "model-a.safetensors"},
                }
            }
        ),
        "B": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "model-b.safetensors"},
                }
            }
        ),
    }

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])

    assert snapshot.card_decisions_by_alias["A"]["ckpt"].visible is True
    assert snapshot.card_decisions_by_alias["A"]["ckpt"].enabled is True
    assert snapshot.card_decisions_by_alias["A"]["ckpt"].revealable is False
    assert snapshot.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert snapshot.card_decisions_by_alias["B"]["ckpt"].enabled is True
    assert snapshot.card_decisions_by_alias["B"]["ckpt"].revealable is False


def test_reordering_does_not_change_checkpoint_visibility_or_activation() -> None:
    """Stack order should not promote or hide checkpoint loader cards."""

    cubes = {
        "A": _checkpoint_cube(),
        "B": _checkpoint_cube(),
    }

    first = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])
    reordered = build_behavior_snapshot(cube_states=cubes, stack_order=["B", "A"])

    assert first.card_decisions_by_alias["A"]["ckpt"].visible is True
    assert first.card_decisions_by_alias["A"]["ckpt"].enabled is True
    assert first.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert first.card_decisions_by_alias["B"]["ckpt"].enabled is True
    assert reordered.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert reordered.card_decisions_by_alias["B"]["ckpt"].enabled is True
    assert reordered.card_decisions_by_alias["A"]["ckpt"].visible is True
    assert reordered.card_decisions_by_alias["A"]["ckpt"].enabled is True


def test_bypass_authored_checkpoint_is_hidden_and_disabled_by_default() -> None:
    """Authored bypass should start checkpoint loaders hidden and inactive."""

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
    """Explicit reveal should show bypass-authored checkpoints without activating them."""

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
    """Bypass-authored checkpoints should require reveal visibility before activation."""

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
    """Activation overrides must not create an enabled-but-hidden checkpoint state."""

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
