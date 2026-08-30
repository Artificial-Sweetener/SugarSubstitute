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

"""Verify activation and reveal override decisions."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    CardBehavior,
    EditorBehaviorContext,
    PackageBehaviorPatch,
    ResolvedNodeBehavior,
    RevealMode,
    compute_editor_behavior,
)
from tests.domain.node_behavior.engine.support import cube


def test_bypass_authored_node_can_be_revealed_without_being_enabled() -> None:
    """Revealed bypass-authored nodes should stay inactive until explicitly enabled."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "vae": {
                        "class_type": "VAELoader",
                        "inputs": {},
                        "mode": 4,
                        "revealed": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "vae": ResolvedNodeBehavior(
                    node_name="vae",
                    class_type="VAELoader",
                    card=CardBehavior(reveal_mode=RevealMode.MENU),
                    fields={},
                )
            },
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
    )

    decisions, _hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch()},
    )

    decision = decisions["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reveal_checked is True
    assert decision.explicit_revealed is True


def test_bypass_authored_node_requires_reveal_before_enable_takes_effect() -> None:
    """Enabled overrides should not create enabled-but-hidden bypass state."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "vae": {
                        "class_type": "VAELoader",
                        "inputs": {},
                        "mode": 4,
                        "enabled": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "vae": ResolvedNodeBehavior(
                    node_name="vae",
                    class_type="VAELoader",
                    card=CardBehavior(reveal_mode=RevealMode.MENU),
                    fields={},
                )
            },
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
    )

    decisions, _hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch()},
    )

    decision = decisions["A"]["vae"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.explicit_override is True
    assert decision.reveal_checked is False


def test_bypass_authored_node_can_be_revealed_and_enabled_explicitly() -> None:
    """Bypass-authored nodes should activate only when both axes allow it."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "vae": {
                        "class_type": "VAELoader",
                        "inputs": {},
                        "mode": 4,
                        "enabled": True,
                        "revealed": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "vae": ResolvedNodeBehavior(
                    node_name="vae",
                    class_type="VAELoader",
                    card=CardBehavior(reveal_mode=RevealMode.MENU),
                    fields={},
                )
            },
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
    )

    decisions, _hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch()},
    )

    decision = decisions["A"]["vae"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.explicit_override is True
    assert decision.explicit_revealed is True


def test_bypass_authored_checkpoint_can_be_revealed_without_being_enabled() -> None:
    """Bypass-authored checkpoint cards should support disabled-but-revealed state."""

    ctx = EditorBehaviorContext(
        stack_order=("A", "B"),
        cubes={
            "A": cube(
                {
                    "ckpt": {
                        "class_type": "CheckpointLoaderSimple",
                        "inputs": {},
                    }
                }
            ),
            "B": cube(
                {
                    "ckpt": {
                        "class_type": "CheckpointLoaderSimple",
                        "inputs": {},
                        "mode": 4,
                        "revealed": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            alias: {
                "ckpt": ResolvedNodeBehavior(
                    node_name="ckpt",
                    class_type="CheckpointLoaderSimple",
                    card=CardBehavior(reveal_mode=RevealMode.MENU),
                    fields={},
                )
            }
            for alias in ("A", "B")
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
    )

    decisions, _hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch(), "B": PackageBehaviorPatch()},
    )

    decision = decisions["B"]["ckpt"]
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reveal_checked is True
    assert decision.explicit_revealed is True
