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

"""Tests for prompt reorder interaction controller orchestration."""

from __future__ import annotations

from typing import Any, cast

import pytest

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptReorderCommitIntent,
    PromptReorderCommitSnapshot,
    PromptReorderKeyboardMoveIntent,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    OverlayFactoryDouble,
    autocomplete_double,
    prompt_interaction_controller,
    reorder_state_for_indices,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


def test_show_segment_overlay_clears_autocomplete_before_entering_reorder_mode() -> (
    None
):
    """Entering segment reorder mode dismisses autocomplete before overlay entry."""

    call_order: list[Any] = []

    class _FakeSegmentOverlay(OverlayDouble):
        """Record overlay entry calls through the factory seam."""

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
            super().set_chips(
                document_view,
                reorder_layout_view,
                reorder_state,
                chips=chips,
                active_chip_index=active_chip_index,
                source_revision=source_revision,
            )
            call_order.append(
                (
                    "set_chips",
                    tuple(segment.index for segment in chips),
                    reorder_layout_view,
                    active_chip_index,
                )
            )

        def set_preview_snapshot(
            self,
            snapshot: object | None,
            *,
            base_drag_snapshot: object | None = None,
            ordered_chip_indices: tuple[int, ...],
        ) -> None:
            """Record preview snapshot pushes without affecting call-order assertions."""

            call_order.append(
                (
                    "set_preview_snapshot",
                    snapshot,
                    base_drag_snapshot,
                    ordered_chip_indices,
                )
            )

        def refresh_geometry(self, *, reason: str = "test") -> None:
            """Record overlay geometry refresh ordering."""

            super().refresh_geometry(reason=reason)
            call_order.append(("refresh_geometry", reason))

        def show(self) -> None:
            """Record overlay show ordering."""

            super().show()
            call_order.append("show")

    class _Factory(OverlayFactoryDouble):
        """Record overlay creation in the test call order."""

        def create_segment_overlay(
            self,
            editor: object,
            *,
            layout_policy: object,
        ) -> OverlayDouble:
            call_order.append(("overlay_init", editor))
            return super().create_segment_overlay(
                editor,
                layout_policy=layout_policy,
            )

    overlay = _FakeSegmentOverlay([0, 1])
    overlay_factory = _Factory(overlay)
    autocomplete = autocomplete_double()
    autocomplete.dismiss_autocomplete = lambda _reason: call_order.append("clear")
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    syntax_renderers = syntax_renderer_double()
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete,
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers,
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=overlay_factory,
    )

    controller._reorder.enter_segment_reorder_mode()

    assert call_order[0] == "clear"
    assert syntax_renderers.clear_transient_state_calls == 1
    assert ("overlay_init", editor) in call_order
    assert any(
        entry[0] == "set_chips" and entry[1] == (0, 1) and entry[3] == 1
        for entry in call_order
    )
    assert ("refresh_geometry", "interaction_position_overlay") not in call_order
    assert call_order.index("show") < next(
        index
        for index, entry in enumerate(call_order)
        if isinstance(entry, tuple) and entry[0] == "set_chips"
    )
    assert controller._reorder.segment_reorder_session.is_active is True
    assert controller._reorder.segment_reorder_session.original_ordered_indices == (
        0,
        1,
    )
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (0, 1)
    assert controller._reorder.segment_reorder_session.active_segment_index == 1
    assert controller._reorder.segment_reorder_session.selection_start == 7
    assert controller._reorder.segment_reorder_session.selection_end == 7
    assert (
        controller._reorder.segment_reorder_session.selection_start_offset_within_active_chip
        == 0
    )
    assert (
        controller._reorder.segment_reorder_session.selection_end_offset_within_active_chip
        == 0
    )
    assert controller.segment_overlay is not None


def test_show_segment_overlay_syncs_preview_state_through_editor_surface() -> None:
    """Overlay entry clears stale preview state before explicit preview sync."""

    overlay = OverlayDouble([0, 1])
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=OverlayFactoryDouble(overlay),
    )

    controller._reorder.enter_segment_reorder_mode()

    assert controller.segment_overlay is overlay
    assert editor.reorder_preview_state_calls == []
    assert editor.clear_reorder_preview_state_calls == 1
    assert overlay.preview_snapshot_calls == []

    overlay._preview_layout_view = overlay._current_layout_view
    overlay.previewLayoutChanged.emit()

    assert editor.reorder_preview_state_calls == []
    controller._reorder.flush_pending_reorder_preview_sync()

    assert len(editor.reorder_preview_state_calls) == 1
    preview_state = editor.reorder_preview_state_calls[0]
    assert preview_state is not None
    preview_state = cast(Any, preview_state)
    assert preview_state.preview_snapshot.document_view.source_text == "alpha, beta"
    assert overlay.preview_snapshot_calls[-1][0] is not None

    controller._reorder._close_segment_overlay(restore_selection=False)

    assert editor.clear_reorder_preview_state_calls == 2


def test_close_segment_overlay_restores_live_paint_after_overlay_is_hidden() -> None:
    """Final live-paint invalidation must run after the covering overlay closes."""

    call_order: list[str] = []

    class _Editor(ControllerEditorDouble):
        """Record when live projection painting is restored."""

        def clear_reorder_preview_state(self) -> None:
            super().clear_reorder_preview_state()
            call_order.append("clear_preview")

    class _Overlay(OverlayDouble):
        """Record when the viewport-covering overlay is hidden."""

        def close(self) -> bool:
            call_order.append("close_overlay")
            return super().close()

    overlay = _Overlay([0, 1])
    editor = _Editor(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        reorder_overlay_factory=OverlayFactoryDouble(overlay),
    )
    controller._reorder._segment_overlay = overlay

    controller._reorder._close_segment_overlay(restore_selection=False)

    assert call_order == ["close_overlay", "clear_preview"]
    assert controller.segment_overlay is None


def test_overlay_pointer_drop_updates_commit_snapshot_without_source_mutation() -> None:
    """Pointer-drop intent prepares commit state without executing source mutation."""

    controller, editor, _document_service, layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble([0, 1], current_layout_view=layout_view)
    controller._reorder._segment_overlay = overlay
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )

    controller._reorder._handle_overlay_commit_intent(
        PromptReorderCommitIntent(reason="pointer_drop", snapshot=snapshot)
    )

    assert editor.toPlainText() == "alpha, beta"
    assert editor.executed_reorder_requests == []
    assert controller._reorder.latest_commit_snapshot is snapshot
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (
        1,
        0,
    )
    assert controller._reorder.segment_reorder_session.has_reordered is True


def test_reorder_preview_sync_does_not_overwrite_latest_commit_snapshot() -> None:
    """Display preview sync does not replace the authoritative commit snapshot."""

    controller, editor, _document_service, layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble(
        [0, 1],
        current_layout_view=layout_view,
        has_reordered=False,
    )
    overlay._preview_layout_view = layout_view
    controller._reorder._segment_overlay = overlay
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )
    controller._reorder._session_controller.capture_snapshot(snapshot)

    controller._reorder.schedule_reorder_preview_sync(reason="preview_only")
    controller._reorder.flush_pending_reorder_preview_sync()

    assert editor.toPlainText() == "alpha, beta"
    assert controller._reorder.latest_commit_snapshot is snapshot
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (
        1,
        0,
    )
    assert len(editor.reorder_preview_state_calls) == 1


def test_stale_reorder_preview_sync_does_not_publish_or_reset_commit_snapshot() -> None:
    """Stale display preview sync does not publish state or replace commit truth."""

    controller, editor, _document_service, layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble(
        [0, 1],
        current_layout_view=layout_view,
        has_reordered=False,
    )
    overlay._preview_layout_view = layout_view
    controller._reorder._segment_overlay = overlay
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )
    controller._reorder._session_controller.capture_snapshot(snapshot)
    controller._reorder._preview_sync.replace_state(
        pending_revision=3,
        pending_reason="stale_preview",
        last_applied_revision=4,
    )

    controller._reorder.flush_pending_reorder_preview_sync()

    assert editor.toPlainText() == "alpha, beta"
    assert editor.reorder_preview_state_calls == []
    assert controller._reorder.latest_commit_snapshot is snapshot
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (
        1,
        0,
    )


def test_keyboard_reorder_captures_commit_snapshot_before_preview_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful keyboard moves publish commit state before display sync."""

    text = "alpha, beta, gamma"
    document_service = PromptDocumentService()
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=7),
        current_cursor=MenuCursorDouble(text=text, position=7),
        text=text,
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=document_service,
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    initial_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(),
    )
    moved_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0, 2)),),
        gaps=(),
    )
    overlay = OverlayDouble(
        [0, 1, 2],
        active_segment_index=1,
        current_layout_view=initial_layout_view,
        has_reordered=False,
    )
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0, 2)),
        layout_view=moved_layout_view,
        ordered_chip_indices=(1, 0, 2),
        active_segment_index=1,
        dragged_segment_index=None,
        has_reordered=True,
    )
    overlay.keyboard_move_snapshots["left"] = snapshot
    controller._reorder._segment_overlay = overlay
    controller._reorder._preview_sync.replace_state(
        pending_revision=1,
        pending_reason="queued_keyboard_preview",
    )
    observed_snapshots: list[PromptReorderCommitSnapshot | None] = []

    def record_preview_sync() -> None:
        """Assert commit state was captured before display preview sync."""

        observed_snapshots.append(controller._reorder.latest_commit_snapshot)
        assert controller._reorder.latest_commit_snapshot == snapshot
        assert controller._reorder.segment_reorder_session.current_ordered_indices == (
            1,
            0,
            2,
        )
        assert controller._reorder.segment_reorder_session.has_reordered is True

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_preview_sync,
    )

    controller._reorder.move_keyboard_reorder_chip(
        PromptReorderKeyboardMoveIntent(direction="left")
    )

    assert observed_snapshots == [snapshot]
    assert controller._reorder.latest_commit_snapshot == snapshot
    assert overlay.keyboard_move_calls == ["left"]


def test_keyboard_reorder_boundary_noop_does_not_update_commit_snapshot() -> None:
    """Boundary keyboard no-ops leave controller commit state unchanged."""

    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(),
    )
    text = "alpha, beta, gamma"
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=0),
        current_cursor=MenuCursorDouble(text=text, position=0),
        text=text,
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    overlay = OverlayDouble(
        [0, 1, 2],
        active_segment_index=0,
        current_layout_view=layout_view,
        has_reordered=False,
    )
    overlay.keyboard_move_results["left"] = False
    controller._reorder._segment_overlay = overlay
    initial_snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((0, 1, 2)),
        layout_view=layout_view,
        ordered_chip_indices=(0, 1, 2),
        active_segment_index=0,
        dragged_segment_index=None,
        has_reordered=False,
    )
    controller._reorder._session_controller.capture_snapshot(initial_snapshot)

    controller._reorder.move_keyboard_reorder_chip(
        PromptReorderKeyboardMoveIntent(direction="left")
    )

    assert controller._reorder.latest_commit_snapshot is initial_snapshot
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (
        0,
        1,
        2,
    )
    assert controller._reorder.segment_reorder_session.has_reordered is False
    assert overlay.keyboard_move_calls == ["left"]


def test_keyboard_preview_sync_does_not_overwrite_captured_commit_snapshot() -> None:
    """Keyboard display preview sync does not replace captured commit state."""

    controller, editor, _document_service, layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble(
        [0, 1],
        current_layout_view=layout_view,
        has_reordered=False,
    )
    overlay._preview_layout_view = layout_view
    controller._reorder._segment_overlay = overlay
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=None,
        has_reordered=True,
    )
    controller._reorder._session_controller.capture_snapshot(snapshot)

    controller._reorder.schedule_reorder_preview_sync(reason="keyboard_reorder_key")
    controller._reorder.flush_pending_reorder_preview_sync(forced=True)

    assert controller._reorder.latest_commit_snapshot is snapshot
    assert controller._reorder.segment_reorder_session.current_ordered_indices == (
        1,
        0,
    )
    assert len(editor.reorder_preview_state_calls) == 1


def test_position_segment_overlay_skips_unchanged_position_refresh() -> None:
    """Positioning does not enter broad overlay refresh when inputs are unchanged."""

    controller, _editor, _document_service, _layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble()
    overlay.needs_position_refresh_result = False
    controller._reorder._segment_overlay = overlay

    controller._reorder.position_segment_overlay()

    assert overlay.needs_position_refresh_calls == ["interaction_position_overlay"]
    assert overlay.refresh_geometry_calls == 0


def test_position_segment_overlay_runs_when_position_key_changes() -> None:
    """Positioning refreshes overlay geometry when viewport inputs change."""

    controller, _editor, _document_service, _layout_view = _controller_for_reorder_text(
        "alpha, beta"
    )
    overlay = OverlayDouble()
    overlay.needs_position_refresh_result = True
    controller._reorder._segment_overlay = overlay

    controller._reorder.position_segment_overlay()

    assert overlay.needs_position_refresh_calls == ["interaction_position_overlay"]
    assert overlay.refresh_geometry_reasons == ["interaction_position_overlay"]


def _controller_for_reorder_text(
    text: str,
) -> tuple[Any, ControllerEditorDouble, PromptDocumentService, PromptReorderLayoutView]:
    """Build a reorder interaction controller and layout for one prompt."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    layout_view = document_service.build_reorder_layout_view(document_view)
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=7),
        current_cursor=MenuCursorDouble(text=text, position=7),
        text=text,
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=document_service,
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    return controller, editor, document_service, layout_view
