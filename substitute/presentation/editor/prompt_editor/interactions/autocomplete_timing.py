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

"""Own autocomplete source snapshots and refresh timing."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent

from substitute.application.prompt_editor import PromptDocumentView
from substitute.presentation.editor.prompt_editor.autocomplete_refresh_intent import (
    PromptAutocompleteRefreshIntent,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptFeatureSnapshotIdentity,
)


class PromptAutocompleteSourceIdentity(Protocol):
    """Describe source identity fields carried by prepared snapshots."""

    @property
    def source_revision(self) -> int:
        """Return the source revision used to reject stale query results."""
        ...

    @property
    def source_length(self) -> int | None:
        """Return the source length when the source owner can provide it."""
        ...


class PromptAutocompleteTimingCursor(Protocol):
    """Describe read-only cursor behavior needed by autocomplete timing."""

    def position(self) -> int:
        """Return the current source cursor position."""

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor currently selects source text."""


class PromptAutocompleteSourceEditor(Protocol):
    """Describe editor source state consumed by the snapshot owner."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current source text."""

    def textCursor(self) -> PromptAutocompleteTimingCursor:  # noqa: N802
        """Return the editor's live text cursor."""

    def prompt_command_source_identity(self) -> PromptAutocompleteSourceIdentity | None:
        """Return the current command source identity."""


PromptAutocompleteDismissReason = Literal[
    "accepted",
    "escape",
    "focus_lost",
    "editor_hidden",
    "caret_left_query",
    "selection_started",
    "incompatible_query",
    "no_query",
]


class PromptAutocompleteLifecycleRequester(Protocol):
    """Request autocomplete lifecycle updates from prepared source snapshots."""

    def retarget_from_source_snapshot(
        self,
        snapshot: "PromptAutocompleteSourceSnapshot",
    ) -> bool:
        """Retarget active autocomplete state from a prepared snapshot."""

    def refresh_results_from_source_snapshot(
        self,
        snapshot: "PromptAutocompleteSourceSnapshot",
    ) -> None:
        """Refresh autocomplete query/results from a prepared snapshot."""

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Dismiss any active autocomplete state for one lifecycle reason."""


class PromptAutocompleteRefreshTimer(Protocol):
    """Describe the QTimer API used by autocomplete timing."""

    timeout: object

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Set whether this timer fires once."""

    def start(self, delay_ms: int) -> None:
        """Start the timer with a millisecond delay."""

    def stop(self) -> None:
        """Stop the timer."""


@dataclass(frozen=True, slots=True)
class PromptAutocompleteSourceSnapshot:
    """Carry the source state used to build one autocomplete query."""

    source_revision: int
    source_length: int
    source_text: str
    cursor_position: int
    has_selection: bool
    source_identity: PromptAutocompleteSourceIdentity | None
    document_view: PromptDocumentView
    document_view_identity: Hashable
    feature_profile_identity: PromptFeatureSnapshotIdentity
    query_reason: str
    refresh_intent: PromptAutocompleteRefreshIntent


class PromptAutocompleteSourceSnapshotController:
    """Prepare source snapshots for autocomplete query refreshes."""

    def __init__(
        self,
        editor: PromptAutocompleteSourceEditor,
        *,
        document_view_provider: Callable[[], PromptDocumentView],
        feature_profile: PromptFeatureProfileController,
    ) -> None:
        """Store source collaborators behind one prepared-snapshot boundary."""

        self._editor = editor
        self._document_view_provider = document_view_provider
        self._feature_profile = feature_profile

    def snapshot(
        self,
        *,
        query_reason: str,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> PromptAutocompleteSourceSnapshot:
        """Return a prepared autocomplete source snapshot."""

        source_text = self._editor.toPlainText()
        source_identity = self._editor.prompt_command_source_identity()
        cursor = self._editor.textCursor()
        document_view = self._document_view_provider()
        return PromptAutocompleteSourceSnapshot(
            source_revision=(
                0 if source_identity is None else source_identity.source_revision
            ),
            source_length=(
                len(source_text)
                if source_identity is None or source_identity.source_length is None
                else source_identity.source_length
            ),
            source_text=source_text,
            cursor_position=cursor.position(),
            has_selection=cursor.hasSelection(),
            source_identity=source_identity,
            document_view=document_view,
            document_view_identity=id(document_view),
            feature_profile_identity=self._feature_profile.identity,
            query_reason=query_reason,
            refresh_intent=refresh_intent,
        )


class PromptAutocompleteTimingController:
    """Own autocomplete debounce, timer lifecycle, and source snapshot requests."""

    _CARET_SETTLE_DELAY_MS = 90
    _EDIT_SETTLE_DELAY_MS = 90

    def __init__(
        self,
        *,
        source_snapshots: PromptAutocompleteSourceSnapshotController,
        lifecycle_requester: PromptAutocompleteLifecycleRequester,
        lora_autocomplete_enabled: Callable[[], bool],
        timer_factory: Callable[[], PromptAutocompleteRefreshTimer] | None = None,
    ) -> None:
        """Store timing collaborators without owning query construction."""

        self._source_snapshots = source_snapshots
        self._lifecycle_requester = lifecycle_requester
        self._lora_autocomplete_enabled = lora_autocomplete_enabled
        self._timer_factory: Callable[[], PromptAutocompleteRefreshTimer] = (
            timer_factory
            if timer_factory is not None
            else cast(Callable[[], PromptAutocompleteRefreshTimer], QTimer)
        )
        self._refresh_timer: PromptAutocompleteRefreshTimer | None = None
        self._refresh_revision = 0
        self._pending_refresh_revision: int | None = None
        self._pending_refresh_query_hint = "unknown"
        self._pending_refresh_reason = "unknown"
        self._pending_refresh_intent: PromptAutocompleteRefreshIntent = "programmatic"
        self._active_refresh_revision: int | None = None
        self._latest_source_snapshot: PromptAutocompleteSourceSnapshot | None = None

    @property
    def latest_source_snapshot(self) -> PromptAutocompleteSourceSnapshot | None:
        """Return the latest source snapshot sent to query refresh."""

        return self._latest_source_snapshot

    @property
    def caret_settle_delay_ms(self) -> int:
        """Return the caret-movement autocomplete debounce interval."""

        return self._CARET_SETTLE_DELAY_MS

    @property
    def edit_settle_delay_ms(self) -> int:
        """Return the edit-key autocomplete debounce interval."""

        return self._EDIT_SETTLE_DELAY_MS

    def refresh_from_current_state(self) -> None:
        """Refresh autocomplete from a prepared source snapshot immediately."""

        self._refresh_from_current_state(
            query_reason="manual_refresh",
            refresh_intent="programmatic",
        )

    def handle_post_key_press(self, event: QKeyEvent) -> None:
        """Schedule autocomplete work after the editor has applied a key press."""

        prefix_snapshot = self._lora_prefix_snapshot()
        if prefix_snapshot is not None and prefix_snapshot.has_selection:
            self.schedule_refresh(
                delay_ms=0,
                query_hint="post_edit",
                schedule_reason="post_edit",
                refresh_intent="typing",
            )
            return
        if prefix_snapshot is not None and self._should_refresh_lora_prefix_immediately(
            prefix_snapshot
        ):
            self._retarget_from_source_snapshot(prefix_snapshot)
            self.schedule_refresh(
                delay_ms=0,
                query_hint="lora_prefix",
                schedule_reason="lora_prefix_edit",
                refresh_intent="typing",
            )
            return
        if self._should_debounce_refresh_for_edit_key(event):
            self._retarget_from_current_state(
                query_reason="edit_retarget",
                refresh_intent="typing",
            )
            self.schedule_refresh(
                delay_ms=self._EDIT_SETTLE_DELAY_MS,
                query_hint="edit_key",
                schedule_reason="edit_debounce",
                refresh_intent="typing",
            )
            return
        if self._should_debounce_refresh_for_key(event):
            self.suppress_for_caret_navigation()
            return
        self._retarget_from_current_state(
            query_reason="post_edit_retarget",
            refresh_intent="typing",
        )
        self.schedule_refresh(
            delay_ms=0,
            query_hint="post_edit",
            schedule_reason="post_edit",
            refresh_intent="typing",
        )

    def clear_for_non_text_interaction(self) -> None:
        """Dismiss autocomplete before entering non-text prompt interactions."""

        self.cancel_pending_caret_refresh()
        self._lifecycle_requester.dismiss_autocomplete("incompatible_query")

    def schedule_caret_refresh(self) -> None:
        """Refresh autocomplete after caret-only movement settles briefly."""

        self.schedule_refresh(
            delay_ms=self._CARET_SETTLE_DELAY_MS,
            query_hint="caret",
            schedule_reason="caret_debounce",
            refresh_intent="caret_navigation",
        )

    def suppress_for_caret_navigation(self) -> None:
        """Dismiss autocomplete after keyboard caret movement without reopening it."""

        self.cancel_pending_caret_refresh()
        self._lifecycle_requester.dismiss_autocomplete("caret_left_query")

    def suppress_for_mouse_navigation(self) -> None:
        """Dismiss autocomplete after mouse caret movement without reopening it."""

        self.cancel_pending_caret_refresh()
        self._lifecycle_requester.dismiss_autocomplete("caret_left_query")

    def schedule_refresh(
        self,
        *,
        delay_ms: int,
        query_hint: str,
        schedule_reason: str,
        refresh_intent: PromptAutocompleteRefreshIntent = "programmatic",
    ) -> None:
        """Schedule one revisioned autocomplete refresh."""

        self._refresh_revision += 1
        self._pending_refresh_revision = self._refresh_revision
        self._pending_refresh_query_hint = query_hint
        self._pending_refresh_reason = schedule_reason
        self._pending_refresh_intent = refresh_intent
        refresh_timer = self._ensure_refresh_timer()
        refresh_timer.start(delay_ms)

    def cancel_pending_caret_refresh(self) -> None:
        """Stop any delayed autocomplete refresh still pending."""

        self._refresh_revision += 1
        refresh_timer = self._refresh_timer
        if refresh_timer is None:
            self._pending_refresh_revision = None
            self._pending_refresh_query_hint = "unknown"
            self._pending_refresh_reason = "unknown"
            self._pending_refresh_intent = "programmatic"
            return
        refresh_timer.stop()
        self._pending_refresh_revision = None
        self._pending_refresh_query_hint = "unknown"
        self._pending_refresh_reason = "unknown"
        self._pending_refresh_intent = "programmatic"

    def handle_focus_out(self) -> None:
        """Clear autocomplete when focus leaves the editor interaction flow."""

        self.cancel_pending_caret_refresh()
        self._lifecycle_requester.dismiss_autocomplete("focus_lost")

    def handle_hide(self) -> None:
        """Clear autocomplete when the editor hides."""

        self.cancel_pending_caret_refresh()
        self._lifecycle_requester.dismiss_autocomplete("editor_hidden")

    def _refresh_from_current_state(
        self,
        *,
        query_reason: str,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> None:
        """Prepare and publish one source snapshot to the query owner."""

        snapshot = self._source_snapshots.snapshot(
            query_reason=query_reason,
            refresh_intent=refresh_intent,
        )
        self._latest_source_snapshot = snapshot
        self._lifecycle_requester.refresh_results_from_source_snapshot(snapshot)

    def _retarget_from_current_state(
        self,
        *,
        query_reason: str,
        refresh_intent: PromptAutocompleteRefreshIntent,
    ) -> bool:
        """Prepare a snapshot and retarget active autocomplete immediately."""

        snapshot = self._source_snapshots.snapshot(
            query_reason=query_reason,
            refresh_intent=refresh_intent,
        )
        return self._retarget_from_source_snapshot(snapshot)

    def _retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Publish one prepared snapshot to the lifecycle retarget owner."""

        self._latest_source_snapshot = snapshot
        return self._lifecycle_requester.retarget_from_source_snapshot(snapshot)

    def _ensure_refresh_timer(self) -> PromptAutocompleteRefreshTimer:
        """Create the single-shot refresh timer on first use."""

        refresh_timer = self._refresh_timer
        if refresh_timer is not None:
            return refresh_timer
        refresh_timer = self._timer_factory()
        refresh_timer.setSingleShot(True)
        timeout_signal = refresh_timer.timeout
        connect = getattr(timeout_signal, "connect")
        connect(self._refresh_pending_autocomplete)
        self._refresh_timer = refresh_timer
        return refresh_timer

    def _refresh_pending_autocomplete(self) -> None:
        """Apply the latest scheduled autocomplete refresh and ignore stale timers."""

        revision = self._pending_refresh_revision
        query_reason = self._pending_refresh_reason
        refresh_intent = self._pending_refresh_intent
        self._pending_refresh_revision = None
        self._pending_refresh_query_hint = "unknown"
        self._pending_refresh_reason = "unknown"
        self._pending_refresh_intent = "programmatic"
        if revision is None or revision != self._refresh_revision:
            return
        previous_active_revision = self._active_refresh_revision
        self._active_refresh_revision = revision
        try:
            self._refresh_from_current_state(
                query_reason=query_reason,
                refresh_intent=refresh_intent,
            )
        finally:
            self._active_refresh_revision = previous_active_revision

    def _lora_prefix_snapshot(self) -> PromptAutocompleteSourceSnapshot | None:
        """Return a prepared snapshot when LoRA prefix probing is enabled."""

        if not self._lora_autocomplete_enabled():
            return None
        return self._source_snapshots.snapshot(
            query_reason="lora_prefix_probe",
            refresh_intent="typing",
        )

    @staticmethod
    def _should_refresh_lora_prefix_immediately(
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Return whether the current edit is entering an unclosed LoRA prefix."""

        if snapshot.has_selection:
            return False
        cursor_position = snapshot.cursor_position
        prompt_text = snapshot.source_text
        if cursor_position < 1 or cursor_position > len(prompt_text):
            return False
        prefix_start = prompt_text.rfind("<", 0, cursor_position)
        if prefix_start < 0:
            return False
        typed_prefix = prompt_text[prefix_start:cursor_position].casefold()
        if ">" in typed_prefix:
            return False
        return "<lora:".startswith(typed_prefix) or typed_prefix.startswith("<lora:")

    @staticmethod
    def _should_debounce_refresh_for_key(event: QKeyEvent) -> bool:
        """Return whether one post-keypress refresh should be delayed."""

        if bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return False
        return event.key() in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        }

    @staticmethod
    def _should_debounce_refresh_for_edit_key(event: QKeyEvent) -> bool:
        """Return whether an edit key should coalesce autocomplete after idle."""

        if bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return False
        return event.key() in {
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        }


__all__ = [
    "PromptAutocompleteDismissReason",
    "PromptAutocompleteLifecycleRequester",
    "PromptAutocompleteRefreshTimer",
    "PromptAutocompleteSourceEditor",
    "PromptAutocompleteSourceIdentity",
    "PromptAutocompleteSourceSnapshot",
    "PromptAutocompleteSourceSnapshotController",
    "PromptAutocompleteTimingController",
    "PromptAutocompleteTimingCursor",
]
