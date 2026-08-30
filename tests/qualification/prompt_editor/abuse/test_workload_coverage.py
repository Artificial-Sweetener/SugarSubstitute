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

"""Test prompt-editor abuse workload and operation-coverage contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.coverage import capture_operation_coverage
from tools.prompt_editor_abuse.workloads import KEY_SLAM, hostile_prompt_scenarios


def test_hostile_workloads_cover_typing_edits_lifecycle_and_layout_pressure() -> None:
    """The deterministic matrix should attack more than ordinary key insertion."""

    scenarios = hostile_prompt_scenarios()
    by_name = {scenario.name: scenario for scenario in scenarios}

    assert by_name["empty-key-slam"].actions[0].value == KEY_SLAM
    assert by_name["long-decorated-start"].cursor_position == 0
    middle = by_name["long-decorated-middle"]
    assert middle.cursor_position == len(middle.initial_text) // 2
    end = by_name["long-decorated-end"]
    assert end.cursor_position == len(end.initial_text)
    assert len(end.initial_text) >= 8_000
    assert {
        "mixed-destructive-editing",
        "paste-undo-redo",
        "scene-marker-creation",
        "selection-replace-delete",
        "resize-wrap-churn",
        "autocomplete-race-churn",
        "seeded-mixed-abuse",
        "lifecycle-scroll-switch-churn",
        "region-separator-horizontal-atomic-navigation",
        "region-separator-vertical-navigation",
        "region-separator-mouse-placement",
        "region-separator-raw-rich-boundary",
        "region-separator-topology-promotion",
        "region-separator-adjacent-authoring",
        "region-separator-adjacent-partition-population",
        "region-separator-continued-authoring",
        "region-separator-nearby-authoring",
        "region-separator-delete-join-split",
        "region-separator-paste-selection-resize",
        "region-separator-multi-line-break",
        "region-separator-seeded-churn",
        "region-separator-canvas-lifecycle",
        "regional-separator-cross-partition-drag",
        "regional-separator-repeated-cross-partition-drag",
        "regional-separator-all-target-sweep",
        "regional-separator-all-source-sweep",
        "regional-separator-mixed-boundary-sweep",
        "regional-separator-leading-partition-exit",
        "regional-separator-trailing-partition-exit",
        "regional-separator-multi-partition-drag",
        "wildcard-txt-zebra-typing",
        "wildcard-scene-marker-error",
        "wildcard-csv-quoted-typing",
        "wildcard-mouse-drag-zebra",
        "prompt-viewport-repaint",
        "wildcard-viewport-repaint",
        "prompt-long-decorated-repaint",
    }.issubset(by_name)
    action_kinds = {
        action.kind for scenario in scenarios for action in scenario.actions
    }
    assert {
        "type",
        "paste",
        "key",
        "select",
        "resize",
        "scroll",
        "focus_cycle",
        "workflow_round_trip",
        "canvas_round_trip",
        "reorder_drag_press",
        "reorder_drag_threshold",
        "reorder_drag_move",
        "reorder_drag_release",
        "request_paint",
        "event_turn",
        "drain_events",
        "step_weight",
        "edit_weight_exact",
    } <= action_kinds
    assert by_name["wildcard-txt-zebra-typing"].editor_kind == "wildcard_txt"
    assert by_name["wildcard-csv-quoted-typing"].editor_kind == "wildcard_csv"
    assert by_name["cache-restored-lora-pointer-step"].mount_source == "workspace_cache"
    assert (
        by_name["v0-19-2-cache-restored-lora-exact-edit-pointer"].mount_source
        == "workspace_cache_0_19_2"
    )
    assert (
        by_name["image-sugar-script-restored-emphasis-exact-edit-pointer"].mount_source
        == "image_sugar_script"
    )
    seeded = by_name["seeded-mixed-abuse"]
    assert seeded.seed == 7
    assert len(seeded.actions) >= 48
    assert {"type", "paste", "select", "resize", "drain_events"} <= {
        action.kind for action in seeded.actions
    }
    separator_seeded = by_name["region-separator-seeded-churn"]
    assert separator_seeded.seed == 7
    assert len(separator_seeded.actions) >= 32
    assert {
        "key",
        "mouse_caret",
        "mouse_drag_selection",
        "display_mode",
        "resize",
        "request_paint",
        "drain_events",
    } <= {action.kind for action in separator_seeded.actions}
    search = by_name["search-highlight-scroll-paint"]
    search_ranges = next(
        action.source_ranges
        for action in search.actions
        if action.kind == "search_highlights" and action.value == "set"
    )
    assert len(search_ranges) >= 36
    assert {length for _start, length in search_ranges} == {len("masterpiece")}


def test_operation_coverage_requires_every_editor_feature() -> None:
    """The hostile matrix must retain complete prompt-editor operation coverage."""

    coverage = capture_operation_coverage(hostile_prompt_scenarios())

    assert "text.type" in coverage.covered
    assert "reorder.pointer_move" in coverage.covered
    assert "autocomplete.accept" in coverage.covered
    assert "diagnostic.context_menu" in coverage.covered
    assert "diagnostic.action" in coverage.covered
    assert "emphasis.pointer_step" in coverage.covered
    assert "emphasis.exact_edit" in coverage.covered
    assert "lora.pointer_step" in coverage.covered
    assert "lora.exact_edit" in coverage.covered
    assert "reorder.pointer_cancel" in coverage.covered
    assert coverage.missing == ()
