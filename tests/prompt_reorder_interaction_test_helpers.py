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

"""Shared doubles for prompt reorder interaction controller tests."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
    PromptReorderLayoutView,
    PromptReorderStateView,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
    PromptSyntaxSpanView,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
    PromptReorderLayoutCommitRequest,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentSession,
    PromptTransientNeutralEmphasisOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_controller import (
    PromptReorderOverlayFactory,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderCommitSnapshot,
)
from substitute.presentation.editor.prompt_editor.syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


class MenuSelectionDouble:
    """Expose the minimal Qt selection API used by controller tests."""

    def __init__(self, cursor: MenuCursorDouble) -> None:
        """Store the cursor backing this selection."""

        self._cursor = cursor

    def isEmpty(self) -> bool:  # noqa: N802
        """Return whether the tracked selection is empty."""

        return self._cursor.selectionStart() == self._cursor.selectionEnd()


class MenuCursorDouble:
    """Provide the minimal cursor API used by reorder controller tests."""

    def __init__(
        self,
        *,
        text: str,
        position: int,
        anchor: int | None = None,
    ) -> None:
        """Store the backing text and cursor anchors."""

        self._text = text
        self._position = position
        self._anchor = position if anchor is None else anchor
        self.moves: list[tuple[int, object | None]] = []

    def sync_text(self, text: str) -> None:
        """Replace the backing text used for selection slices."""

        self._text = text

    def position(self) -> int:
        """Return the current cursor position."""

        return self._position

    def anchor(self) -> int:
        """Return the current cursor anchor."""

        return self._anchor

    def selection(self) -> MenuSelectionDouble:
        """Return the current selection wrapper."""

        return MenuSelectionDouble(self)

    def selectionStart(self) -> int:  # noqa: N802
        """Return the inclusive selection start."""

        return min(self._anchor, self._position)

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the exclusive selection end."""

        return max(self._anchor, self._position)

    def selectedText(self) -> str:  # noqa: N802
        """Return the selected source substring."""

        return self._text[self.selectionStart() : self.selectionEnd()]

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor tracks a non-empty selection."""

        return self.selectionStart() != self.selectionEnd()

    def setPosition(self, pos: int, mode: object | None = None) -> None:  # noqa: N802
        """Move or extend the tracked cursor selection."""

        self.moves.append((pos, mode))
        mode_name = "" if mode is None else str(mode)
        if mode == "keep" or mode_name.endswith("KeepAnchor"):
            self._position = pos
            return
        self._anchor = pos
        self._position = pos


class ControllerEditorDouble:
    """Provide the editor API required by reorder interaction tests."""

    def __init__(
        self,
        *,
        clicked_cursor: MenuCursorDouble,
        current_cursor: MenuCursorDouble,
        text: str,
        parent_widget: object | None = None,
        viewport: object | None = None,
    ) -> None:
        """Store cursors and prompt text used by the controller."""

        self._clicked_cursor = clicked_cursor
        self._current_cursor = current_cursor
        self._text = text
        self._parent_widget = parent_widget
        self._viewport = (
            viewport
            if viewport is not None
            else SimpleNamespace(mapToGlobal=lambda position: position)
        )
        self.reorder_preview_state_calls: list[object | None] = []
        self.clear_reorder_preview_state_calls = 0
        self.autocomplete_preview_state_calls: list[object | None] = []
        self.has_pending_projection_update_result = False
        self.flush_pending_projection_update_calls: list[str] = []
        self._reorder_preview_state: object | None = None
        self.clear_emphasis_adjustment_session_calls = 0
        self.executed_reorder_requests: list[PromptReorderLayoutCommitRequest] = []

    def cursorForPosition(self, _pos: object) -> MenuCursorDouble:  # noqa: N802
        """Return the clicked cursor at the menu position."""

        return self._clicked_cursor

    def textCursor(self) -> MenuCursorDouble:  # noqa: N802
        """Return the current editor cursor."""

        return self._current_cursor

    def setTextCursor(self, cursor: MenuCursorDouble) -> None:  # noqa: N802
        """Persist the supplied cursor."""

        cursor.sync_text(self._text)
        self._current_cursor = cursor

    def toPlainText(self) -> str:  # noqa: N802
        """Return the backing prompt text."""

        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the backing prompt text and synchronize cursors."""

        self._text = text
        self._clicked_cursor.sync_text(text)
        self._current_cursor.sync_text(text)

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return no source identity for direct controller tests."""

        return None

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return no editor-owned active syntax span."""

        return None

    def viewport(self) -> object:
        """Return the editor viewport used by overlay positioning code."""

        return self._viewport

    def parentWidget(self) -> object | None:  # noqa: N802
        """Return the configured parent widget."""

        return self._parent_widget

    def mapFromGlobal(self, position: object) -> object:  # noqa: N802
        """Return the supplied global position unchanged."""

        return position

    def setFocus(self) -> None:  # noqa: N802
        """Accept focus restoration requests."""

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return no active emphasis-adjustment session."""

        return None

    def clear_emphasis_adjustment_session(self) -> None:
        """Record one emphasis session clear request."""

        self.clear_emphasis_adjustment_session_calls += 1

    def clear_transient_neutral_emphasis(self) -> None:
        """Accept transient neutral emphasis clears."""

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return no active transient neutral emphasis owner."""

        return None

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return no active transient neutral emphasis range."""

        return None

    def set_reorder_preview_state(self, preview_state: object | None) -> None:
        """Record explicit reorder preview state pushes."""

        self._reorder_preview_state = preview_state
        self.reorder_preview_state_calls.append(preview_state)

    def clear_reorder_preview_state(self) -> None:
        """Record preview-state clear requests."""

        self._reorder_preview_state = None
        self.clear_reorder_preview_state_calls += 1

    def set_autocomplete_preview_state(self, preview_state: object | None) -> None:
        """Record autocomplete preview updates."""

        self.autocomplete_preview_state_calls.append(preview_state)

    def has_pending_projection_update(self) -> bool:
        """Return whether a projection update is pending."""

        return self.has_pending_projection_update_result

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Record pending projection flushes."""

        self.flush_pending_projection_update_calls.append(reason)
        self.has_pending_projection_update_result = False

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        **_kwargs: object,
    ) -> object:
        """Record unexpected reorder command execution."""

        self.executed_reorder_requests.append(request)
        raise AssertionError("This reorder interaction test should not mutate source.")


class SemanticRefreshControllerDouble:
    """Provide no-op semantic refresh scheduling for direct interaction tests."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.queued_sources: list[tuple[str, str]] = []
        self.flush_reasons: list[str] = []
        self.cancel_reasons: list[str] = []

    def queue_source_changed(
        self,
        source_text: str,
        *,
        reason: str,
        prepared_document_view: object | None = None,
        prepared_render_plan: object | None = None,
    ) -> None:
        """Record one queued semantic refresh request."""

        _ = prepared_document_view, prepared_render_plan
        self.queued_sources.append((source_text, reason))

    def flush(self, *, reason: str) -> None:
        """Record one semantic refresh flush request."""

        self.flush_reasons.append(reason)

    def cancel_pending(self, *, reason: str) -> None:
        """Record one semantic refresh cancellation request."""

        self.cancel_reasons.append(reason)


class SignalDouble:
    """Store and invoke one callback for signal-like test seams."""

    def __init__(self) -> None:
        """Initialize an empty callback slot."""

        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store one callback for later emission."""

        self._callback = callback

    def emit(self) -> None:
        """Invoke the stored callback."""

        assert self._callback is not None
        self._callback()


class FakeTimeoutSignal:
    """Store and invoke one timer callback for deterministic scheduler tests."""

    def __init__(self) -> None:
        """Initialize the fake timeout signal without subscribers."""

        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the callback connected by the production code."""

        self._callback = callback

    def emit(self) -> None:
        """Invoke the connected callback when one exists."""

        assert self._callback is not None
        self._callback()


class FakeQTimer:
    """Provide a deterministic single-shot timer for reorder scheduler tests."""

    instances: list["FakeQTimer"] = []
    single_shots: list[tuple[int, Callable[[], None]]] = []

    def __init__(self) -> None:
        """Track construction and initialize timer state."""

        self.single_shot = False
        self.interval = 0
        self.active = False
        self.started_intervals: list[int] = []
        self.stop_calls = 0
        self.timeout = FakeTimeoutSignal()
        self.__class__.instances.append(self)

    @classmethod
    def singleShot(cls, interval: int, callback: Callable[[], None]) -> None:  # noqa: N802
        """Record one static single-shot callback for manual firing."""

        cls.single_shots.append((interval, callback))

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record the requested single-shot behavior."""

        self.single_shot = single_shot

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Record the interval configured before timer starts."""

        self.interval = interval

    def start(self, interval: int) -> None:
        """Record each requested start interval."""

        self.active = True
        self.started_intervals.append(interval)

    def stop(self) -> None:
        """Record timer cancellation requests."""

        self.active = False
        self.stop_calls += 1

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the fake timer is currently active."""

        return self.active

    def fire(self) -> None:
        """Trigger the connected timeout callback immediately."""

        self.active = False
        self.timeout.emit()


def reorder_state_for_indices(
    ordered_indices: tuple[int, ...],
    *,
    separator: str = ", ",
) -> PromptReorderStateView:
    """Return a deterministic reorder state for controller tests."""

    return PromptReorderStateView(
        ordered_chip_indices=ordered_indices,
        separator_slots=tuple(separator for _ in ordered_indices[:-1]),
        has_trailing_comma=False,
    )


class OverlayDouble:
    """Provide the overlay API used by reorder interaction tests."""

    def __init__(
        self,
        ordered_indices: list[int] | None = None,
        *,
        active_segment_index: int | None = None,
        drop_target: object | None = None,
        dragged_segment_index: int | None = None,
        current_layout_view: PromptReorderLayoutView | None = None,
        base_drag_layout_view: PromptReorderLayoutView | None = None,
        has_base_drag_placement_geometry: bool = False,
        should_flush_initial_landing_shadow_sync: bool = False,
        has_reordered: bool = True,
    ) -> None:
        """Store committed ordering and overlay lifecycle calls."""

        self._ordered_indices = [] if ordered_indices is None else ordered_indices
        self._current_reorder_state = reorder_state_for_indices(
            tuple(self._ordered_indices)
        )
        self._active_segment_index = active_segment_index
        self._drop_target = drop_target
        self._dragged_segment_index = dragged_segment_index
        self._current_layout_view = current_layout_view
        self._preview_layout_view: PromptReorderLayoutView | None = None
        self._base_drag_layout_view = base_drag_layout_view
        self._has_base_drag_placement_geometry = has_base_drag_placement_geometry
        self._should_flush_initial_landing_shadow_sync = (
            should_flush_initial_landing_shadow_sync
        )
        self._has_reordered = has_reordered
        self.cancel_drag_calls = 0
        self.closed = 0
        self.deleted = 0
        self.refresh_geometry_calls = 0
        self.refresh_geometry_reasons: list[str] = []
        self.needs_position_refresh_result = True
        self.needs_position_refresh_calls: list[str] = []
        self.preview_sync_decisions: list[bool] = []
        self.preview_scheduler_events: list[str] = []
        self.autoscroll_flush_calls: list[str] = []
        self.keyboard_move_calls: list[str] = []
        self.keyboard_move_results: dict[str, bool] = {}
        self.keyboard_move_snapshots: dict[str, PromptReorderCommitSnapshot] = {}
        self.current_work_unit_id = 0
        self.previewLayoutChanged = SignalDouble()
        self.drag_handler: Callable[[object], None] | None = None
        self.commit_handler: Callable[[PromptReorderCommitIntent], None] | None = None
        self.cancel_handler: Callable[[PromptReorderCancelIntent], None] | None = None
        self.set_chips_calls: list[
            tuple[object, object, tuple[int, ...], int | None]
        ] = []
        self.preview_snapshot_calls: list[
            tuple[object | None, object | None, tuple[int, ...]]
        ] = []
        self.show_calls = 0

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return the prepared reorder snapshot used by command commit."""

        return PromptReorderCommitSnapshot(
            reorder_state=self._current_reorder_state,
            layout_view=self._current_layout_view,
            ordered_chip_indices=tuple(self._ordered_indices),
            active_segment_index=self._active_segment_index,
            dragged_segment_index=self._dragged_segment_index,
            has_reordered=self._has_reordered,
        )

    def dragged_segment_index(self) -> int | None:
        """Return the configured active dragged segment."""

        return self._dragged_segment_index

    def drop_target(self) -> object | None:
        """Return the configured active drop target."""

        return self._drop_target

    def preview_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the current preview layout for preview sync tests."""

        return self._preview_layout_view

    def base_drag_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the stable base-drag layout view."""

        return self._base_drag_layout_view

    def preview_reorder_state(self) -> PromptReorderStateView | None:
        """Return no active preview reorder state by default."""

        return None

    def base_drag_reorder_state(self) -> PromptReorderStateView | None:
        """Return no base-drag reorder state by default."""

        return None

    def set_chips(
        self,
        document_view: object,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[Any, ...],
        active_chip_index: int | None = None,
        source_revision: int | None = None,
    ) -> None:
        """Record chip publication from reorder mode entry."""

        _ = source_revision
        chip_indices = tuple(segment.index for segment in chips)
        self._ordered_indices = list(chip_indices)
        self._current_layout_view = reorder_layout_view
        self._current_reorder_state = reorder_state
        self.set_chips_calls.append(
            (document_view, reorder_layout_view, chip_indices, active_chip_index)
        )

    def set_preview_snapshot(
        self,
        snapshot: object | None,
        *,
        base_drag_snapshot: object | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Record preview snapshot pushes from the controller."""

        self.preview_snapshot_calls.append(
            (snapshot, base_drag_snapshot, ordered_chip_indices)
        )

    def has_base_drag_placement_geometry(self) -> bool:
        """Return whether this double has base placement geometry."""

        return self._has_base_drag_placement_geometry

    def should_flush_initial_landing_shadow_sync(self) -> bool:
        """Return whether the controller should run the one-shot shadow sync."""

        should_flush = self._should_flush_initial_landing_shadow_sync
        self._should_flush_initial_landing_shadow_sync = False
        return should_flush

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Record coalesced autoscroll flush requests from preview sync."""

        self.autoscroll_flush_calls.append(reason)
        return False

    def record_preview_sync_decision(self, *, immediate: bool) -> None:
        """Record controller preview-sync scheduling decisions."""

        self.preview_sync_decisions.append(immediate)

    def record_preview_scheduler_event(self, event: str) -> None:
        """Record preview-scheduler event classifications."""

        self.preview_scheduler_events.append(event)

    def current_instrumentation_work_unit_id(self) -> int:
        """Return a deterministic pointer work-unit id."""

        return self.current_work_unit_id

    def instrumentation_gesture_id(self) -> int | None:
        """Return no active gesture id."""

        return None

    def instrumentation_event_id(self) -> int | None:
        """Return no active event id."""

        return None

    def is_drag_pointer_loop_active(self) -> bool:
        """Return no active pointer loop."""

        return False

    def cancel_drag(self) -> None:
        """Record drag-cancel requests."""

        self.cancel_drag_calls += 1

    def close(self) -> bool:
        """Record overlay close requests."""

        self.closed += 1
        return True

    def deleteLater(self) -> None:  # noqa: N802
        """Record deferred overlay deletion requests."""

        self.deleted += 1

    def set_drag_handler(self, handler: Callable[[object], None] | None) -> None:
        """Store the drag intent handler."""

        self.drag_handler = handler

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Store the commit intent handler."""

        self.commit_handler = handler

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Store the cancel intent handler."""

        self.cancel_handler = handler

    def refresh_geometry(self, *, reason: str = "test") -> None:
        """Record overlay-local geometry refresh requests."""

        self.refresh_geometry_calls += 1
        self.refresh_geometry_reasons.append(reason)

    def needs_position_refresh(self, *, reason: str = "test") -> bool:
        """Return the configured position-refresh decision."""

        self.needs_position_refresh_calls.append(reason)
        return self.needs_position_refresh_result

    def show(self) -> None:
        """Record overlay show requests."""

        self.show_calls += 1

    def move_active_chip_left(self) -> bool:
        """Record one leftward keyboard reorder request."""

        return self._record_keyboard_move("left")

    def move_active_chip_right(self) -> bool:
        """Record one rightward keyboard reorder request."""

        return self._record_keyboard_move("right")

    def move_active_chip_up(self) -> bool:
        """Record one upward keyboard reorder request."""

        return self._record_keyboard_move("up")

    def move_active_chip_down(self) -> bool:
        """Record one downward keyboard reorder request."""

        return self._record_keyboard_move("down")

    def _record_keyboard_move(self, direction: str) -> bool:
        """Apply a configured keyboard snapshot for one controller test move."""

        self.keyboard_move_calls.append(direction)
        moved = self.keyboard_move_results.get(direction, True)
        if not moved:
            return False
        snapshot = self.keyboard_move_snapshots.get(direction)
        if snapshot is not None:
            self._ordered_indices = list(snapshot.ordered_chip_indices)
            self._active_segment_index = snapshot.active_segment_index
            self._dragged_segment_index = snapshot.dragged_segment_index
            self._current_layout_view = snapshot.layout_view
            if snapshot.reorder_state is not None:
                self._current_reorder_state = snapshot.reorder_state
            self._has_reordered = snapshot.has_reordered
        return True


class OverlayFactoryDouble:
    """Create deterministic reorder overlay doubles."""

    def __init__(self, overlay: OverlayDouble | None = None) -> None:
        """Initialize the factory with an optional prebuilt overlay."""

        self.overlay = overlay or OverlayDouble()
        self.create_calls: list[tuple[object, object]] = []

    def create_segment_overlay(
        self,
        editor: object,
        *,
        layout_policy: object,
    ) -> OverlayDouble:
        """Return the configured overlay double and record construction inputs."""

        self.create_calls.append((editor, layout_policy))
        return self.overlay


class SyntaxRendererCoordinatorDouble:
    """Record syntax-renderer seam updates requested by the interaction controller."""

    def __init__(self, action_result: object | None = None) -> None:
        """Initialize controller-to-renderer call tracking."""

        self.prompt_state_calls: list[tuple[object, PromptSyntaxRenderPlan]] = []
        self.active_span_calls: list[tuple[PromptSyntaxSpanView | None, int]] = []
        self.refresh_geometry_calls = 0
        self.clear_transient_state_calls = 0
        self.action_result = action_result
        self.syntax_action_calls: list[object] = []

    def set_prompt_state(
        self,
        document_view: object,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Record one prompt snapshot replacement."""

        self.prompt_state_calls.append((document_view, render_plan))

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Record one caret-active syntax update."""

        self.active_span_calls.append((active_span, cursor_position))

    def refresh_geometry(self) -> None:
        """Record one syntax-renderer geometry refresh request."""

        self.refresh_geometry_calls += 1

    def clear_transient_state(self) -> None:
        """Record one transient-state clear request."""

        self.clear_transient_state_calls += 1

    def syntax_action_at(self, position: object) -> object | None:
        """Return the configured syntax action for one deterministic position."""

        self.syntax_action_calls.append(position)
        return self.action_result


def autocomplete_double() -> SimpleNamespace:
    """Return the minimal autocomplete collaborator used by controller tests."""

    return SimpleNamespace(
        handle_key_press=lambda _event: False,
        refresh_for_query=lambda _query, **_kwargs: None,
        refresh_for_lora_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: None,
        refresh_geometry=lambda: None,
    )


def syntax_renderer_double(
    action_result: object | None = None,
) -> SyntaxRendererCoordinatorDouble:
    """Return a fresh syntax-renderer seam double for controller tests."""

    return SyntaxRendererCoordinatorDouble(action_result=action_result)


def semantic_refresh_controller_double() -> SemanticRefreshControllerDouble:
    """Return a deterministic semantic refresh controller."""

    return SemanticRefreshControllerDouble()


def syntax_service() -> PromptSyntaxService:
    """Return the standard prompt syntax service used by controller tests."""

    return PromptSyntaxService(EmptyPromptWildcardCatalogGateway())


def prompt_interaction_controller(
    editor: Any,
    *,
    syntax_renderers: SyntaxRendererCoordinatorDouble,
    document_service: PromptDocumentService | None = None,
    mutation_service: PromptMutationService | None = None,
    syntax_service_: PromptSyntaxService | None = None,
    syntax_profile: PromptSyntaxProfile | None = None,
    autocomplete: object | None = None,
    semantic_refresh_controller: object | None = None,
    reorder_overlay_factory: PromptReorderOverlayFactory | None = None,
) -> Any:
    """Build a prompt interaction controller with a syntax-state owner."""

    interaction_module = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.controller"
    )
    resolved_document_service = document_service or PromptDocumentService()
    resolved_syntax_service = syntax_service_ or syntax_service()
    resolved_syntax_profile = syntax_profile or prompt_syntax_profile(
        "emphasis",
        "wildcard",
    )
    syntax_state = PromptSyntaxStateController(
        editor=editor,
        renderers=cast(PromptSyntaxRendererCoordinator, syntax_renderers),
        document_service=resolved_document_service,
        syntax_service=resolved_syntax_service,
        syntax_profile=resolved_syntax_profile,
    )
    return interaction_module.PromptInteractionController(
        editor,
        autocomplete=autocomplete or autocomplete_double(),
        syntax_state=syntax_state,
        document_service=resolved_document_service,
        mutation_service=mutation_service or PromptMutationService(),
        syntax_service=resolved_syntax_service,
        syntax_profile=resolved_syntax_profile,
        semantic_refresh_controller=(
            semantic_refresh_controller or semantic_refresh_controller_double()
        ),
        reorder_overlay_factory=reorder_overlay_factory or OverlayFactoryDouble(),
    )
