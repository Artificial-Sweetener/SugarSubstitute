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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
)
from substitute.domain.node_behavior import NodeDisplayDecision
from substitute.presentation.shell.workspace_generation_request_builder import (
    activation_node_keys_by_alias,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_activation_node_keys_follow_authored_defaults() -> None:
    """Generation activation lists should be deltas from authored defaults."""

    workflow = SimpleNamespace(
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "revealed_enabled_bypass": {"mode": 4},
                        "revealed_disabled_bypass": {"mode": 4},
                        "normal_disabled": {},
                    }
                }
            )
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "revealed_enabled_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "revealed_disabled_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:revealed",
                ),
                "normal_disabled": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

    enabled, disabled = activation_node_keys_by_alias(behavior_snapshot, workflow)

    assert enabled == {"A": ("revealed_enabled_bypass",)}
    assert disabled == {"A": ("normal_disabled",)}


def test_activation_node_keys_keep_hidden_active_schedule_node_enabled() -> None:
    """Hidden active infrastructure nodes should not serialize disable overrides."""

    workflow = SimpleNamespace(
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "schedule_encode_prompts": {
                            "class_type": (
                                "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                            ),
                            "inputs": {},
                        },
                    }
                }
            )
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "schedule_encode_prompts": NodeDisplayDecision(
                    visible=False,
                    enabled=True,
                    reason="policy:override-hide",
                    revealable=False,
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

    enabled, disabled = activation_node_keys_by_alias(behavior_snapshot, workflow)

    assert enabled == {}
    assert disabled == {}
