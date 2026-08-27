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

"""Test prompt-editor abuse interaction structural-policy contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.models import (
    PromptAbuseActionOwnerDelta,
)
from tools.prompt_editor_abuse.structural_policy import (
    prompt_abuse_structural_violations,
)


def test_structural_policy_accepts_bounded_pointer_and_coalesced_preview_work() -> None:
    """Owner budgets should accept geometry-only moves and one queued preview unit."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=4,
            unit_index=0,
            label="reorder_drag_move:0.500000",
            counter_deltas=(
                ("autoscroll_pointer_update_count", 1.0),
                ("drag_move_count", 1.0),
                ("drop_target_changed_count", 1.0),
                ("instrumented_reorder_preview_request_count", 1.0),
                ("max_drag_move_ms", 2.5),
                ("preview_scheduler_request_count", 1.0),
                ("target_change_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=5,
            unit_index=0,
            label="event_turn:",
            counter_deltas=(
                ("animation_plan_applied_count", 1.0),
                ("animation_plan_build_count", 1.0),
                ("preview_geometry_full_count", 1.0),
                ("preview_projection_incremental_layout_count", 2.0),
                ("preview_scheduler_run_count", 1.0),
                ("projection_snapshot_rebuild_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_rejects_duplicate_reorder_activation_geometry() -> None:
    """Alt activation must prepare one coherent preview geometry publication."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="key_press:'alt'",
            counter_deltas=(("preview_geometry_full_count", 2.0),),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == 1
    assert "preview_geometry_full_count" in violations[0]
    assert "expected=<=1" in violations[0]
    assert "actual=2" in violations[0]


def test_structural_policy_rejects_heavy_pointer_work_and_unbounded_queueing() -> None:
    """Direct pointer work and queued publication should fail with exact diagnostics."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=4,
            unit_index=0,
            label="reorder_drag_move:1.000000",
            counter_deltas=(
                ("drag_move_count", 1.0),
                ("drop_target_changed_count", 1.0),
                ("instrumented_reorder_preview_request_count", 2.0),
                ("preview_scheduler_request_count", 2.0),
                ("projection_snapshot_rebuild_count", 1.0),
                ("target_change_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=5,
            unit_index=0,
            label="event_turn:",
            counter_deltas=(
                ("preview_scheduler_run_count", 2.0),
                ("projection_snapshot_rebuild_count", 3.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert any("preview_scheduler_request_count" in item for item in violations)
    assert any("projection_snapshot_rebuild_count" in item for item in violations)
    assert any("preview_scheduler_run_count" in item for item in violations)
    assert all(item.startswith("structural_budget:") for item in violations)


def test_structural_policy_rejects_editor_rebuild_work_on_canvas_round_trip() -> None:
    """Canvas switching must not rebuild or prepare hidden prompt-editor state."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=2,
            unit_index=0,
            label="canvas_round_trip:",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == 3
    assert any("instrumented_layout_snapshot_count" in item for item in violations)
    assert any("instrumented_projection_rebuild_count" in item for item in violations)
    assert any("region_chrome_prepare_count" in item for item in violations)
