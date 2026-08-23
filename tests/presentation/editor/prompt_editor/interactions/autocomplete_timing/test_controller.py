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

"""Verify prompt autocomplete key-timing controller ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_timing import (
    PromptAutocompleteRefreshTimer,
    PromptAutocompleteSourceSnapshot,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)
from tests.support.prompt_editor.controller_support import key_event


class _FakeTimeoutSignal:
    """Record one timeout callback for deterministic timer tests."""

    def __init__(self) -> None:
        """Initialize an empty callback slot."""

        self.callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the timeout callback."""

        self.callback = callback

    def emit(self) -> None:
        """Run the connected callback."""

        assert self.callback is not None
        self.callback()


class _FakeRefreshTimer:
    """Provide a deterministic refresh timer for timing-controller tests."""

    def __init__(self) -> None:
        """Initialize timer state."""

        self.timeout = _FakeTimeoutSignal()
        self.single_shot = False
        self.started_intervals: list[int] = []
        self.stop_calls = 0

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record single-shot configuration."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record one start interval."""

        self.started_intervals.append(delay_ms)

    def stop(self) -> None:
        """Record one cancellation."""

        self.stop_calls += 1

    def fire(self) -> None:
        """Trigger the connected timeout callback."""

        self.timeout.emit()


class _TimingCursor:
    """Expose cursor position and selection state for timing tests."""

    def __init__(self, *, position: int, has_selection: bool = False) -> None:
        """Store cursor state."""

        self._position = position
        self._has_selection = has_selection

    def position(self) -> int:
        """Return the configured cursor position."""

        return self._position

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor has a selection."""

        return self._has_selection


class _TimingEditor:
    """Expose prompt text without projection-flush behavior for timing tests."""

    def __init__(self, text: str) -> None:
        """Store prompt text and initialize flush accounting."""

        self.text = text
        self.flush_calls: list[str] = []

    def toPlainText(self) -> str:  # noqa: N802
        """Return the configured prompt text."""

        return self.text

    def textCursor(self) -> _TimingCursor:  # noqa: N802
        """Return a cursor at the end of the prompt text."""

        return _TimingCursor(position=len(self.text))

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for timing tests."""

        return None

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Record unexpected projection flushes."""

        self.flush_calls.append(reason)


class _LifecycleRequester:
    """Record lifecycle snapshots requested by timing tests."""

    def __init__(self) -> None:
        """Initialize snapshot accounting."""

        self.retarget_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.refresh_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.dismiss_reasons: list[str] = []

    def retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Record one retarget snapshot."""

        self.retarget_snapshots.append(snapshot)
        return True

    def refresh_results_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> None:
        """Record one snapshot refresh."""

        self.refresh_snapshots.append(snapshot)

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one dismiss reason."""

        self.dismiss_reasons.append(reason)


def _timing_controller(
    editor: _TimingEditor,
    *,
    lifecycle: _LifecycleRequester,
    timers: list[_FakeRefreshTimer],
    lora_enabled: bool = False,
) -> PromptAutocompleteTimingController:
    """Return an autocomplete timing controller backed by deterministic fakes."""

    feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.LORA_AUTOCOMPLETE,) if lora_enabled else (),
        )
    )
    document_view = PromptDocumentService().build_document_view(editor.text)

    def timer_factory() -> PromptAutocompleteRefreshTimer:
        """Create and record one fake timer."""

        timer = _FakeRefreshTimer()
        timers.append(timer)
        return cast(PromptAutocompleteRefreshTimer, timer)

    return PromptAutocompleteTimingController(
        source_snapshots=PromptAutocompleteSourceSnapshotController(
            cursor_state=lambda: (
                (cursor := editor.textCursor()).position(),
                cursor.hasSelection(),
            ),
            document_view_provider=lambda: document_view,
            feature_profile=feature_profile,
            source_identity=editor.prompt_command_source_identity,
            source_text=editor.toPlainText,
        ),
        lifecycle_requester=lifecycle,
        lora_autocomplete_enabled=lambda: lora_enabled,
        timer_factory=timer_factory,
    )


def test_post_key_refresh_uses_prepared_snapshot_without_projection_flush() -> None:
    """Post-key refresh uses source snapshots without flushing projection work."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(editor, lifecycle=lifecycle, timers=timers)

    controller.handle_post_key_press(key_event(Qt.Key.Key_E, text="e"))

    assert lifecycle.refresh_snapshots == []
    assert len(timers) == 1
    assert timers[-1].started_intervals == [0]

    timers[-1].fire()

    assert lifecycle.refresh_snapshots[-1].source_text == "1girl, blue"
    assert lifecycle.refresh_snapshots[-1].cursor_position == len("1girl, blue")
    assert lifecycle.refresh_snapshots[-1].refresh_intent == "typing"
    assert editor.flush_calls == []


def test_navigation_key_clears_without_reopening_autocomplete() -> None:
    """Caret-navigation keys dismiss autocomplete without scheduling refresh work."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(editor, lifecycle=lifecycle, timers=timers)

    controller.handle_post_key_press(key_event(Qt.Key.Key_Right))

    assert lifecycle.dismiss_reasons == ["caret_left_query"]
    assert lifecycle.refresh_snapshots == []
    assert timers == []


def test_backspace_retargets_and_debounces_autocomplete_refresh() -> None:
    """Backspace retargets active autocomplete and delays heavy result refresh."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(editor, lifecycle=lifecycle, timers=timers)

    controller.handle_post_key_press(key_event(Qt.Key.Key_Backspace))

    assert lifecycle.retarget_snapshots[-1].query_reason == "edit_retarget"
    assert lifecycle.dismiss_reasons == []
    assert lifecycle.refresh_snapshots == []
    assert timers[-1].started_intervals == [controller.edit_settle_delay_ms]

    timers[-1].fire()

    assert lifecycle.refresh_snapshots[-1].source_text == "1girl, blue"
    assert lifecycle.refresh_snapshots[-1].refresh_intent == "typing"


def test_lora_prefix_refreshes_without_edit_delay() -> None:
    """Unclosed LoRA prefix edits refresh immediately when LoRA autocomplete is enabled."""

    for text in ("<", "<l", "<lora:"):
        editor = _TimingEditor(text)
        lifecycle = _LifecycleRequester()
        timers: list[_FakeRefreshTimer] = []
        controller = _timing_controller(
            editor,
            lifecycle=lifecycle,
            timers=timers,
            lora_enabled=True,
        )

        controller.handle_post_key_press(key_event(Qt.Key.Key_A, text=text[-1]))

        assert timers[-1].started_intervals == [0]
