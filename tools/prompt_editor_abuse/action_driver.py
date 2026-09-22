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

"""Dispatch and measure one prepared prompt-editor abuse action."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter, thread_time
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from .action_counter_probe import PromptAbuseActionCounterProbe
from .action_host import PromptAbuseActionHost
from .measured_dispatch import dispatch_event_drain, dispatch_typed_text
from .models import (
    PromptAbuseAction,
    PromptAbuseActionOwnerDelta,
    PromptAbuseDispatchSample,
    PromptAbuseLatencyClass,
)
from .owner_state import (
    capture_prompt_cursor_positions,
    capture_prompt_editor_owner_state,
)
from .runtime_probe import PromptAbuseRuntimeProbe

type PromptAbuseActionCompletion = Callable[[str | None], None]


def dispatch_action(
    host: PromptAbuseActionHost,
    editor: object,
    target: QWidget,
    action: PromptAbuseAction,
    *,
    action_index: int,
    runtime_telemetry: bool = False,
    counter_probe: PromptAbuseActionCounterProbe | None = None,
    counter_deltas: list[PromptAbuseActionOwnerDelta] | None = None,
    complete_action: PromptAbuseActionCompletion | None = None,
) -> tuple[PromptAbuseDispatchSample, ...]:
    """Dispatch one action and return low-overhead timing evidence."""

    counter_probe = counter_probe or PromptAbuseActionCounterProbe(editor)
    if counter_deltas is None:
        counter_deltas = []

    if action.kind == "type":
        return dispatch_typed_text(
            host,
            editor,
            target,
            action,
            action_index=action_index,
            runtime_telemetry=runtime_telemetry,
            counter_probe=counter_probe,
            counter_deltas=counter_deltas,
            complete_action=complete_action,
        )
    if action.kind in {"event_turn", "drain_events"}:
        return dispatch_event_drain(
            host,
            editor,
            action,
            action_index=action_index,
            runtime_telemetry=runtime_telemetry,
            counter_probe=counter_probe,
            counter_deltas=counter_deltas,
            complete_action=complete_action,
        )
    action_label = _action_label(action)
    counter_probe.begin_unit()
    with PromptAbuseRuntimeProbe(enabled=runtime_telemetry) as runtime_probe:
        runtime_probe.begin_sample()
        started_at = perf_counter()
        thread_cpu_started_at = thread_time()
        lifecycle_steps = _dispatch_single_action(host, editor, target, action)
        dispatch_thread_cpu_ms = (thread_time() - thread_cpu_started_at) * 1_000.0
        dispatch_ms = (perf_counter() - started_at) * 1_000.0
        runtime_sample = runtime_probe.finish_sample()
    if complete_action is not None:
        complete_action(action.expected_source)
    source_exact = host.source_actions.source_matches(editor, action.expected_source)
    caret_exact = host.source_actions.caret_matches(
        editor, action.expected_cursor_position
    )
    selection_exact = host.source_actions.anchor_matches(
        editor, action.expected_anchor_position
    )
    feature_exact, feature_mismatch = host.capture_feature_checkpoint(editor, action)
    owner_state = capture_prompt_editor_owner_state(
        editor,
        validate_layout_fragments=False,
    )
    actual_cursor_position, actual_anchor_position = capture_prompt_cursor_positions(
        editor
    )
    measured_steps = lifecycle_steps or ((action_label, dispatch_ms),)
    samples = tuple(
        PromptAbuseDispatchSample(
            action_index=action_index,
            unit_index=unit_index,
            label=label,
            dispatch_ms=step_dispatch_ms,
            source_exact=source_exact,
            caret_exact=caret_exact,
            selection_exact=selection_exact,
            feature_exact=feature_exact,
            latency_class=_latency_class(action),
            actual_source_on_mismatch=(
                None if source_exact else str(cast(Any, editor).toPlainText())
            ),
            actual_cursor_position=actual_cursor_position,
            expected_cursor_position=action.expected_cursor_position,
            actual_anchor_position=actual_anchor_position,
            expected_anchor_position=action.expected_anchor_position,
            feature_mismatch=feature_mismatch,
            projection_current_after_dispatch=owner_state.projection_current,
            semantic_current_after_dispatch=owner_state.semantic_current,
            visible_source_current_after_dispatch=owner_state.visible_source_current,
            visible_caret_current_after_dispatch=owner_state.visible_caret_current,
            active_projection_ownership_valid=(
                owner_state.active_projection_ownership_valid
            ),
            layout_projection_ownership_valid=(
                owner_state.layout_projection_ownership_valid
            ),
            layout_fragment_ownership_valid=(
                owner_state.layout_fragment_ownership_valid
            ),
            layout_fragment_ownership_mismatch=(
                owner_state.layout_fragment_ownership_mismatch
            ),
            caret_transform_depth=owner_state.caret_transform_depth,
            caret_transform_depth_valid=owner_state.caret_transform_depth_valid,
            transient_overlay_kind=owner_state.transient_overlay_kind,
            projection_freshness=owner_state.projection_freshness,
            allocated_block_delta=(
                runtime_sample.allocated_block_delta
                if unit_index == len(measured_steps) - 1
                else 0
            ),
            gc_collection_count=(
                runtime_sample.gc_collection_count
                if unit_index == len(measured_steps) - 1
                else 0
            ),
            gc_collected_objects=(
                runtime_sample.gc_collected_objects
                if unit_index == len(measured_steps) - 1
                else 0
            ),
            gc_pause_ms=(
                runtime_sample.gc_pause_ms
                if unit_index == len(measured_steps) - 1
                else 0.0
            ),
            dispatch_thread_cpu_ms=(
                dispatch_thread_cpu_ms if len(measured_steps) == 1 else None
            ),
        )
        for unit_index, (label, step_dispatch_ms) in enumerate(measured_steps)
    )
    counter_deltas.append(
        counter_probe.finish_unit(
            action_index=action_index,
            unit_index=0,
            label=action_label,
        )
    )
    return samples


def _dispatch_single_action(
    host: PromptAbuseActionHost,
    editor: object,
    target: QWidget,
    action: PromptAbuseAction,
) -> tuple[tuple[str, float], ...]:
    """Route one single-unit action to its authoritative capability owner."""

    if action.kind == "paste":
        host.keyboard_actions.paste_text(target, action.value)
    elif action.kind == "key":
        host.keyboard_actions.dispatch_key(target, action.value)
    elif action.kind == "key_press":
        host.keyboard_actions.press_key(target, action.value)
    elif action.kind == "key_release":
        host.keyboard_actions.release_key(target, action.value)
    elif action.kind == "key_chord":
        host.keyboard_actions.press_chord(target, action.value)
    elif action.kind == "select":
        host.source_actions.select_range(editor, action)
    elif action.kind == "move_cursor":
        host.source_actions.move_cursor(editor, action)
    elif action.kind == "resize":
        assert action.viewport_size is not None
        host.resize_editor(editor, *action.viewport_size)
    elif action.kind == "scroll":
        host.scroll_editor(editor, action.value)
    elif action.kind == "focus_cycle":
        host.focus_cycle(target)
    elif action.kind == "workflow_round_trip":
        return host.workflow_round_trip()
    elif action.kind == "canvas_round_trip":
        return host.canvas_round_trip()
    elif action.kind == "reorder_drag_press":
        host.reorder_drag_press(editor, action.value)
    elif action.kind == "reorder_drag_threshold":
        host.reorder_drag_threshold(editor)
    elif action.kind == "reorder_drag_move":
        host.reorder_drag_move(editor, action.value)
    elif action.kind == "reorder_drag_sweep":
        host.reorder_drag_sweep(editor)
    elif action.kind == "reorder_drag_release":
        host.reorder_drag_release(editor)
    elif action.kind == "reorder_drag_autoscroll":
        host.reorder_drag_autoscroll(editor)
    elif action.kind == "reorder_drag_cancel":
        host.reorder_drag_cancel(editor, target)
    elif action.kind == "request_paint":
        cast(Any, editor).viewport().update()
    elif action.kind == "display_mode":
        host.set_display_mode(editor, action.value)
    elif action.kind == "search_highlights":
        host.set_search_highlights(editor, action)
    elif action.kind == "mouse_caret":
        assert action.position is not None
        host.source_actions.mouse_caret(editor, action.position)
    elif action.kind == "mouse_drag_selection":
        assert action.position is not None
        assert action.selection_end is not None
        host.source_actions.mouse_drag_selection(
            editor, action.position, action.selection_end
        )
    elif action.kind == "wheel_weight":
        host.weight_actions.wheel(editor, action.value)
    elif action.kind == "step_weight":
        host.weight_actions.step(editor, action.value)
    elif action.kind == "edit_weight_exact":
        host.weight_actions.edit_exact(editor, action.value)
    elif action.kind == "refresh_diagnostics":
        host.feature_actions.refresh_diagnostics(editor)
    elif action.kind == "lora_picker_open":
        host.feature_actions.open_lora_picker(editor)
    elif action.kind == "lora_picker_activate":
        host.feature_actions.activate_first_lora_picker_item(editor)
    elif action.kind == "context_menu":
        assert action.position is not None
        host.feature_actions.open_context_menu(editor, action.position)
    elif action.kind == "context_menu_trigger":
        assert action.position is not None
        host.feature_actions.trigger_context_menu_action(
            editor, action.position, action.value
        )
    elif action.kind == "context_menu_trigger_cached":
        host.feature_actions.trigger_cached_context_menu_action(action.value)
    else:
        raise ValueError(f"Unsupported prompt abuse action kind {action.kind!r}.")
    return ()


def _action_label(action: PromptAbuseAction) -> str:
    """Return one concise sample label for a dispatched action."""

    if action.kind in {
        "key",
        "key_press",
        "key_release",
        "key_chord",
        "paste",
        "reorder_drag_press",
        "reorder_drag_threshold",
        "reorder_drag_move",
    }:
        return f"{action.kind}:{action.value[:32]!r}"
    return action.kind


def _latency_class(action: PromptAbuseAction) -> PromptAbuseLatencyClass:
    """Classify one dispatch so setup work cannot pollute text-input budgets."""

    if action.kind in {"type", "paste", "key"}:
        return "text_input"
    if action.kind in {"workflow_round_trip", "canvas_round_trip"}:
        return "lifecycle"
    if action.kind in {"request_paint", "display_mode", "search_highlights"}:
        return "lifecycle"
    if action.kind in {"event_turn", "drain_events"}:
        return "backlog_drain"
    return "interaction"


__all__ = ["dispatch_action"]
