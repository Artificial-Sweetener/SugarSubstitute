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

"""Verify Phase 27.2 autocomplete timing and source snapshot ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_timing import (
    PromptAutocompleteSourceSnapshot,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)


class _Cursor:
    """Expose deterministic cursor state to the timing owner."""

    def __init__(self, *, position: int, has_selection: bool = False) -> None:
        """Store cursor state."""

        self._position = position
        self._has_selection = has_selection

    def position(self) -> int:
        """Return the cursor position."""

        return self._position

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor has a selection."""

        return self._has_selection


class _Editor:
    """Provide mutable editor source state for timing tests."""

    def __init__(self, text: str, *, has_selection: bool = False) -> None:
        """Store source and cursor state."""

        self.text = text
        self.cursor_position = len(text)
        self.has_selection = has_selection
        self.source_revision = 3
        self.text_reads = 0
        self.cursor_reads = 0
        self.identity_reads = 0

    def toPlainText(self) -> str:  # noqa: N802
        """Return source text and record the read."""

        self.text_reads += 1
        return self.text

    def textCursor(self) -> _Cursor:  # noqa: N802
        """Return current cursor state and record the read."""

        self.cursor_reads += 1
        return _Cursor(position=self.cursor_position, has_selection=self.has_selection)

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return source identity and record the read."""

        self.identity_reads += 1
        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )


class _TimerSignal:
    """Expose a Qt-like signal connect method."""

    def __init__(self, timer: "_Timer") -> None:
        """Store the owning timer."""

        self._timer = timer

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the timeout callback."""

        self._timer.callback = callback


class _Timer:
    """Provide deterministic single-shot timer behavior."""

    def __init__(self) -> None:
        """Initialize timer state."""

        self.timeout = _TimerSignal(self)
        self.callback: Callable[[], None] | None = None
        self.started_delays: list[int] = []
        self.stop_calls = 0
        self.single_shot = False

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record single-shot configuration."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record one timer start."""

        self.started_delays.append(delay_ms)

    def stop(self) -> None:
        """Record one timer stop."""

        self.stop_calls += 1

    def fire(self) -> None:
        """Run the stored timeout callback."""

        if self.callback is not None:
            self.callback()


class _LifecycleRequester:
    """Record lifecycle requests sent to the autocomplete owner."""

    def __init__(self) -> None:
        """Initialize request storage."""

        self.retarget_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.refresh_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.dismiss_reasons: list[str] = []

    def retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Record one prepared retarget snapshot."""

        self.retarget_snapshots.append(snapshot)
        return True

    def refresh_results_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> None:
        """Record one prepared source snapshot."""

        self.refresh_snapshots.append(snapshot)

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one explicit dismissal."""

        self.dismiss_reasons.append(reason)


def test_source_snapshot_carries_revision_cursor_document_and_feature_identity() -> (
    None
):
    """Source snapshots should be the only hot-path source read boundary."""

    editor = _Editor("alpha")
    feature_profile = _feature_profile(PromptEditorFeature.LORA_AUTOCOMPLETE)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(editor.text)
    snapshots = PromptAutocompleteSourceSnapshotController(
        editor,
        document_view_provider=lambda: document_view,
        feature_profile=feature_profile,
    )

    snapshot = snapshots.snapshot(
        query_reason="unit",
        refresh_intent="programmatic",
    )

    assert snapshot.source_revision == 3
    assert snapshot.source_length == len("alpha")
    assert snapshot.source_text == "alpha"
    assert snapshot.cursor_position == len("alpha")
    assert snapshot.has_selection is False
    assert snapshot.source_identity == PromptCommandSourceIdentity(
        source_revision=3,
        source_length=len("alpha"),
    )
    assert snapshot.document_view is document_view
    assert snapshot.document_view_identity == id(document_view)
    assert snapshot.feature_profile_identity == feature_profile.identity
    assert snapshot.query_reason == "unit"
    assert snapshot.refresh_intent == "programmatic"
    assert editor.text_reads == 1
    assert editor.cursor_reads == 1
    assert editor.identity_reads == 1


def test_debounce_uses_latest_revision_and_refreshes_from_prepared_snapshot() -> None:
    """Debounced refresh should publish only the latest pending timer revision."""

    editor = _Editor("alpha")
    lifecycle = _LifecycleRequester()
    timer = _Timer()
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timer=timer,
        feature_profile=_feature_profile(),
    )

    controller.schedule_caret_refresh()
    controller.schedule_caret_refresh()

    assert timer.started_delays == [
        controller.caret_settle_delay_ms,
        controller.caret_settle_delay_ms,
    ]

    editor.text = "alphabet"
    editor.cursor_position = len("alphabet")
    editor.source_revision = 4
    timer.fire()

    assert len(lifecycle.refresh_snapshots) == 1
    assert lifecycle.refresh_snapshots[0].source_text == "alphabet"
    assert lifecycle.refresh_snapshots[0].source_revision == 4
    assert lifecycle.refresh_snapshots[0].query_reason == "caret_debounce"
    assert lifecycle.refresh_snapshots[0].refresh_intent == "caret_navigation"
    assert controller.latest_source_snapshot == lifecycle.refresh_snapshots[0]


def test_arrow_key_post_press_suppresses_autocomplete_refresh() -> None:
    """Caret-only key navigation should clear autocomplete without reopening it."""

    editor = _Editor("alpha")
    lifecycle = _LifecycleRequester()
    timer = _Timer()
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timer=timer,
        feature_profile=_feature_profile(),
    )

    controller.handle_post_key_press(_key_event(Qt.Key.Key_Right))
    timer.fire()

    assert lifecycle.dismiss_reasons == ["caret_left_query"]
    assert timer.started_delays == []
    assert lifecycle.refresh_snapshots == []


def test_edit_key_retargets_before_debounced_result_refresh() -> None:
    """Backspace/Delete should retarget immediately and debounce heavy results."""

    editor = _Editor("1gi")
    lifecycle = _LifecycleRequester()
    timer = _Timer()
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timer=timer,
        feature_profile=_feature_profile(),
    )

    controller.handle_post_key_press(_key_event(Qt.Key.Key_Backspace))

    assert len(lifecycle.retarget_snapshots) == 1
    assert lifecycle.retarget_snapshots[0].query_reason == "edit_retarget"
    assert lifecycle.retarget_snapshots[0].refresh_intent == "typing"
    assert lifecycle.dismiss_reasons == []
    assert timer.started_delays == [controller.edit_settle_delay_ms]

    timer.fire()

    assert len(lifecycle.refresh_snapshots) == 1
    assert lifecycle.refresh_snapshots[0].query_reason == "edit_debounce"


def test_clear_paths_cancel_pending_timers_without_query_refresh() -> None:
    """Focus, hide, and non-text clears should cancel timing without querying."""

    editor = _Editor("alpha")
    lifecycle = _LifecycleRequester()
    timer = _Timer()
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timer=timer,
        feature_profile=_feature_profile(),
    )

    controller.schedule_caret_refresh()
    controller.clear_for_non_text_interaction()
    controller.handle_focus_out()
    controller.handle_hide()
    timer.fire()

    assert timer.stop_calls == 3
    assert lifecycle.dismiss_reasons == [
        "incompatible_query",
        "focus_lost",
        "editor_hidden",
    ]
    assert lifecycle.refresh_snapshots == []


def test_lora_prefix_immediate_refresh_uses_snapshot_and_selection_suppresses() -> None:
    """Immediate LoRA-prefix refresh should be derived from prepared snapshots."""

    editor = _Editor("<lo")
    lifecycle = _LifecycleRequester()
    timer = _Timer()
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timer=timer,
        feature_profile=_feature_profile(PromptEditorFeature.LORA_AUTOCOMPLETE),
    )

    controller.handle_post_key_press(_key_event(Qt.Key.Key_O))

    assert timer.started_delays == [0]
    assert editor.text_reads == 1

    timer.fire()

    assert lifecycle.refresh_snapshots[-1].query_reason == "lora_prefix_edit"
    assert lifecycle.refresh_snapshots[-1].refresh_intent == "typing"

    selected_editor = _Editor("<lo", has_selection=True)
    selected_timer = _Timer()
    selected_controller = _timing_controller(
        selected_editor,
        lifecycle=_LifecycleRequester(),
        timer=selected_timer,
        feature_profile=_feature_profile(PromptEditorFeature.LORA_AUTOCOMPLETE),
    )

    selected_controller.handle_post_key_press(_key_event(Qt.Key.Key_O))

    assert selected_timer.started_delays == [0]
    assert selected_editor.text_reads == 1


def _timing_controller(
    editor: _Editor,
    *,
    lifecycle: _LifecycleRequester,
    timer: _Timer,
    feature_profile: PromptFeatureProfileController,
) -> PromptAutocompleteTimingController:
    """Build a timing controller with deterministic collaborators."""

    document_service = PromptDocumentService()
    source_snapshots = PromptAutocompleteSourceSnapshotController(
        editor,
        document_view_provider=lambda: document_service.build_document_view(
            editor.text
        ),
        feature_profile=feature_profile,
    )
    return PromptAutocompleteTimingController(
        source_snapshots=source_snapshots,
        lifecycle_requester=lifecycle,
        lora_autocomplete_enabled=lambda: feature_profile.lora_autocomplete_enabled,
        timer_factory=lambda: cast(Any, timer),
    )


def _feature_profile(
    *features: PromptEditorFeature,
) -> PromptFeatureProfileController:
    """Return a feature profile controller for timing tests."""

    return PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(features)
    )


def _key_event(key: Qt.Key) -> QKeyEvent:
    """Return a deterministic key event."""

    return QKeyEvent(
        QKeyEvent.Type.KeyPress,
        int(key),
        Qt.KeyboardModifier.NoModifier,
    )
