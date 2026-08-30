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

"""Test prompt-editor abuse editing structural-policy contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.models import (
    PromptAbuseActionOwnerDelta,
)
from tools.prompt_editor_abuse.structural_policy import (
    prompt_abuse_structural_violations,
)


def test_structural_policy_rejects_semantic_work_on_passive_editor_actions() -> None:
    """Navigation, selection, paint, and scroll must remain source-neutral."""

    deltas = tuple(
        PromptAbuseActionOwnerDelta(
            action_index=index,
            unit_index=0,
            label=label,
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        )
        for index, label in enumerate(
            (
                "key:'up'",
                "mouse_caret",
                "mouse_drag_selection",
                "move_cursor",
                "request_paint",
                "scroll",
                "select",
            )
        )
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == len(deltas) * 3
    assert all("expected=0" in violation for violation in violations)


def test_structural_policy_accepts_one_bounded_incremental_user_edit() -> None:
    """One character edit may use one source and one projection strategy."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:'x'",
            counter_deltas=(
                ("instrumented_editing_replace_range_count", 1.0),
                ("instrumented_projection_incremental_applied_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="key:'enter'",
            counter_deltas=(
                ("instrumented_editing_replace_range_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_distinguishes_canonical_and_active_edit_projections() -> (
    None
):
    """One canonical edit may publish one additional active-edit projection."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:')'",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:')'",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 3.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert any(
        "instrumented_projection_document_build_count" in violation
        for violation in prompt_abuse_structural_violations(rejected)
    )


def test_structural_policy_models_one_immediate_danbooru_import_completion() -> None:
    """Literal URL paste and its immediate import may commit two revisions."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'https://danbooru.donmai.us/posts/1'",
            counter_deltas=(
                ("instrumented_danbooru_import_apply_count", 1.0),
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_editing_replace_range_count", 2.0),
                ("instrumented_editing_paste_count", 1.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_surface_source_apply_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'https://danbooru.donmai.us/posts/1'",
            counter_deltas=(
                ("instrumented_danbooru_import_apply_count", 2.0),
                ("instrumented_editing_replace_range_count", 3.0),
                ("instrumented_surface_source_apply_count", 3.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert any(
        "instrumented_danbooru_import_apply_count" in item for item in violations
    )
    assert any(
        "instrumented_editing_replace_range_count" in item for item in violations
    )
    assert any("instrumented_surface_source_apply_count" in item for item in violations)


def test_structural_policy_rejects_duplicate_edit_and_projection_work() -> None:
    """One input unit must not trigger multiple source or applied-path units."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'x'",
            counter_deltas=(
                ("instrumented_editing_paste_count", 2.0),
                ("instrumented_editing_replace_full_source_count", 1.0),
                ("instrumented_editing_replace_range_count", 2.0),
                ("instrumented_projection_fast_insert_applied_count", 1.0),
                ("instrumented_projection_incremental_applied_count", 1.0),
                ("instrumented_surface_source_apply_count", 2.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert any("instrumented_editing_paste_count" in item for item in violations)
    assert any(
        "instrumented_editing_replace_full_source_count" in item for item in violations
    )
    assert any(
        "instrumented_editing_replace_range_count" in item for item in violations
    )
    assert any("instrumented_surface_source_apply_count" in item for item in violations)
    assert any("projection_applied_path_count" in item for item in violations)
