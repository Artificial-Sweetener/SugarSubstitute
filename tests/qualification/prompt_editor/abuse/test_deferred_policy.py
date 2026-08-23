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

"""Test prompt-editor abuse deferred-work structural-policy contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.models import (
    PromptAbuseActionOwnerDelta,
)
from tools.prompt_editor_abuse.structural_policy import (
    prompt_abuse_structural_violations,
)


def test_structural_policy_bounds_queued_core_and_workflow_round_trip_work() -> None:
    """One event turn and one workflow round trip must stay coalesced."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="event_turn:0",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="workflow_round_trip",
            counter_deltas=(
                ("instrumented_document_view_build_count", 2.0),
                ("instrumented_editing_replace_full_source_count", 1.0),
                ("instrumented_layout_snapshot_count", 6.0),
                ("instrumented_projection_document_build_count", 4.0),
                ("instrumented_projection_rebuild_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 2.0),
            ),
        ),
    )
    rejected = tuple(
        PromptAbuseActionOwnerDelta(
            action_index=delta.action_index,
            unit_index=delta.unit_index,
            label=delta.label,
            counter_deltas=tuple(
                (counter_name, value + 1.0)
                for counter_name, value in delta.counter_deltas
            ),
        )
        for delta in accepted
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert len(violations) == 12


def test_structural_policy_models_queued_autocomplete_and_reorder_projections() -> None:
    """Queued transient owners may add bounded projection and layout documents."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="drain_events:0",
            counter_deltas=(
                ("instrumented_autocomplete_preview_update_count", 1.0),
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 2.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="event_turn:0",
            counter_deltas=(
                ("instrumented_document_view_build_count", 2.0),
                ("instrumented_layout_snapshot_count", 4.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_reorder_preview_run_count", 1.0),
                ("instrumented_syntax_render_plan_build_count", 2.0),
                ("preview_scheduler_run_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=2,
            unit_index=0,
            label="key:'down'",
            counter_deltas=(
                ("instrumented_autocomplete_preview_update_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_attributes_deferred_projection_flush_to_prior_edit() -> None:
    """Passive movement may flush one explicitly identified pending edit update."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_pending_flush_applied_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
            ),
        ),
    )
    unowned_rebuild = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert len(prompt_abuse_structural_violations(unowned_rebuild)) == 3


def test_structural_policy_attributes_passive_diagnostic_cache_clear_to_publish() -> (
    None
):
    """Caret movement may invalidate one materially changed diagnostic view."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="select",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_diagnostics_visible_publish_count", 1.0),
                ("instrumented_diagnostics_visible_refresh_count", 2.0),
            ),
        ),
    )
    unowned_clear = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="select",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_diagnostics_visible_refresh_count", 1.0),
            ),
        ),
    )
    repeated_publish = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 2.0),
                ("instrumented_diagnostics_visible_publish_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert len(prompt_abuse_structural_violations(unowned_clear)) == 1
    assert len(prompt_abuse_structural_violations(repeated_publish)) == 2


def test_structural_policy_keeps_resize_source_neutral_and_single_pass() -> None:
    """A delivered resize may lay out once without rebuilding prompt semantics."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="resize",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_surface_resize_event_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="resize",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 2.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_surface_resize_event_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert len(violations) == 4
