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

"""Verify visibility, switch, and search decisions."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    ActivationDefault,
    CardBehavior,
    EnabledSwitchPolicy,
    EditorBehaviorContext,
    PackageBehaviorPatch,
    ResolvedNodeBehavior,
    RevealMode,
    compute_editor_behavior,
)
from tests.domain.node_behavior.engine.support import cube


def test_never_policy_visible_node_hides_enabled_switch() -> None:
    """Visible primary worker nodes should stay active without a title switch."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "sampler": {
                        "class_type": "CustomSamplerWorker",
                        "inputs": {"steps": 20, "denoise": 1.0},
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "sampler": ResolvedNodeBehavior(
                    node_name="sampler",
                    class_type="CustomSamplerWorker",
                    card=CardBehavior(
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                    ),
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

    decision = decisions["A"]["sampler"]
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.show_enabled_switch is False


def test_never_policy_suppresses_generic_revealable_switch() -> None:
    """The NEVER policy should override generic reveal-menu switch exposure."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "worker": {
                        "class_type": "CustomSamplerWorker",
                        "inputs": {"steps": 20, "denoise": 1.0},
                        "revealed": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "worker": ResolvedNodeBehavior(
                    node_name="worker",
                    class_type="CustomSamplerWorker",
                    card=CardBehavior(
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                        reveal_mode=RevealMode.MENU,
                        hidden=True,
                    ),
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

    decision = decisions["A"]["worker"]
    assert decision.visible is True
    assert decision.revealable is True
    assert decision.show_enabled_switch is False


def test_hard_hidden_card_can_remain_active_without_materializing() -> None:
    """Opt-in infrastructure cards should stay active while remaining invisible."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "schedule": {
                        "class_type": (
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        "inputs": {},
                        "revealed": True,
                        "enabled": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "schedule": ResolvedNodeBehavior(
                    node_name="schedule",
                    class_type="SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl",
                    card=CardBehavior(
                        activation_default=ActivationDefault.ENABLED,
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                        hidden=True,
                    ),
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

    decision = decisions["A"]["schedule"]
    assert decision.visible is False
    assert decision.enabled is True
    assert decision.revealable is False
    assert decision.show_enabled_switch is False
    assert decision.reason == "policy:override-hide"


def test_hard_hidden_card_defaults_inactive_without_activation_opt_in() -> None:
    """Hard-hidden cards should keep their existing inactive default."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "worker": {
                        "class_type": "CustomWorker",
                        "inputs": {},
                        "revealed": True,
                        "enabled": True,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "worker": ResolvedNodeBehavior(
                    node_name="worker",
                    class_type="CustomWorker",
                    card=CardBehavior(
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                        hidden=True,
                    ),
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

    decision = decisions["A"]["worker"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.revealable is False
    assert decision.show_enabled_switch is False
    assert decision.reason == "policy:override-hide"


def test_never_policy_suppresses_authored_bypass_switch() -> None:
    """Bypass-authored nodes should still honor a NEVER switch policy."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "worker": {
                        "class_type": "CustomSamplerWorker",
                        "inputs": {"steps": 20, "denoise": 1.0},
                        "mode": 4,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "worker": ResolvedNodeBehavior(
                    node_name="worker",
                    class_type="CustomSamplerWorker",
                    card=CardBehavior(
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                    ),
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

    decision = decisions["A"]["worker"]
    assert decision.visible is False
    assert decision.enabled is False
    assert decision.revealable is True
    assert decision.show_enabled_switch is False


def test_search_filter_does_not_disable_policy_visible_nodes() -> None:
    """Node search visibility should not change generation activation decisions."""

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
        node_search_text="missing",
    )

    decisions, _hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch()},
    )

    decision = decisions["A"]["vae"]
    assert decision.visible is False
    assert decision.enabled is True
    assert decision.reason == "search:node-filter"
