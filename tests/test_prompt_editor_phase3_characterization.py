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

"""Characterize Phase 3 diagnostic and reorder editor behavior."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import os
from typing import Any, Generic, TypeVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDiagnosticSnapshot,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptSourceNormalizationService,
    PromptSpellingDiagnosticPayload,
    PromptSpellingSuggestionSet,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptEditorCommand,
    build_diagnostic_action_command,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptDiagnosticsFeatureController,
    PromptFeatureProfileController,
    PromptWildcardFeatureController,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    surface_for,
)

TResult = TypeVar("TResult")

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "phase 3 prompt editor characterization tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _DeferredTaskHandle(Generic[TResult]):
    """Store a pending async request until a test completes it."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store the request and pending callbacks."""

        self._request = request
        self._callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self.cancelled_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the pending request identity."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether this fake handle has completed."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the completed outcome when present."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Store or immediately publish one callback."""

        _ = reason
        if self._outcome is not None:
            callback(self._outcome)
            return
        self._callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancelled_reasons.append(reason)

    def run(self) -> None:
        """Execute the request and publish the outcome."""

        try:
            result = self._request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            outcome = PromptAsyncTaskOutcome[TResult](
                identity=self._request.identity,
                context=self._request.context,
                error=error,
            )
        else:
            outcome = PromptAsyncTaskOutcome(
                identity=self._request.identity,
                context=self._request.context,
                result=result,
            )
        self._outcome = outcome
        for callback in tuple(self._callbacks):
            callback(outcome)


class _Token:
    """Provide a never-cancelled token for deferred characterization work."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _DeferredRequestChannel(Generic[TResult]):
    """Capture submitted diagnostics requests so tests can complete them later."""

    def __init__(self) -> None:
        """Initialize pending handle storage."""

        self.handles: list[_DeferredTaskHandle[TResult]] = []
        self.cancelled_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> _DeferredTaskHandle[TResult]:
        """Store one request and return its pending handle."""

        handle: _DeferredTaskHandle[TResult] = _DeferredTaskHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancelled_reasons.append(reason)


class _ImmediateRequestChannel(Generic[TResult]):
    """Complete diagnostics requests synchronously for action tests."""

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> _DeferredTaskHandle[TResult]:
        """Run one request immediately and return its completed handle."""

        handle: _DeferredTaskHandle[TResult] = _DeferredTaskHandle(request)
        handle.run()
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Accept cancellation requests for protocol completeness."""

        _ = reason


class _ImmediateDebouncer:
    """Run debounced callbacks immediately for characterization helpers."""

    @property
    def is_pending(self) -> bool:
        """Return that no callback remains pending."""

        return False

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Invoke the callback immediately."""

        _ = reason
        callback()

    def flush(self, *, reason: str) -> bool:
        """Report that no pending callback was flushed."""

        _ = reason
        return False

    def cancel(self, *, reason: str) -> bool:
        """Report that no pending callback was cancelled."""

        _ = reason
        return False


class _FakeDiagnosticsService:
    """Return deterministic diagnostics for supplied prompt text."""

    def __init__(self) -> None:
        """Initialize request recording."""

        self.calls: list[str] = []

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return one spelling diagnostic for the first word in the text."""

        self.calls.append(text)
        first_word = text.strip().split(" ", 1)[0]
        return PromptDiagnosticSnapshot(
            source_text=text,
            diagnostics=(
                _spelling_diagnostic(
                    0,
                    len(first_word),
                    first_word,
                ),
            ),
        )


class _FakeCursor:
    """Apply source edits for diagnostics controller tests."""

    def __init__(self, editor: "_FakeEditor", position: int = 0) -> None:
        """Store the editor and initial cursor range."""

        self._editor = editor
        self._position = position
        self._anchor = position

    def position(self) -> int:
        """Return the current source cursor position."""

        return self._position

    def setPosition(self, position: int, mode: object | None = None) -> None:  # noqa: N802
        """Move or extend the source selection."""

        if mode == QTextCursor.MoveMode.KeepAnchor:
            self._position = position
            return
        self._position = position
        self._anchor = position

    def insertText(self, text: str) -> None:  # noqa: N802
        """Replace the selected source range."""

        start = min(self._anchor, self._position)
        end = max(self._anchor, self._position)
        self._editor.text = self._editor.text[:start] + text + self._editor.text[end:]
        self._position = start + len(text)
        self._anchor = self._position


class _FakeEditor:
    """Provide the editor API used by diagnostics actions."""

    def __init__(self, text: str, *, cursor_position: int = 0) -> None:
        """Store source text and cursor state."""

        self.text = text
        self.cursor = _FakeCursor(self, cursor_position)
        self.focused = False
        self.source_revision = 0

    def toPlainText(self) -> str:
        """Return current source text."""

        return self.text

    def textCursor(self) -> _FakeCursor:
        """Return the mutable test cursor."""

        return self.cursor

    def setTextCursor(self, cursor: object) -> None:
        """Accept the mutated test cursor."""

        self.cursor = cast(_FakeCursor, cursor)

    def setFocus(self) -> None:
        """Record focus restoration."""

        self.focused = True

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current fake source identity for diagnostic commands."""

        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one diagnostic action through the real command boundary."""

        cursor_state = PromptCursorState(
            cursor_position=self.cursor.position(),
            anchor_position=self.cursor.position(),
        )
        session: PromptEditingSession[object] = PromptEditingSession(
            source_text=self.text,
            source_revision=self.source_revision,
            cursor_state=cursor_state,
            max_undo_states=8,
            max_redo_states=8,
        )
        command: PromptEditorCommand[object] = build_diagnostic_action_command(
            action,
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=PromptUndoSnapshot(
                source_text=session.source_text,
                cursor_state=session.cursor_state,
                restoration_payload=None,
            ),
        )
        result = cast(
            PromptDiagnosticCommandResult[object],
            PromptCommandDispatcher(session).execute(command),
        )
        self.text = session.source_text
        self.source_revision = session.source_revision
        if result.cursor_state is not None:
            self.cursor = _FakeCursor(self, result.cursor_state.cursor_position)
        return result


class _FakeSurface:
    """Capture diagnostics pushed to the projection surface."""

    def __init__(self) -> None:
        """Initialize visible diagnostics state."""

        self.diagnostics: tuple[PromptDiagnostic, ...] = ()

    def set_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Store visible diagnostics."""

        self.diagnostics = diagnostics

    def clear_diagnostics(self) -> None:
        """Clear visible diagnostics."""

        self.diagnostics = ()


class _FakeSpellcheckProvider:
    """Provide deterministic spelling actions for diagnostic menu tests."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.ignored_words: list[str] = []
        self.added_words: list[str] = []
        self.suggestion_words: list[str] = []

    def suggestions_for_word(
        self,
        word: str,
        *,
        limit: int = 8,
    ) -> PromptSpellingSuggestionSet:
        """Return one configured replacement suggestion."""

        _ = limit
        self.suggestion_words.append(word)
        return PromptSpellingSuggestionSet(word=word, suggestions=("type",))

    def ignore_word_for_session(self, word: str) -> None:
        """Record a session-scoped ignore."""

        self.ignored_words.append(word)

    def add_word_to_dictionary(self, word: str) -> bool:
        """Record a persistent dictionary add."""

        self.added_words.append(word)
        return True

    def dictionary_add_supported(self) -> bool:
        """Return that persistent additions are available."""

        return True


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one Phase 3 characterization test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_phase3_async_diagnostics_ignore_stale_snapshots() -> None:
    """Older diagnostics tasks must not overwrite the newest source snapshot."""

    editor = _FakeEditor("oldword ", cursor_position=len("oldword "))
    surface = _FakeSurface()
    service = _FakeDiagnosticsService()
    request_channel: _DeferredRequestChannel[PromptDiagnosticSnapshot] = (
        _DeferredRequestChannel()
    )
    controller = _diagnostics_controller(
        editor,
        _spelling_diagnostic(0, 7, "oldword"),
        surface=surface,
        request_channel=request_channel,
    )
    cast(Any, controller)._service = service
    request_channel.handles.clear()

    controller.refresh_now()
    editor.text = "newword "
    editor.cursor = _FakeCursor(editor, len("newword "))
    controller.refresh_now()

    assert service.calls == []
    assert len(request_channel.handles) == 2

    request_channel.handles[1].run()
    assert [diagnostic.message for diagnostic in surface.diagnostics] == [
        "Possible spelling issue: newword"
    ]

    request_channel.handles[0].run()
    assert [diagnostic.message for diagnostic in surface.diagnostics] == [
        "Possible spelling issue: newword"
    ]


def test_phase3_spelling_context_actions_replace_ignore_and_add_dictionary() -> None:
    """Spelling diagnostic actions should mutate or delegate exactly once."""

    editor = _FakeEditor("one typo ", cursor_position=len("one typo "))
    spellcheck = _FakeSpellcheckProvider()
    controller = _diagnostics_controller(
        editor,
        _spelling_diagnostic(4, 8, "typo"),
        spellcheck_provider=spellcheck,
    )
    controller.refresh_now()
    spellcheck.suggestion_words.clear()

    actions = controller.actions_for_diagnostic(_spelling_diagnostic(4, 8, "typo"))

    assert [action.label for action in actions] == [
        "type",
        "Ignore spelling",
        "Add to dictionary",
    ]
    assert spellcheck.suggestion_words == []

    assert actions[1].callback is not None
    actions[1].callback()
    assert spellcheck.ignored_words == ["typo"]

    assert actions[2].callback is not None
    actions[2].callback()
    assert spellcheck.added_words == ["typo"]

    assert actions[0].callback is not None
    actions[0].callback()
    assert editor.toPlainText() == "one type "
    assert editor.focused is True


def test_phase3_duplicate_context_actions_remove_emphasize_and_ignore() -> None:
    """Duplicate diagnostic actions should cover mutating and non-mutating paths."""

    remove_editor = _FakeEditor("alpha, beta, beta")
    remove_diagnostic = _duplicate_diagnostic(
        text="alpha, beta, beta",
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )
    remove_controller = _diagnostics_controller(remove_editor, remove_diagnostic)
    remove_actions = remove_controller.actions_for_diagnostic(remove_diagnostic)
    assert remove_actions[0].label == "Remove duplicate"
    assert remove_actions[0].callback is not None
    remove_actions[0].callback()
    assert remove_editor.toPlainText() == "alpha, beta"

    emphasize_editor = _FakeEditor("yellow hat, yellow hat")
    emphasize_diagnostic = _duplicate_diagnostic(
        text="yellow hat, yellow hat",
        normalized_segment="yellow hat",
        first_start=0,
        first_end=10,
        duplicate_start=12,
        duplicate_end=22,
    )
    emphasize_controller = _diagnostics_controller(
        emphasize_editor,
        emphasize_diagnostic,
    )
    emphasize_actions = emphasize_controller.actions_for_diagnostic(
        emphasize_diagnostic
    )
    assert emphasize_actions[1].label == "Emphasize first"
    assert emphasize_actions[1].callback is not None
    emphasize_actions[1].callback()
    assert emphasize_editor.toPlainText() == "(yellow hat:1.10)"

    ignore_editor = _FakeEditor("alpha, beta, beta")
    ignore_surface = _FakeSurface()
    ignore_controller = _diagnostics_controller(
        ignore_editor,
        remove_diagnostic,
        surface=ignore_surface,
    )
    ignore_controller.refresh_now()
    assert ignore_surface.diagnostics == (remove_diagnostic,)
    ignore_actions = ignore_controller.actions_for_diagnostic(remove_diagnostic)
    assert ignore_actions[2].label == "Ignore duplicate"
    assert ignore_actions[2].callback is not None
    ignore_actions[2].callback()
    assert len(ignore_surface.diagnostics) == 0


def test_phase3_diagnostic_decorations_preserve_autocomplete_selection_and_cursor(
    widgets: list[QWidget],
) -> None:
    """Diagnostics should preserve selected text state across active decorations."""

    text = "<lora:demo:0.80>, {missing}, (blue sky:1.20), typo"
    box = _show_phase3_editor(widgets, text=text)
    cursor = box.textCursor()
    cursor.setPosition(text.index("blue"), QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(text.index("sky") + len("sky"), QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    surface = surface_for(box)
    surface.set_search_matches(((text.index("typo"), len("typo")),), active_index=0)
    suffix_text = ", sharp focus"
    preview_position = text.index("typo") + len("typ")
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=preview_position,
            suffix_text=suffix_text,
        )
    )
    lora_fragments = surface.source_range_fragments(
        start=text.index("<lora"),
        end=text.index(">") + 1,
    )
    wildcard_fragments = surface.source_range_fragments(
        start=text.index("{missing}"),
        end=text.index("{missing}") + len("{missing}"),
    )
    emphasis_fragments = surface.source_range_fragments(
        start=text.index("(blue"),
        end=text.index(")") + 1,
    )
    cursor_position = box.textCursor().position()
    selection_start = box.textCursor().selectionStart()
    selection_end = box.textCursor().selectionEnd()
    diagnostic = _spelling_diagnostic(text.index("typo"), len(text), "typo")

    surface.set_diagnostics((diagnostic,))
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(float, cast(Any, surface)._scroll_offset())
    diagnostic_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )
    pixmap = QPixmap(surface.viewport().size())
    surface.viewport().render(pixmap)

    preview_state = surface._session.autocomplete_preview  # noqa: SLF001
    assert preview_state is not None
    assert preview_state.suffix_text == suffix_text
    assert surface.active_projection_document() is surface.projection_document()
    assert not any(run.ghosted for run in surface.active_projection_document().runs)
    assert lora_fragments
    assert wildcard_fragments
    assert emphasis_fragments
    assert diagnostic_fragments
    assert surface._session.search_match_ranges == (  # noqa: SLF001
        (text.index("typo"), len("typo")),
    )
    assert surface._session.active_search_match_index == 0  # noqa: SLF001
    assert box.toPlainText() == text
    assert box.textCursor().position() == cursor_position
    assert box.textCursor().selectionStart() == selection_start
    assert box.textCursor().selectionEnd() == selection_end
    assert surface._session.diagnostics  # noqa: SLF001
    assert not pixmap.isNull()


def test_phase3_diagnostic_fragments_follow_autocomplete_preview_layout(
    widgets: list[QWidget],
) -> None:
    """Diagnostics should resolve geometry through layout-backed ghost text."""

    text = "<lora:demo:0.80>, {missing}, (blue sky:1.20), typo"
    box = _show_phase3_editor(widgets, text=text)
    surface = surface_for(box)
    typo_start = text.index("typo")
    preview_position = typo_start + len("typ")
    surface.set_cursor_positions(
        cursor_position=preview_position,
        anchor_position=preview_position,
    )
    suffix_text = ", sharp focus"
    surface.set_search_matches(((typo_start, len("typo")),), active_index=0)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=preview_position,
            suffix_text=suffix_text,
        )
    )
    diagnostic = _spelling_diagnostic(typo_start, len(text), "typo")
    surface.set_diagnostics((diagnostic,))
    preview_document = surface.active_projection_document()

    assert preview_document is not surface.projection_document()
    assert any(
        run.ghosted and run.display_text == suffix_text for run in preview_document.runs
    )
    assert surface.source_range_fragments(
        start=text.index("<lora"),
        end=text.index(">") + 1,
    )
    assert surface.source_range_fragments(
        start=text.index("{missing}"),
        end=text.index("{missing}") + len("{missing}"),
    )
    assert surface.source_range_fragments(
        start=text.index("(blue"),
        end=text.index(")") + 1,
    )
    assert surface.source_range_fragments(
        start=diagnostic.source_start,
        end=diagnostic.source_end,
    )


def test_phase3_reorder_entry_exposes_chip_identity_and_source_metadata(
    widgets: list[QWidget],
) -> None:
    """Entering reorder mode should expose stable chip source and separator data."""

    text = "alpha, <lora:demo:0.80>, (blue sky:1.20), {animal|2}"
    box = _show_phase3_editor(widgets, text=text)

    overlay = _enter_reorder_mode(box)
    chips = _overlay_chip_widgets(overlay)
    chips_by_index = {cast(int, chip.property("segmentIndex")): chip for chip in chips}
    segments_by_index = {
        index: cast(Any, chip)._segment  # noqa: SLF001
        for index, chip in chips_by_index.items()
    }

    assert sorted(chips_by_index) == [0, 1, 2, 3]
    assert [chips_by_index[index].property("segmentText") for index in range(4)] == [
        "alpha,",
        "<lora:demo:0.80>,",
        "(blue sky:1.20),",
        "{animal|2}",
    ]
    assert [segments_by_index[index].serialized_text for index in range(4)] == [
        "alpha",
        "<lora:demo:0.80>",
        "(blue sky:1.20)",
        "{animal|2}",
    ]
    assert [
        text[
            segments_by_index[index].selection_start : segments_by_index[
                index
            ].selection_end
        ]
        for index in range(4)
    ] == ["alpha", "<lora:demo:0.80>", "(blue sky:1.20)", "{animal|2}"]
    assert [segments_by_index[index].separator_text_after for index in range(4)] == [
        ", ",
        ", ",
        ", ",
        "",
    ]

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(ensure_qapp())


def test_phase3_reorder_escape_exits_without_source_mutation(
    widgets: list[QWidget],
) -> None:
    """Escape should cancel reorder mode and restore the original source."""

    text = "alpha, beta, gamma"
    box = _show_phase3_editor(widgets, text=text)
    overlay = _enter_reorder_mode(box)
    _drag_reorder_chip_to_global(
        _overlay_chip_by_segment_index(overlay, 1),
        global_target=_overlay_chip_by_segment_index(overlay, 0).mapToGlobal(
            QPoint(4, _overlay_chip_by_segment_index(overlay, 0).rect().center().y())
        ),
    )
    process_events(ensure_qapp(), cycles=20)
    assert cast(Any, overlay).ordered_chip_indices() == [1, 0, 2]
    assert box.toPlainText() == text

    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(ensure_qapp())

    assert box.toPlainText() == text
    assert _editor_reorder_preview_text(box) == ""
    assert getattr(box, "_segment_overlay") is None


def test_phase3_reorder_duplicate_tokens_preserve_identity_through_commit(
    widgets: list[QWidget],
) -> None:
    """Identical chip labels should retain distinct segment identities when reordered."""

    box = _show_phase3_editor(widgets, text="alpha, beta, alpha")
    overlay = _enter_reorder_mode(box)
    _drag_reorder_chip_to_global(
        _overlay_chip_by_segment_index(overlay, 2),
        global_target=_overlay_chip_by_segment_index(overlay, 1).mapToGlobal(
            QPoint(4, _overlay_chip_by_segment_index(overlay, 1).rect().center().y())
        ),
    )
    process_events(ensure_qapp(), cycles=20)

    assert cast(Any, overlay).ordered_chip_indices() == [0, 2, 1]
    assert box.toPlainText() == "alpha, beta, alpha"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(ensure_qapp())

    assert box.toPlainText() == "alpha, alpha, beta"
    box.undo()
    assert box.toPlainText() == "alpha, beta, alpha"
    box.redo()
    assert box.toPlainText() == "alpha, alpha, beta"


def test_phase3_reorder_preview_does_not_mutate_source_until_commit(
    widgets: list[QWidget],
) -> None:
    """Drag preview should remain separate from source text until Alt release."""

    box = _show_phase3_editor(widgets, text="alpha,\n\nbeta, gamma")
    overlay = _enter_reorder_mode(box)
    _drag_reorder_chip_to_global(
        _overlay_chip_by_segment_index(overlay, 2),
        global_target=_overlay_chip_by_segment_index(overlay, 0).mapToGlobal(
            QPoint(4, _overlay_chip_by_segment_index(overlay, 0).rect().center().y())
        ),
    )
    process_events(ensure_qapp(), cycles=20)

    assert cast(Any, overlay).ordered_chip_indices() == [2, 0, 1]
    assert box.toPlainText() == "alpha,\n\nbeta, gamma"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(ensure_qapp())

    assert box.toPlainText() == "gamma, alpha,\n\nbeta"


def _diagnostics_controller(
    editor: _FakeEditor,
    diagnostic: PromptDiagnostic,
    *,
    surface: _FakeSurface | None = None,
    spellcheck_provider: _FakeSpellcheckProvider | None = None,
    request_channel: _DeferredRequestChannel[PromptDiagnosticSnapshot]
    | _ImmediateRequestChannel[PromptDiagnosticSnapshot]
    | None = None,
) -> PromptDiagnosticsFeatureController:
    """Return a controller wired to deterministic diagnostic dependencies."""

    service = _StaticDiagnosticsService(editor.toPlainText(), diagnostic)
    feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.WILDCARD_SYNTAX,
                PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,
            )
        )
    )
    controller = PromptDiagnosticsFeatureController(
        host=editor,
        surface=surface or _FakeSurface(),
        feature_profile=feature_profile,
        wildcard_feature=PromptWildcardFeatureController(
            feature_profile=feature_profile,
            wildcard_catalog_gateway=cast(Any, EmptyPromptWildcardCatalogGateway()),
            request_channel=_ImmediateRequestChannel(),
        ),
        request_channel=request_channel or _ImmediateRequestChannel(),
        debouncer=_ImmediateDebouncer(),
    )
    controller.activate()
    cast(Any, controller)._service = service
    cast(Any, controller)._spellcheck_provider = spellcheck_provider
    return controller


class _StaticDiagnosticsService:
    """Return one fixed diagnostic snapshot."""

    def __init__(self, source_text: str, diagnostic: PromptDiagnostic) -> None:
        """Store fixed snapshot fields."""

        self._source_text = source_text
        self._diagnostic = diagnostic

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return the fixed diagnostic for the current text."""

        _ = text
        return PromptDiagnosticSnapshot(
            source_text=self._source_text,
            diagnostics=(self._diagnostic,),
        )


def _show_phase3_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int = 420,
) -> PromptEditor:
    """Create a visible prompt editor configured for Phase 3 behavior."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(width + 48, 360)
    layout = QVBoxLayout(host)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.EMPHASIS,
                PromptEditorFeature.WILDCARD_SYNTAX,
                PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
                PromptEditorFeature.LORA_SYNTAX,
                PromptEditorFeature.SEGMENT_REORDER,
                PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,
            )
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    layout.addWidget(box)
    box.setPlainText(text)
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    process_events(app)
    widgets.extend([host, box])
    return box


def _enter_reorder_mode(box: PromptEditor) -> QWidget:
    """Enter Alt reorder mode and return the live overlay."""

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(ensure_qapp())
    overlay = cast(QWidget | None, getattr(box, "_segment_overlay"))
    assert overlay is not None
    assert overlay.isVisible() is True
    return overlay


def _overlay_chip_widgets(overlay: QWidget) -> list[QWidget]:
    """Return visible reorder chips sorted by rendered position."""

    chips = [
        chip
        for chip in overlay.findChildren(QWidget, "segmentChip")
        if chip.isVisible()
    ]
    return sorted(
        chips,
        key=lambda chip: (
            chip.mapToGlobal(chip.rect().topLeft()).y(),
            chip.mapToGlobal(chip.rect().topLeft()).x(),
        ),
    )


def _overlay_chip_by_segment_index(overlay: QWidget, segment_index: int) -> QWidget:
    """Return one visible reorder chip by segment identity."""

    for chip in overlay.findChildren(QWidget, "segmentChip"):
        if chip.property("segmentIndex") == segment_index:
            return chip
    raise AssertionError(f"Missing segment chip for index {segment_index}.")


def _drag_reorder_chip_to_global(chip: QWidget, *, global_target: QPoint) -> None:
    """Drag one reorder chip to a target global point."""

    start = chip.rect().center()
    target = chip.mapFromGlobal(global_target)
    QTest.mousePress(chip, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(chip, target, 10)
    QTest.mouseRelease(chip, Qt.MouseButton.LeftButton, pos=target, delay=10)


def _editor_reorder_preview_text(box: PromptEditor) -> str:
    """Return the active reorder preview source text."""

    preview_document = cast(
        Any,
        surface_for(box),
    )._reorder_preview_projection.preview_document
    if preview_document is None:
        return ""
    return cast(str, preview_document.source_text)


def _spelling_diagnostic(
    source_start: int,
    source_end: int,
    word: str,
) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=source_start,
        source_end=source_end,
        message=f"Possible spelling issue: {word}",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def _duplicate_diagnostic(
    *,
    text: str,
    normalized_segment: str,
    first_start: int,
    first_end: int,
    duplicate_start: int,
    duplicate_end: int,
) -> PromptDiagnostic:
    """Return one deterministic duplicate-segment diagnostic."""

    _ = text
    return PromptDiagnostic(
        diagnostic_id=(
            f"duplicate:{duplicate_start}:{duplicate_end}:{normalized_segment}"
        ),
        kind=PromptDiagnosticKind.DUPLICATE_SEGMENT,
        severity=PromptDiagnosticSeverity.WARNING,
        source_start=duplicate_start,
        source_end=duplicate_end,
        message=f"Duplicate prompt segment: {normalized_segment}",
        payload=PromptDuplicateSegmentDiagnosticPayload(
            normalized_segment=normalized_segment,
            first_source_start=first_start,
            first_source_end=first_end,
            duplicate_source_start=duplicate_start,
            duplicate_source_end=duplicate_end,
        ),
    )
