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

"""Characterize the focused Qt reorder-overlay session owner."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import cast

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.lifecycle import (
    PromptReorderLifecycleOwner,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_overlay_session import (
    PromptReorderOverlaySessionEditor,
    PromptReorderOverlaySessionOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptEditorInteractionMode,
)
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    OverlayFactoryDouble,
    reorder_state_for_indices,
)


@dataclass
class _SessionHost:
    """Provide immutable entry facts and record transient clearing."""

    document_service: PromptDocumentService
    source_text: str
    enabled: bool = True
    clear_calls: int = 0

    def current_reorder_document_view(self) -> PromptDocumentView:
        """Return the document view used by one session entry request."""

        return self.document_service.build_document_view(self.source_text)

    def segment_reorder_enabled(self) -> bool:
        """Return whether this deterministic host allows reorder entry."""

        return self.enabled

    def clear_transient_state_for_reorder(self) -> None:
        """Record transient cleanup before the session becomes active."""

        self.clear_calls += 1


@dataclass
class _PreviewPublicationDouble:
    """Record the focused preview lifecycle boundary consumed by the session."""

    publishing: bool = False
    reset_reasons: list[str] = field(default_factory=list)
    bindings: list[tuple[object, object, object]] = field(default_factory=list)
    schedule_reasons: list[str] = field(default_factory=list)
    flushes: list[tuple[str | None, bool]] = field(default_factory=list)
    close_reasons: list[str] = field(default_factory=list)
    clear_calls: int = 0
    unbind_calls: int = 0
    pending: bool = False
    on_flush: Callable[[], None] | None = None

    def reset(self, *, reason: str) -> None:
        """Record reset for one accepted overlay session."""

        self.reset_reasons.append(reason)

    def bind_session(
        self,
        *,
        overlay: object,
        build_facts: object,
        sync_context: object,
    ) -> None:
        """Record one complete overlay-preview binding."""

        self.bindings.append((overlay, build_facts, sync_context))

    def schedule(self, *, reason: str) -> None:
        """Record one overlay-originated latest-wins schedule request."""

        self.schedule_reasons.append(reason)

    def has_pending(self) -> bool:
        """Return whether keyboard preparation must flush preview work first."""

        return self.pending

    def flush(self, *, reason: str | None = None, forced: bool = False) -> None:
        """Record one explicit preview flush boundary."""

        self.flushes.append((reason, forced))
        self.pending = False
        if self.on_flush is not None:
            self.on_flush()

    def close(self, *, reason: str) -> None:
        """Record scheduler/cache closure before overlay hiding."""

        self.close_reasons.append(reason)

    def clear_published_state(self) -> None:
        """Record live-paint restoration after overlay closure."""

        self.clear_calls += 1

    def unbind_session(self) -> None:
        """Record release of all overlay-owned preview authorities."""

        self.unbind_calls += 1


def test_overlay_session_owns_entry_binding_and_cancel_teardown_order() -> None:
    """Entry and cancellation must keep application policy and Qt lifetime separate."""

    owner, editor, overlay, host, preview, _lifecycle = _owner_for_text("alpha, beta")

    owner.enter()

    assert owner.overlay is overlay
    assert owner.interaction_mode is PromptEditorInteractionMode.SEGMENT_REORDER
    assert host.clear_calls == 1
    assert preview.reset_reasons == ["overlay_show"]
    assert preview.bindings and preview.bindings[0][0] is overlay
    assert overlay.show_calls == 1
    assert overlay.set_chips_calls
    assert overlay.commit_handler is not None
    assert overlay.cancel_handler is not None

    owner.cancel(PromptReorderCancelIntent(reason="test", restore_selection=False))

    assert overlay.cancel_drag_calls == 1
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert preview.close_reasons == ["overlay_close"]
    assert preview.clear_calls == 1
    assert preview.unbind_calls == 1
    assert owner.overlay is None
    assert owner.interaction_mode is PromptEditorInteractionMode.TEXT_EDITING
    assert editor.toPlainText() == "alpha, beta"


def test_overlay_session_captures_keyboard_snapshot_before_forced_preview_flush() -> (
    None
):
    """Keyboard moves must publish application commit truth before visual sync work."""

    owner, _editor, overlay, _host, preview, lifecycle = _owner_for_text(
        "alpha, beta, gamma"
    )
    owner.enter()
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0, 2)),
        layout_view=overlay.commit_snapshot().layout_view,
        ordered_chip_indices=(1, 0, 2),
        active_segment_index=1,
        dragged_segment_index=None,
        has_reordered=True,
    )
    overlay.keyboard_move_snapshots["left"] = snapshot
    observed_snapshots: list[PromptReorderCommitSnapshot | None] = []
    preview.on_flush = lambda: observed_snapshots.append(
        lifecycle.latest_commit_snapshot
    )

    owner.move_keyboard(PromptReorderKeyboardMoveIntent(direction="left"))

    assert lifecycle.latest_commit_snapshot == snapshot
    assert lifecycle.session_state.current_ordered_indices == (1, 0, 2)
    assert observed_snapshots == [snapshot]
    assert preview.flushes == [("keyboard_reorder_key", True)]


def test_overlay_session_positioning_is_damage_bounded() -> None:
    """Unchanged viewport inputs must not trigger a broad overlay geometry refresh."""

    owner, _editor, overlay, _host, _preview, _lifecycle = _owner_for_text(
        "alpha, beta"
    )
    owner.enter()
    overlay.needs_position_refresh_result = False

    owner.position()

    assert overlay.needs_position_refresh_calls == ["interaction_position_overlay"]
    assert overlay.refresh_geometry_calls == 0


def test_overlay_session_refreshes_when_viewport_geometry_changes() -> None:
    """A changed viewport key performs exactly one overlay geometry refresh."""

    owner, _editor, overlay, _host, _preview, _lifecycle = _owner_for_text(
        "alpha, beta"
    )
    owner.enter()
    overlay.needs_position_refresh_result = True

    owner.position()

    assert overlay.needs_position_refresh_calls == ["interaction_position_overlay"]
    assert overlay.refresh_geometry_reasons == ["interaction_position_overlay"]


def test_overlay_session_skips_positioning_during_atomic_preview_publication() -> None:
    """Reentrant viewport events cannot observe a partially published preview."""

    owner, _editor, overlay, _host, preview, _lifecycle = _owner_for_text("alpha, beta")
    owner.enter()
    preview.publishing = True

    owner.position()

    assert overlay.needs_position_refresh_calls == []
    assert overlay.refresh_geometry_calls == 0


def test_overlay_session_keeps_commit_truth_on_keyboard_boundary_noop() -> None:
    """A rejected keyboard move cannot replace the lifecycle's commit snapshot."""

    owner, _editor, overlay, _host, _preview, lifecycle = _owner_for_text(
        "alpha, beta, gamma"
    )
    owner.enter()
    overlay.keyboard_move_results["left"] = False
    initial_snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((0, 1, 2)),
        layout_view=overlay.commit_snapshot().layout_view,
        ordered_chip_indices=(0, 1, 2),
        active_segment_index=0,
        dragged_segment_index=None,
        has_reordered=False,
    )
    lifecycle.capture_snapshot(initial_snapshot)

    owner.move_keyboard(PromptReorderKeyboardMoveIntent(direction="left"))

    assert lifecycle.latest_commit_snapshot is initial_snapshot
    assert lifecycle.session_state.current_ordered_indices == (0, 1, 2)
    assert lifecycle.session_state.has_reordered is False
    assert overlay.keyboard_move_calls == ["left"]


def test_overlay_session_captures_pointer_commit_without_source_mutation() -> None:
    """A pointer callback records authoritative commit truth for later execution."""

    owner, editor, overlay, _host, _preview, lifecycle = _owner_for_text("alpha, beta")
    owner.enter()
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=reorder_state_for_indices((1, 0)),
        layout_view=overlay.commit_snapshot().layout_view,
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )

    assert overlay.commit_handler is not None
    overlay.commit_handler(
        PromptReorderCommitIntent(reason="pointer_drop", snapshot=snapshot)
    )

    assert lifecycle.latest_commit_snapshot is snapshot
    assert editor.toPlainText() == "alpha, beta"


def _owner_for_text(
    text: str,
) -> tuple[
    PromptReorderOverlaySessionOwner,
    ControllerEditorDouble,
    OverlayDouble,
    _SessionHost,
    _PreviewPublicationDouble,
    PromptReorderLifecycleOwner,
]:
    """Build one focused session owner with deterministic presentation ports."""

    document_service = PromptDocumentService()
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=7),
        current_cursor=MenuCursorDouble(text=text, position=7),
        text=text,
    )
    overlay = OverlayDouble()
    host = _SessionHost(document_service=document_service, source_text=text)
    preview = _PreviewPublicationDouble()
    lifecycle = PromptReorderLifecycleOwner(document_service)
    owner = PromptReorderOverlaySessionOwner(
        cast(PromptReorderOverlaySessionEditor, editor),
        host=host,
        document_service=document_service,
        lifecycle=lifecycle,
        preview_publication=cast(PromptReorderPreviewPublicationOwner, preview),
        overlay_factory=OverlayFactoryDouble(overlay),
    )
    return owner, editor, overlay, host, preview, lifecycle
