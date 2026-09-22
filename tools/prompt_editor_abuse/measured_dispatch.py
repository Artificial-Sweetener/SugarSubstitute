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

"""Measure multi-unit text input and event-drain abuse actions."""

from __future__ import annotations

from time import perf_counter, thread_time
from collections.abc import Callable
from typing import Any, cast

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from .action_counter_probe import PromptAbuseActionCounterProbe
from .action_host import PromptAbuseActionHost
from .models import (
    PromptAbuseAction,
    PromptAbuseActionOwnerDelta,
    PromptAbuseDispatchSample,
)
from .owner_state import (
    capture_prompt_cursor_positions,
    capture_prompt_editor_owner_state,
)
from .runtime_probe import PromptAbuseRuntimeProbe, PromptAbuseRuntimeSample


def dispatch_typed_text(
    host: PromptAbuseActionHost,
    editor: object,
    target: QWidget,
    action: PromptAbuseAction,
    *,
    action_index: int,
    runtime_telemetry: bool,
    counter_probe: PromptAbuseActionCounterProbe,
    counter_deltas: list[PromptAbuseActionOwnerDelta],
    complete_action: Callable[[str | None], None] | None,
) -> tuple[PromptAbuseDispatchSample, ...]:
    """Dispatch and time every character while checking exact source order."""

    prompt_editor = cast(Any, editor)
    cursor = prompt_editor.textCursor()
    expected_source = prompt_editor.toPlainText()
    expected_start = cursor.selectionStart()
    expected_end = cursor.selectionEnd()
    samples: list[PromptAbuseDispatchSample] = []
    with PromptAbuseRuntimeProbe(enabled=runtime_telemetry) as runtime_probe:
        for unit_index, character in enumerate(action.value):
            is_final_unit = unit_index == len(action.value) - 1
            expected_source = (
                expected_source[:expected_start]
                + character
                + expected_source[expected_end:]
            )
            expected_start += len(character)
            expected_end = expected_start
            label = f"type:{character!r}"
            counter_probe.begin_unit()
            runtime_probe.begin_sample()
            started_at = perf_counter()
            thread_cpu_started_at = thread_time()
            QTest.keyClicks(target, character)
            dispatch_thread_cpu_ms = (thread_time() - thread_cpu_started_at) * 1_000.0
            dispatch_ms = (perf_counter() - started_at) * 1_000.0
            runtime_sample = runtime_probe.finish_sample()
            actual_source = str(prompt_editor.toPlainText())
            actual_cursor_position, actual_anchor_position = (
                capture_prompt_cursor_positions(editor)
            )
            checkpoint_source = (
                action.expected_source
                if is_final_unit and action.expected_source is not None
                else expected_source
            )
            checkpoint_cursor = (
                action.expected_cursor_position
                if is_final_unit and action.expected_cursor_position is not None
                else expected_start
            )
            checkpoint_anchor = (
                action.expected_anchor_position
                if is_final_unit and action.expected_anchor_position is not None
                else expected_start
            )
            if complete_action is not None:
                complete_action(checkpoint_source)
            source_exact = actual_source == checkpoint_source
            caret_exact = actual_cursor_position == checkpoint_cursor
            feature_exact, feature_mismatch = (
                host.capture_feature_checkpoint(editor, action)
                if is_final_unit
                else (True, None)
            )
            owner_state = capture_prompt_editor_owner_state(
                editor,
                validate_layout_fragments=False,
            )
            samples.append(
                PromptAbuseDispatchSample(
                    action_index=action_index,
                    unit_index=unit_index,
                    label=label,
                    dispatch_ms=dispatch_ms,
                    source_exact=source_exact,
                    caret_exact=caret_exact,
                    selection_exact=actual_anchor_position == checkpoint_anchor,
                    feature_exact=feature_exact,
                    latency_class="text_input",
                    actual_source_on_mismatch=None if source_exact else actual_source,
                    actual_cursor_position=actual_cursor_position,
                    expected_cursor_position=checkpoint_cursor,
                    actual_anchor_position=actual_anchor_position,
                    expected_anchor_position=checkpoint_anchor,
                    feature_mismatch=feature_mismatch,
                    projection_current_after_dispatch=owner_state.projection_current,
                    semantic_current_after_dispatch=owner_state.semantic_current,
                    visible_source_current_after_dispatch=(
                        owner_state.visible_source_current
                    ),
                    visible_caret_current_after_dispatch=(
                        owner_state.visible_caret_current
                    ),
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
                    caret_transform_depth_valid=(
                        owner_state.caret_transform_depth_valid
                    ),
                    transient_overlay_kind=owner_state.transient_overlay_kind,
                    projection_freshness=owner_state.projection_freshness,
                    allocated_block_delta=runtime_sample.allocated_block_delta,
                    gc_collection_count=runtime_sample.gc_collection_count,
                    gc_collected_objects=runtime_sample.gc_collected_objects,
                    gc_pause_ms=runtime_sample.gc_pause_ms,
                    dispatch_thread_cpu_ms=dispatch_thread_cpu_ms,
                )
            )
            counter_deltas.append(
                counter_probe.finish_unit(
                    action_index=action_index,
                    unit_index=unit_index,
                    label=label,
                )
            )
    if action.expected_source is not None and expected_source != action.expected_source:
        owner_state = capture_prompt_editor_owner_state(
            editor,
            validate_layout_fragments=False,
        )
        samples.append(
            PromptAbuseDispatchSample(
                action_index=action_index,
                unit_index=len(action.value),
                label="type:expected-checkpoint",
                dispatch_ms=0.0,
                source_exact=prompt_editor.toPlainText() == action.expected_source,
                caret_exact=host.source_actions.caret_matches(
                    editor, action.expected_cursor_position
                ),
                selection_exact=host.source_actions.anchor_matches(
                    editor,
                    action.expected_anchor_position,
                ),
                latency_class="text_input",
                actual_source_on_mismatch=str(prompt_editor.toPlainText()),
                actual_cursor_position=capture_prompt_cursor_positions(editor)[0],
                expected_cursor_position=action.expected_cursor_position,
                actual_anchor_position=capture_prompt_cursor_positions(editor)[1],
                expected_anchor_position=action.expected_anchor_position,
                projection_current_after_dispatch=owner_state.projection_current,
                semantic_current_after_dispatch=owner_state.semantic_current,
                visible_source_current_after_dispatch=(
                    owner_state.visible_source_current
                ),
                visible_caret_current_after_dispatch=(
                    owner_state.visible_caret_current
                ),
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
                dispatch_thread_cpu_ms=0.0,
            )
        )
    return tuple(samples)


def dispatch_event_drain(
    host: PromptAbuseActionHost,
    editor: object,
    action: PromptAbuseAction,
    *,
    action_index: int,
    runtime_telemetry: bool,
    counter_probe: PromptAbuseActionCounterProbe,
    counter_deltas: list[PromptAbuseActionOwnerDelta],
    complete_action: Callable[[str | None], None] | None,
) -> tuple[PromptAbuseDispatchSample, ...]:
    """Time each event-loop turn without instrumenting between drain cycles."""

    measured_cycles: list[tuple[float, float, PromptAbuseRuntimeSample]] = []
    cycle_count = 1 if action.kind == "event_turn" else 10
    with PromptAbuseRuntimeProbe(enabled=runtime_telemetry) as runtime_probe:
        for cycle in range(cycle_count):
            label = f"{action.kind}:{cycle}"
            counter_probe.begin_unit()
            runtime_probe.begin_sample()
            started_at = perf_counter()
            thread_cpu_started_at = thread_time()
            host.event_loop.process_events(cycles=1)
            dispatch_thread_cpu_ms = (thread_time() - thread_cpu_started_at) * 1_000.0
            dispatch_ms = (perf_counter() - started_at) * 1_000.0
            measured_cycles.append(
                (dispatch_ms, dispatch_thread_cpu_ms, runtime_probe.finish_sample())
            )
            if complete_action is not None:
                complete_action(action.expected_source)
            counter_deltas.append(
                counter_probe.finish_unit(
                    action_index=action_index,
                    unit_index=cycle,
                    label=label,
                )
            )
    source_exact = host.source_actions.source_matches(editor, action.expected_source)
    caret_exact = host.source_actions.caret_matches(
        editor, action.expected_cursor_position
    )
    prompt_editor = cast(Any, editor)
    owner_state = capture_prompt_editor_owner_state(
        editor,
        validate_layout_fragments=False,
    )
    actual_source = str(prompt_editor.toPlainText())
    actual_cursor_position, actual_anchor_position = capture_prompt_cursor_positions(
        editor
    )
    selection_exact = host.source_actions.anchor_matches(
        editor, action.expected_anchor_position
    )
    feature_exact, feature_mismatch = host.capture_feature_checkpoint(editor, action)
    return tuple(
        PromptAbuseDispatchSample(
            action_index=action_index,
            unit_index=cycle,
            label=f"{action.kind}:{cycle}",
            dispatch_ms=dispatch_ms,
            source_exact=source_exact,
            caret_exact=caret_exact,
            selection_exact=selection_exact,
            feature_exact=feature_exact,
            latency_class="backlog_drain",
            actual_source_on_mismatch=None if source_exact else actual_source,
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
            allocated_block_delta=runtime_sample.allocated_block_delta,
            gc_collection_count=runtime_sample.gc_collection_count,
            gc_collected_objects=runtime_sample.gc_collected_objects,
            gc_pause_ms=runtime_sample.gc_pause_ms,
            dispatch_thread_cpu_ms=dispatch_thread_cpu_ms,
        )
        for cycle, (
            dispatch_ms,
            dispatch_thread_cpu_ms,
            runtime_sample,
        ) in enumerate(measured_cycles)
    )


__all__ = ["dispatch_event_drain", "dispatch_typed_text"]
