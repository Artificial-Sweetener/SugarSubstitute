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

"""Contract tests for authored-bypass VAE activation and reveal behavior."""

from __future__ import annotations

from typing import Any

from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def _vae_cube(
    *,
    enabled: bool | None = None,
    revealed: bool = False,
    mode: Any = None,
) -> object:
    """Return one cube containing a VAE loader with optional editor metadata."""

    node = {"class_type": "VAELoader", "inputs": {}}
    if mode is not None:
        node["mode"] = mode
    if enabled is not None:
        node["enabled"] = enabled
    if revealed:
        node["revealed"] = True
    return cube_state(nodes={"vae": node})


def test_vae_loader_without_authored_bypass_is_visible_and_enabled() -> None:
    """VAE loader visibility should not be class-sensitive."""

    snapshot = build_behavior_snapshot(
        cube_states={"A": _vae_cube()},
        stack_order=["A"],
    )

    decision = snapshot.card_decisions_by_alias["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.revealable is False
    assert decision.reason == "default:active"


def test_string_mode_four_does_not_apply_authored_bypass_policy() -> None:
    """Only integer mode 4 should count as authored bypass metadata."""

    snapshot = build_behavior_snapshot(
        cube_states={"A": _vae_cube(mode="4")},
        stack_order=["A"],
    )

    decision = snapshot.card_decisions_by_alias["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.revealable is False


def test_bypass_authored_vae_is_hidden_and_disabled_by_default() -> None:
    """Authored bypass should start VAE loaders hidden and inactive."""

    cubes = {
        "A": _vae_cube(mode=4),
        "B": _vae_cube(mode=4),
    }

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])

    assert snapshot.card_decisions_by_alias["A"]["vae"].visible is False
    assert snapshot.card_decisions_by_alias["A"]["vae"].enabled is False
    assert (
        snapshot.card_decisions_by_alias["A"]["vae"].reason == "policy:authored-bypass"
    )
    assert snapshot.card_decisions_by_alias["B"]["vae"].visible is False
    assert snapshot.card_decisions_by_alias["B"]["vae"].enabled is False


def test_revealing_bypass_authored_vae_makes_it_visible_but_disabled() -> None:
    """Explicit reveal should show bypass-authored VAE nodes without activating them."""

    cubes = {
        "A": _vae_cube(mode=4, revealed=True),
        "B": _vae_cube(mode=4),
    }

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])

    decision = snapshot.card_decisions_by_alias["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.explicit_override is None
    assert decision.explicit_revealed is True
    assert decision.reveal_checked is True
    assert snapshot.card_decisions_by_alias["B"]["vae"].visible is False


def test_revealed_bypass_authored_vae_can_be_enabled_explicitly() -> None:
    """Activation should require both reveal visibility and explicit enable."""

    snapshot = build_behavior_snapshot(
        cube_states={"A": _vae_cube(mode=4, enabled=True, revealed=True)},
        stack_order=["A"],
    )

    decision = snapshot.card_decisions_by_alias["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.explicit_override is True
    assert decision.explicit_revealed is True


def test_enabled_bypass_authored_vae_without_reveal_stays_hidden_and_disabled() -> None:
    """Activation overrides must not create an enabled-but-hidden bypass state."""

    snapshot = build_behavior_snapshot(
        cube_states={"A": _vae_cube(mode=4, enabled=True)},
        stack_order=["A"],
    )

    decision = snapshot.card_decisions_by_alias["A"]["vae"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.explicit_override is True
    assert decision.reveal_checked is False
