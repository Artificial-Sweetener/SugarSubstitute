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

"""Dispatch hostile prompt-editor actions through real Qt input routes."""

from __future__ import annotations

from time import perf_counter, thread_time
from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QMouseEvent,
    QTextCursor,
    QWheelEvent,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)

from .action_checkpoint import capture_action_checkpoint
from .action_counter_probe import PromptAbuseActionCounterProbe
from .models import (
    PromptAbuseAction,
    PromptAbuseActionOwnerDelta,
    PromptAbuseDispatchSample,
)
from .models import PromptAbuseLatencyClass
from .owner_state import (
    capture_prompt_cursor_positions,
    capture_prompt_editor_owner_state,
)
from .runtime_probe import PromptAbuseRuntimeProbe, PromptAbuseRuntimeSample


class PromptAbuseActionHost:
    """Own generic Qt input dispatch outside any one editor container."""

    def paste_text(self, target: QWidget, text: str) -> None:
        """Paste clipboard text through the focused production input route."""

        QApplication.clipboard().setText(text)
        QTest.keyClick(target, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    def undo(self, target: QWidget) -> None:
        """Undo through the focused production input route."""

        QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    def redo(self, target: QWidget) -> None:
        """Redo through the focused production input route."""

        QTest.keyClick(target, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)

    def process_events(self, *, cycles: int = 4) -> None:
        """Drain a bounded number of Qt event-loop cycles."""

        for _cycle in range(cycles):
            QApplication.processEvents()

    def scroll_editor(self, editor: object, target: str) -> None:
        """Move the scrollbar; explicit event-turn actions measure publication."""

        scrollbar = cast(Any, editor).verticalScrollBar()
        if target == "top":
            value = scrollbar.minimum()
        elif target == "middle":
            value = (scrollbar.minimum() + scrollbar.maximum()) // 2
        elif target == "bottom":
            value = scrollbar.maximum()
        else:
            raise ValueError(f"Unsupported prompt abuse scroll target {target!r}.")
        scrollbar.setValue(value)

    def focus_cycle(self, target: QWidget) -> None:
        """Move focus away and back without creating another window."""

        target.clearFocus()
        self.process_events(cycles=2)
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        self.process_events(cycles=2)

    def workflow_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch workflows and return one timing for each visible transition."""

        raise RuntimeError("Workflow round trips require the real-shell action host.")

    def canvas_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch canvases and return one timing for each visible transition."""

        raise RuntimeError("Canvas round trips require the real-shell action host.")

    def reorder_drag_press(self, editor: object, value: str) -> None:
        """Press a reorder chip when the concrete host supports it."""

        del editor, value
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_threshold(self, editor: object) -> None:
        """Cross the platform drag threshold when the concrete host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_move(self, editor: object, value: str) -> None:
        """Move an active reorder chip drag when its host supports it."""

        del editor, value
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_release(self, editor: object) -> None:
        """Release an active reorder chip drag when its host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_autoscroll(self, editor: object) -> None:
        """Autoscroll an active reorder drag when its host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_cancel(self, editor: object, target: QWidget) -> None:
        """Cancel an active reorder drag when its host supports it."""

        del editor, target
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def set_display_mode(self, editor: object, mode: str) -> None:
        """Switch the production editor between projected and raw source modes."""

        cast(Any, editor).setRichPromptRenderingEnabled(mode == "rich")

    def set_search_highlights(self, editor: object, action: PromptAbuseAction) -> None:
        """Publish or clear search highlights through the production feature owner."""

        prompt_editor = cast(Any, editor)
        if action.value == "set":
            prompt_editor.set_search_matches(
                action.source_ranges,
                action.active_index,
                query_identity=(
                    "prompt-abuse",
                    action.source_ranges,
                    action.active_index,
                ),
            )
            return
        prompt_editor.clear_search_matches()

    def mouse_caret(self, editor: object, position: int) -> None:
        """Place the caret through a real viewport click at a source boundary."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        QTest.mouseClick(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=_viewport_point_for_source_position(prompt_editor, position),
            delay=0,
        )

    def mouse_drag_selection(self, editor: object, start: int, end: int) -> None:
        """Create a directional selection through a real viewport pointer drag."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        start_point = _viewport_point_for_source_position(prompt_editor, start)
        end_point = _viewport_point_for_source_position(prompt_editor, end)
        QTest.mousePress(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=start_point,
            delay=0,
        )
        QTest.mouseMove(viewport, end_point, delay=0)
        QTest.mouseRelease(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=end_point,
            delay=0,
        )

    def wheel_weight(self, editor: object, direction: str) -> None:
        """Wheel the first weighted token through viewport pointer hit testing."""

        prompt_editor = cast(Any, editor)
        surface = prompt_editor._surface
        token = next(
            (
                candidate
                for candidate in surface.projection_document().tokens
                if candidate.kind.value in {"emphasis", "lora"}
            ),
            None,
        )
        if token is None:
            raise RuntimeError("Prompt abuse wheel action requires a weighted token.")
        weight_rect = surface.token_weight_text_rect(token)
        if weight_rect is None:
            raise RuntimeError("Prompt abuse wheel token has no visible geometry.")
        viewport = cast(QWidget, prompt_editor.viewport())
        local_position = weight_rect.center().toPoint()
        global_position = viewport.mapToGlobal(local_position)
        activated_editors = cast(
            set[int],
            getattr(self, "_wheel_activated_editor_ids", set()),
        )
        if id(prompt_editor) not in activated_editors:
            QTest.mouseClick(
                viewport,
                Qt.MouseButton.LeftButton,
                pos=local_position,
                delay=0,
            )
            activated_editors.add(id(prompt_editor))
            self._wheel_activated_editor_ids = activated_editors
        angle_delta = 120 if direction == "up" else -120
        event = QWheelEvent(
            QPointF(local_position),
            QPointF(global_position),
            QPoint(),
            QPoint(0, angle_delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(viewport, event)
        if not event.isAccepted():
            raise RuntimeError("Prompt abuse weighted-token wheel was not accepted.")

    def refresh_diagnostics(self, editor: object) -> None:
        """Refresh diagnostics through the production feature controller."""

        cast(Any, editor)._diagnostics_feature_controller.refresh_now()

    def open_lora_picker(self, editor: object) -> None:
        """Open the production LoRA picker and require a visible populated popup."""

        presenter = cast(Any, editor)._lora_picker_popup_presenter
        presenter.open_lora_picker()
        popup = presenter._popup
        if popup is None or not popup.isVisible():
            raise RuntimeError("Prompt abuse LoRA picker did not become visible.")
        snapshot = presenter._data_source.lora_picker_snapshot
        if not snapshot.consumable or not snapshot.items:
            raise RuntimeError("Prompt abuse LoRA picker has no consumable rows.")

    def activate_first_lora_picker_item(self, editor: object) -> None:
        """Activate the first real picker row through its production signal."""

        presenter = cast(Any, editor)._lora_picker_popup_presenter
        popup = presenter._popup
        if popup is None or not popup.isVisible():
            raise RuntimeError("Prompt abuse LoRA picker activation requires a popup.")
        snapshot = presenter._data_source.lora_picker_snapshot
        if not snapshot.items:
            raise RuntimeError("Prompt abuse LoRA picker activation has no row.")
        popup.loraActivated.emit(snapshot.items[0])

    def open_context_menu(self, editor: object, position: int) -> None:
        """Right-click one source boundary and capture the real headless menu."""

        self._dispatch_context_menu(editor, position, trigger_label=None)

    def trigger_context_menu_action(
        self,
        editor: object,
        position: int,
        action_label: str,
    ) -> None:
        """Trigger one exact action from the production-built headless menu."""

        self._dispatch_context_menu(editor, position, trigger_label=action_label)

    def trigger_cached_context_menu_action(self, action_label: str) -> None:
        """Activate one exact row from the most recently captured menu."""

        actions = cast(tuple[QAction, ...], getattr(self, "_last_context_actions", ()))
        matching_action = next(
            (
                action
                for action in actions
                if action.text() == action_label
                or action.property("promptFullTriggerWordsLabel") == action_label
            ),
            None,
        )
        if matching_action is None:
            raise RuntimeError(
                f"Missing cached prompt abuse context-menu action {action_label!r}."
            )
        matching_action.trigger()

    def _dispatch_context_menu(
        self,
        editor: object,
        position: int,
        *,
        trigger_label: str | None,
    ) -> None:
        """Build one production menu and optionally activate an exact row."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        local_position = _viewport_point_for_source_position(prompt_editor, position)
        global_position = viewport.mapToGlobal(local_position)
        labels: list[str] = []
        triggered = False
        round_menu_class = cast(Any, RoundMenu)
        original_exec = round_menu_class.exec

        def capture_menu(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture menu rows without opening a native popup."""

            nonlocal triggered
            _populate_lazy_submenus(menu)
            labels.extend(_menu_action_labels(menu))
            self._last_context_actions = _menu_actions(menu)
            if trigger_label is None:
                return
            matching_action = next(
                (
                    action
                    for action in _menu_actions(menu)
                    if action.text() == trigger_label
                    or action.property("promptFullTriggerWordsLabel") == trigger_label
                ),
                None,
            )
            if matching_action is not None:
                matching_action.trigger()
                triggered = True

        round_menu_class.exec = capture_menu
        try:
            press_event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(local_position),
                QPointF(global_position),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(viewport, press_event)
            context_event = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                local_position,
                global_position,
            )
            QCoreApplication.sendEvent(viewport, context_event)
        finally:
            round_menu_class.exec = original_exec
        self._last_context_menu_labels = tuple(labels)
        if trigger_label is not None and not triggered:
            raise RuntimeError(
                f"Missing prompt abuse context-menu action {trigger_label!r}."
            )

    def capture_feature_checkpoint(
        self,
        editor: object,
        action: PromptAbuseAction,
    ) -> tuple[bool, str | None]:
        """Combine editor-owner and action-host checkpoints."""

        exact, mismatch = capture_action_checkpoint(editor, action)
        mismatches = [] if mismatch is None else [mismatch]
        if action.expected_context_labels is not None:
            actual_labels = getattr(self, "_last_context_menu_labels", ())
            missing_labels = tuple(
                label
                for label in action.expected_context_labels
                if label not in actual_labels
            )
            if missing_labels:
                mismatches.append(
                    f"context_menu:missing={missing_labels!r}:actual={actual_labels!r}"
                )
        return exact and not mismatches, ";".join(mismatches) or None


_QT_KEYS = {
    "backspace": Qt.Key.Key_Backspace,
    "delete": Qt.Key.Key_Delete,
    "enter": Qt.Key.Key_Return,
    "escape": Qt.Key.Key_Escape,
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
    "home": Qt.Key.Key_Home,
    "end": Qt.Key.Key_End,
    "tab": Qt.Key.Key_Tab,
    "alt": Qt.Key.Key_Alt,
}


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
) -> tuple[PromptAbuseDispatchSample, ...]:
    """Dispatch one action and return low-overhead timing evidence."""

    counter_probe = counter_probe or PromptAbuseActionCounterProbe(editor)
    if counter_deltas is None:
        counter_deltas = []

    if action.kind == "type":
        return _dispatch_typed_text(
            editor,
            target,
            action,
            action_index=action_index,
            runtime_telemetry=runtime_telemetry,
            counter_probe=counter_probe,
            counter_deltas=counter_deltas,
        )
    if action.kind in {"event_turn", "drain_events"}:
        return _dispatch_event_drain(
            host,
            editor,
            action,
            action_index=action_index,
            runtime_telemetry=runtime_telemetry,
            counter_probe=counter_probe,
            counter_deltas=counter_deltas,
        )
    action_label = _action_label(action)
    counter_probe.begin_unit()
    with PromptAbuseRuntimeProbe(enabled=runtime_telemetry) as runtime_probe:
        runtime_probe.begin_sample()
        started_at = perf_counter()
        thread_cpu_started_at = thread_time()
        lifecycle_steps: tuple[tuple[str, float], ...] = ()
        if action.kind == "paste":
            host.paste_text(target, action.value)
        elif action.kind == "key":
            _dispatch_key(host, target, action.value)
        elif action.kind == "key_press":
            QTest.keyPress(target, _named_key(action.value))
        elif action.kind == "key_release":
            QTest.keyRelease(target, _named_key(action.value))
        elif action.kind == "key_chord":
            _dispatch_key_chord(target, action.value)
        elif action.kind == "select":
            _select_source_range(editor, action)
        elif action.kind == "move_cursor":
            _move_source_cursor(editor, action)
        elif action.kind == "resize":
            assert action.viewport_size is not None
            cast(Any, editor).resize(*action.viewport_size)
        elif action.kind == "scroll":
            host.scroll_editor(editor, action.value)
        elif action.kind == "focus_cycle":
            host.focus_cycle(target)
        elif action.kind == "workflow_round_trip":
            lifecycle_steps = host.workflow_round_trip()
        elif action.kind == "canvas_round_trip":
            lifecycle_steps = host.canvas_round_trip()
        elif action.kind == "reorder_drag_press":
            host.reorder_drag_press(editor, action.value)
        elif action.kind == "reorder_drag_threshold":
            host.reorder_drag_threshold(editor)
        elif action.kind == "reorder_drag_move":
            host.reorder_drag_move(editor, action.value)
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
            host.mouse_caret(editor, action.position)
        elif action.kind == "mouse_drag_selection":
            assert action.position is not None
            assert action.selection_end is not None
            host.mouse_drag_selection(editor, action.position, action.selection_end)
        elif action.kind == "wheel_weight":
            host.wheel_weight(editor, action.value)
        elif action.kind == "refresh_diagnostics":
            host.refresh_diagnostics(editor)
        elif action.kind == "lora_picker_open":
            host.open_lora_picker(editor)
        elif action.kind == "lora_picker_activate":
            host.activate_first_lora_picker_item(editor)
        elif action.kind == "context_menu":
            assert action.position is not None
            host.open_context_menu(editor, action.position)
        elif action.kind == "context_menu_trigger":
            assert action.position is not None
            host.trigger_context_menu_action(editor, action.position, action.value)
        elif action.kind == "context_menu_trigger_cached":
            host.trigger_cached_context_menu_action(action.value)
        else:
            raise ValueError(f"Unsupported prompt abuse action kind {action.kind!r}.")
        dispatch_thread_cpu_ms = (thread_time() - thread_cpu_started_at) * 1_000.0
        dispatch_ms = (perf_counter() - started_at) * 1_000.0
        runtime_sample = runtime_probe.finish_sample()
    source_exact = _source_matches(editor, action.expected_source)
    caret_exact = _caret_matches(editor, action.expected_cursor_position)
    selection_exact = _anchor_matches(editor, action.expected_anchor_position)
    feature_exact, feature_mismatch = host.capture_feature_checkpoint(editor, action)
    owner_state = capture_prompt_editor_owner_state(editor)
    actual_cursor_position, actual_anchor_position = capture_prompt_cursor_positions(
        editor
    )
    measured_steps = lifecycle_steps or ((_action_label(action), dispatch_ms),)
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
            visible_source_current_after_dispatch=(owner_state.visible_source_current),
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


def _dispatch_typed_text(
    editor: object,
    target: QWidget,
    action: PromptAbuseAction,
    *,
    action_index: int,
    runtime_telemetry: bool,
    counter_probe: PromptAbuseActionCounterProbe,
    counter_deltas: list[PromptAbuseActionOwnerDelta],
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
            source_exact = actual_source == expected_source
            caret_exact = actual_cursor_position == expected_start
            owner_state = capture_prompt_editor_owner_state(editor)
            samples.append(
                PromptAbuseDispatchSample(
                    action_index=action_index,
                    unit_index=unit_index,
                    label=label,
                    dispatch_ms=dispatch_ms,
                    source_exact=source_exact,
                    caret_exact=caret_exact,
                    selection_exact=actual_anchor_position == expected_start,
                    latency_class="text_input",
                    actual_source_on_mismatch=(None if source_exact else actual_source),
                    actual_cursor_position=actual_cursor_position,
                    expected_cursor_position=expected_start,
                    actual_anchor_position=actual_anchor_position,
                    expected_anchor_position=expected_start,
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
        owner_state = capture_prompt_editor_owner_state(editor)
        samples.append(
            PromptAbuseDispatchSample(
                action_index=action_index,
                unit_index=len(action.value),
                label="type:expected-checkpoint",
                dispatch_ms=0.0,
                source_exact=prompt_editor.toPlainText() == action.expected_source,
                caret_exact=_caret_matches(editor, action.expected_cursor_position),
                selection_exact=_anchor_matches(
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


def _dispatch_event_drain(
    host: PromptAbuseActionHost,
    editor: object,
    action: PromptAbuseAction,
    *,
    action_index: int,
    runtime_telemetry: bool,
    counter_probe: PromptAbuseActionCounterProbe,
    counter_deltas: list[PromptAbuseActionOwnerDelta],
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
            host.process_events(cycles=1)
            dispatch_thread_cpu_ms = (thread_time() - thread_cpu_started_at) * 1_000.0
            dispatch_ms = (perf_counter() - started_at) * 1_000.0
            measured_cycles.append(
                (
                    dispatch_ms,
                    dispatch_thread_cpu_ms,
                    runtime_probe.finish_sample(),
                )
            )
            counter_deltas.append(
                counter_probe.finish_unit(
                    action_index=action_index,
                    unit_index=cycle,
                    label=label,
                )
            )
    source_exact = _source_matches(editor, action.expected_source)
    caret_exact = _caret_matches(editor, action.expected_cursor_position)
    prompt_editor = cast(Any, editor)
    owner_state = capture_prompt_editor_owner_state(editor)
    actual_source = str(prompt_editor.toPlainText())
    actual_cursor_position, actual_anchor_position = capture_prompt_cursor_positions(
        editor
    )
    selection_exact = _anchor_matches(editor, action.expected_anchor_position)
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


def _dispatch_key(
    host: PromptAbuseActionHost,
    target: QWidget,
    key_name: str,
) -> None:
    """Dispatch one named editing key through its production route."""

    if key_name == "undo":
        host.undo(target)
        return
    if key_name == "redo":
        host.redo(target)
        return
    control_keys = {
        "copy": Qt.Key.Key_C,
        "cut": Qt.Key.Key_X,
        "select_all": Qt.Key.Key_A,
    }
    control_key = control_keys.get(key_name)
    if control_key is not None:
        QTest.keyClick(target, control_key, Qt.KeyboardModifier.ControlModifier)
        return
    modifier_name, separator, modified_key_name = key_name.partition("_")
    modifier = {
        "shift": Qt.KeyboardModifier.ShiftModifier,
        "control": Qt.KeyboardModifier.ControlModifier,
    }.get(modifier_name)
    if separator and modifier is not None:
        QTest.keyClick(
            target,
            _named_key(modified_key_name),
            modifier,
        )
        return
    QTest.keyClick(target, _named_key(key_name))


def _dispatch_key_chord(target: QWidget, chord: str) -> None:
    """Dispatch one supported modifier chord through Qt's real key route."""

    modifier_name, separator, key_name = chord.partition("+")
    if separator != "+" or modifier_name != "alt":
        raise ValueError(f"Unsupported prompt abuse key chord {chord!r}.")
    QTest.keyPress(
        target,
        _named_key(key_name),
        Qt.KeyboardModifier.AltModifier,
    )


def _named_key(key_name: str) -> Qt.Key:
    """Return one supported Qt key by stable campaign name."""

    key = _QT_KEYS.get(key_name)
    if key is None:
        raise ValueError(f"Unsupported prompt abuse key {key_name!r}.")
    return key


def _select_source_range(editor: object, action: PromptAbuseAction) -> None:
    """Select one source range through the editor's authoritative cursor."""

    assert action.position is not None
    assert action.selection_end is not None
    prompt_editor = cast(Any, editor)
    cursor = prompt_editor.textCursor()
    cursor.setPosition(action.position, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(action.selection_end, QTextCursor.MoveMode.KeepAnchor)
    prompt_editor.setTextCursor(cursor)


def _move_source_cursor(editor: object, action: PromptAbuseAction) -> None:
    """Move the authoritative source cursor to one exact position."""

    assert action.position is not None
    prompt_editor = cast(Any, editor)
    cursor = prompt_editor.textCursor()
    cursor.setPosition(action.position, QTextCursor.MoveMode.MoveAnchor)
    prompt_editor.setTextCursor(cursor)


def _source_matches(editor: object, expected_source: str | None) -> bool:
    """Return whether an action's exact source checkpoint is satisfied."""

    return expected_source is None or cast(Any, editor).toPlainText() == expected_source


def _viewport_point_for_source_position(editor: Any, position: int) -> QPoint:
    """Return a viewport point on one authoritative source caret boundary."""

    surface = editor._surface
    caret_state = surface.projection_document().caret_map.state_for_source_position(
        position
    )
    rect = surface._layout.cursor_rect(
        caret_state,
        scroll_offset=surface._scroll_offset(),
    )
    return QPoint(round(rect.center().x()), round(rect.center().y()))


def _menu_action_labels(menu: object) -> tuple[str, ...]:
    """Return top-level and nested labels from one rendered QFluent menu."""

    labels: list[str] = []
    actions = getattr(menu, "menuActions", None)
    if callable(actions):
        labels.extend(
            action.text() for action in actions() if isinstance(action, QAction)
        )
    for submenu in getattr(menu, "_subMenus", ()):
        labels.extend(_menu_action_labels(submenu))
    return tuple(labels)


def _populate_lazy_submenus(menu: object) -> None:
    """Populate renderer-owned lazy submenus before measuring their actions."""

    for submenu in getattr(menu, "_subMenus", ()):
        populate = getattr(submenu, "populate_if_needed", None)
        if callable(populate):
            populate()


def _menu_actions(menu: object) -> tuple[QAction, ...]:
    """Return every triggerable action from one rendered QFluent menu tree."""

    result: list[QAction] = []
    actions = getattr(menu, "menuActions", None)
    if callable(actions):
        result.extend(action for action in actions() if isinstance(action, QAction))
    for submenu in getattr(menu, "_subMenus", ()):
        result.extend(_menu_actions(submenu))
    return tuple(result)


def _caret_matches(editor: object, expected_position: int | None) -> bool:
    """Return whether an action's exact logical caret checkpoint is satisfied."""

    return (
        expected_position is None
        or capture_prompt_cursor_positions(editor)[0] == expected_position
    )


def _anchor_matches(editor: object, expected_position: int | None) -> bool:
    """Return whether the authoritative selection anchor matches a checkpoint."""

    return (
        expected_position is None
        or capture_prompt_cursor_positions(editor)[1] == expected_position
    )


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


__all__ = ["PromptAbuseActionHost", "dispatch_action"]
