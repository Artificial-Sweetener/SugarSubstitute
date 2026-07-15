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

"""Contract tests for prompt diagnostics presentation controller behavior."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from PySide6.QtGui import QTextCursor

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDiagnosticSnapshot,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptSourceNormalizationService,
    PromptSpellingDiagnosticPayload,
    PromptSpellingSuggestionSet,
    PromptWildcardDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptEditorCommand,
    build_diagnostic_action_command,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
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

TResult = TypeVar("TResult")


class _FakeService:
    """Provide deterministic diagnostics snapshots for controller tests."""

    def __init__(self, diagnostic: PromptDiagnostic) -> None:
        """Store the diagnostic returned for every snapshot."""

        self._diagnostic = diagnostic
        self.snapshot_calls: list[str] = []

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return one diagnostic for the supplied text."""

        self.snapshot_calls.append(text)
        return PromptDiagnosticSnapshot(
            source_text=text, diagnostics=(self._diagnostic,)
        )


class _FailingService:
    """Raise deterministic diagnostics failures for async logging tests."""

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Raise an error that includes source text which logs must not serialize."""

        raise RuntimeError(text)


class _FakeSurface:
    """Record projection diagnostic updates."""

    def __init__(self) -> None:
        """Initialize diagnostic call recording."""

        self.diagnostics: tuple[PromptDiagnostic, ...] = ()
        self.set_count = 0
        self.clear_count = 0

    def set_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Store diagnostics."""

        self.set_count += 1
        self.diagnostics = diagnostics

    def clear_diagnostics(self) -> None:
        """Record diagnostic clearing."""

        self.clear_count += 1
        self.diagnostics = ()


class _FakeCursor:
    """Record and apply source-range replacement cursor operations."""

    def __init__(self, editor: "_FakeEditor") -> None:
        """Initialize cursor call recording."""

        self._editor = editor
        self.positions: list[tuple[int, object | None]] = []
        self.inserted_text = ""
        self._position = 0
        self._anchor = 0

    def position(self) -> int:
        """Return the configured source cursor position."""

        return self._position

    def set_position_value(self, position: int) -> None:
        """Set the source cursor position returned to display policy."""

        self._position = position
        self._anchor = position

    def setPosition(self, position: int, mode: object | None = None) -> None:  # noqa: N802
        """Record one cursor movement."""

        self.positions.append((position, mode))
        if mode == QTextCursor.MoveMode.KeepAnchor:
            self._position = position
            return
        self._position = position
        self._anchor = position

    def insertText(self, text: str) -> None:  # noqa: N802
        """Record and apply replacement text."""

        self.inserted_text = text
        start = min(self._anchor, self._position)
        end = max(self._anchor, self._position)
        self._editor._text = (
            self._editor._text[:start] + text + self._editor._text[end:]
        )
        self._position = start + len(text)
        self._anchor = self._position


class _FakeEditor:
    """Provide the editor surface needed by diagnostics controller tests."""

    def __init__(self, text: str, *, cursor_position: int = 0) -> None:
        """Store current text and cursor."""

        self._text = text
        self.cursor = _FakeCursor(self)
        self.cursor.set_position_value(cursor_position)
        self.focused = False
        self.source_revision = 0
        self.read_count = 0

    def toPlainText(self) -> str:
        """Return current source text."""

        self.read_count += 1
        return self._text

    def set_text(self, text: str) -> None:
        """Mutate current source text for stale-result tests."""

        self._text = text
        self.source_revision += 1

    def set_cursor_position(self, position: int) -> None:
        """Mutate current source cursor position for visibility tests."""

        self.cursor.set_position_value(position)

    def textCursor(self) -> _FakeCursor:
        """Return the recording cursor."""

        return self.cursor

    def setTextCursor(self, cursor: object) -> None:
        """Accept the recording cursor."""

        _ = cursor

    def setFocus(self) -> None:
        """Record focus restoration."""

        self.focused = True

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current fake source identity for diagnostic commands."""

        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self._text),
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
            source_text=self._text,
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
        self._text = session.source_text
        self.source_revision = session.source_revision
        if result.cursor_state is not None:
            self.cursor.set_position_value(result.cursor_state.cursor_position)
        return result


class _ImmediateTaskHandle(Generic[TResult]):
    """Publish an already-completed prompt async outcome to callbacks."""

    def __init__(
        self,
        outcome: PromptAsyncTaskOutcome[TResult],
    ) -> None:
        """Store the completed outcome."""

        self._outcome = outcome
        self.cancelled_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the completed request identity."""

        return self._outcome.identity

    @property
    def is_finished(self) -> bool:
        """Return that immediate fake work is complete."""

        return True

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult]:
        """Return the stored outcome."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Invoke completion callbacks immediately."""

        _ = reason
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancelled_reasons.append(reason)


class _ImmediateRequestChannel(Generic[TResult]):
    """Run async requests immediately while proving the request-channel boundary."""

    def __init__(self) -> None:
        """Initialize request-channel call recording."""

        self.submitted_count = 0
        self.cancelled_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> _ImmediateTaskHandle[TResult]:
        """Execute one request and return an immediate handle."""

        self.submitted_count += 1
        try:
            result = request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            outcome = PromptAsyncTaskOutcome[TResult](
                identity=request.identity,
                context=request.context,
                error=error,
            )
        else:
            outcome = PromptAsyncTaskOutcome(
                identity=request.identity,
                context=request.context,
                result=result,
            )
        return _ImmediateTaskHandle(outcome)

    def cancel_pending(self, *, reason: str) -> None:
        """Record request-channel cancellation."""

        self.cancelled_reasons.append(reason)


class _Token:
    """Provide a never-cancelled token for immediate diagnostics tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _FakeDebouncer:
    """Record debounced callbacks for deterministic refresh tests."""

    def __init__(self) -> None:
        """Initialize debouncer state."""

        self.request_count = 0
        self.cancel_count = 0
        self._pending: Callable[[], None] | None = None

    @property
    def is_pending(self) -> bool:
        """Return whether a callback is queued."""

        return self._pending is not None

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Store the latest debounced callback."""

        _ = reason
        self.request_count += 1
        self._pending = callback

    def flush(self, *, reason: str) -> bool:
        """Run and clear the latest pending callback."""

        _ = reason
        callback = self._pending
        self._pending = None
        if callback is None:
            return False
        callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Clear the latest pending callback."""

        _ = reason
        callback = self._pending
        self._pending = None
        self.cancel_count += 1
        return callback is not None


class _EchoService:
    """Build diagnostics that identify the exact requested source text."""

    def __init__(self) -> None:
        """Initialize source-text request recording."""

        self.snapshot_calls: list[str] = []

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return one spelling diagnostic for the current text snapshot."""

        self.snapshot_calls.append(text)
        word = text.strip()
        return PromptDiagnosticSnapshot(
            source_text=text,
            diagnostics=(_spelling_diagnostic(0, len(word), word),),
        )


class _FakeSpellcheckService:
    """Provide prepared spelling suggestions for diagnostics menu tests."""

    def __init__(self) -> None:
        """Initialize suggestion and dictionary call recording."""

        self.suggestion_words: list[str] = []
        self.ignored_words: list[str] = []
        self.added_words: list[str] = []

    def suggestions_for_word(
        self,
        word: str,
        *,
        limit: int = 8,
    ) -> PromptSpellingSuggestionSet:
        """Return one deterministic spelling suggestion."""

        _ = limit
        self.suggestion_words.append(word)
        return PromptSpellingSuggestionSet(word=word, suggestions=("type",))

    def ignore_word_for_session(self, word: str) -> None:
        """Record ignored spelling words."""

        self.ignored_words.append(word)

    def add_word_to_dictionary(self, word: str) -> bool:
        """Record persistent dictionary additions."""

        self.added_words.append(word)
        return True

    def dictionary_add_supported(self) -> bool:
        """Return dictionary add support for menu actions."""

        return True


def _diagnostics_controller(
    editor: _FakeEditor,
    surface: _FakeSurface,
    service: object,
    *,
    request_channel: _ImmediateRequestChannel[PromptDiagnosticSnapshot] | None = None,
    debouncer: _FakeDebouncer | None = None,
    spellcheck_service: object | None = None,
) -> PromptDiagnosticsFeatureController:
    """Return an activated diagnostics feature with deterministic service behavior."""

    controller = PromptDiagnosticsFeatureController(
        host=editor,
        surface=surface,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(
                (
                    PromptEditorFeature.WILDCARD_SYNTAX,
                    PromptEditorFeature.SPELLCHECK,
                    PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,
                )
            )
        ),
        wildcard_feature=PromptWildcardFeatureController(
            feature_profile=PromptFeatureProfileController(
                PromptEditorFeatureProfile.enabled_profile(
                    (PromptEditorFeature.WILDCARD_SYNTAX,)
                )
            ),
            wildcard_catalog_gateway=cast(PromptWildcardCatalogGateway, object()),
            request_channel=_ImmediateRequestChannel(),
        ),
        spellcheck_service=cast(Any, spellcheck_service),
        request_channel=request_channel or _ImmediateRequestChannel(),
        debouncer=debouncer or _FakeDebouncer(),
    )
    controller.activate()
    cast(Any, controller)._service = service
    if debouncer is not None:
        debouncer.request_count = 0
        debouncer.cancel_count = 0
    return controller


def test_controller_dispatches_refresh_through_request_channel() -> None:
    """Diagnostics refresh should use the async channel before updating surface."""

    diagnostic = _spelling_diagnostic(0, 4, "typo")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("typo")
    request_channel: _ImmediateRequestChannel[PromptDiagnosticSnapshot] = (
        _ImmediateRequestChannel()
    )
    controller = _diagnostics_controller(
        editor,
        surface,
        service,
        request_channel=request_channel,
    )

    controller.refresh_now()

    assert request_channel.submitted_count == 1
    assert surface.diagnostics == (diagnostic,)
    assert controller.visible_diagnostic_at_source_position(2) == diagnostic


def test_controller_debounces_text_changes_to_latest_snapshot() -> None:
    """Text changes should schedule one diagnostics refresh for the newest source."""

    service = _EchoService()
    surface = _FakeSurface()
    editor = _FakeEditor("alpha ", cursor_position=0)
    request_channel: _ImmediateRequestChannel[PromptDiagnosticSnapshot] = (
        _ImmediateRequestChannel()
    )
    debouncer = _FakeDebouncer()
    controller = _diagnostics_controller(
        editor,
        surface,
        service,
        request_channel=request_channel,
        debouncer=debouncer,
    )

    controller.handle_text_changed()
    editor.set_text("beta ")
    controller.handle_text_changed()
    assert debouncer.request_count == 2
    assert debouncer.cancel_count == 0
    assert service.snapshot_calls == []

    assert debouncer.flush(reason="test") is True

    assert service.snapshot_calls == ["beta "]
    assert request_channel.submitted_count == 1
    assert debouncer.cancel_count == 1
    assert [diagnostic.message for diagnostic in surface.diagnostics] == [
        "Possible spelling issue: beta"
    ]


def test_controller_failure_publishes_unavailable_snapshot_with_safe_log(
    caplog: Any,
) -> None:
    """Diagnostics failures should clear visible state without logging source text."""

    surface = _FakeSurface()
    editor = _FakeEditor("secret prompt text", cursor_position=0)
    controller = _diagnostics_controller(editor, surface, _FailingService())
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.prompt_editor.features.diagnostics",
    )

    controller.refresh_now()

    assert surface.diagnostics == ()
    assert surface.clear_count == 1
    assert controller.snapshot.unavailable_reason == "RuntimeError"
    assert controller.snapshot.identity.stale is True
    assert "prompt_diagnostics.refresh.failed" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "secret prompt text" not in caplog.text


def test_controller_filters_active_word_before_updating_surface() -> None:
    """Controller should keep full snapshot but display only policy-visible diagnostics."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("beut", cursor_position=4)
    controller = _diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert service.snapshot_calls == ["beut"]
    assert not surface.diagnostics
    assert surface.clear_count == 1
    assert controller.visible_diagnostic_at_source_position(2) is None


def test_controller_refreshes_visible_diagnostics_on_cursor_move_without_backend_refresh() -> (
    None
):
    """Caret movement should update visibility from the cached snapshot."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("beut", cursor_position=4)
    controller = _diagnostics_controller(editor, surface, service)
    controller.refresh_now()
    assert not surface.diagnostics

    editor.set_cursor_position(0)
    controller.refresh_visible_diagnostics()

    assert service.snapshot_calls == ["beut"]
    assert surface.diagnostics == (diagnostic,)


def test_controller_skips_unchanged_visible_diagnostic_surface_update() -> None:
    """Repeated visibility refreshes should not repush unchanged diagnostics."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("beut", cursor_position=0)
    controller = _diagnostics_controller(editor, surface, service)
    controller.refresh_now()
    assert surface.diagnostics == (diagnostic,)
    assert surface.set_count == 1

    controller.refresh_visible_diagnostics()

    assert surface.diagnostics == (diagnostic,)
    assert surface.set_count == 1


def test_controller_context_lookup_uses_full_snapshot_for_active_word() -> None:
    """Context lookup should include hidden active-word diagnostics for actions."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("beut", cursor_position=4)
    controller = _diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert not surface.diagnostics
    assert service.snapshot_calls == ["beut"]
    assert controller.context_diagnostic_at_source_position(2) == diagnostic
    assert controller.context_diagnostic_at_source_position(4) is None


def test_controller_prepares_spelling_menu_actions_before_menu_read() -> None:
    """Prepared diagnostic menu reads should not load spelling suggestions."""

    diagnostic = _spelling_diagnostic(4, 8, "typo")
    spellcheck = _FakeSpellcheckService()
    editor = _FakeEditor("one typo", cursor_position=0)
    controller = _diagnostics_controller(
        editor,
        _FakeSurface(),
        _FakeService(diagnostic),
        spellcheck_service=spellcheck,
    )

    controller.refresh_now()
    assert spellcheck.suggestion_words == ["typo"]
    spellcheck.suggestion_words.clear()
    editor.read_count = 0

    snapshot = controller.prepared_menu_actions_for_source_position(5)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id == diagnostic.diagnostic_id
    assert [action.label for action in snapshot.actions] == [
        "type",
        "Ignore spelling",
        "Add to dictionary",
    ]
    assert spellcheck.suggestion_words == []
    assert editor.read_count == 0


def test_controller_prepared_menu_actions_include_hidden_active_word() -> None:
    """Menu action snapshots should include active-word diagnostics hidden in paint."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    controller = _diagnostics_controller(
        _FakeEditor("beut", cursor_position=4),
        _FakeSurface(),
        _FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.prepared_menu_actions_for_source_position(2)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id == diagnostic.diagnostic_id
    assert snapshot.actions


def test_controller_prepared_menu_actions_report_no_diagnostic_without_derivation() -> (
    None
):
    """Positions outside diagnostics should return ready empty action snapshots."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    editor = _FakeEditor("beut", cursor_position=0)
    controller = _diagnostics_controller(
        editor,
        _FakeSurface(),
        _FakeService(diagnostic),
    )
    controller.refresh_now()
    editor.read_count = 0

    snapshot = controller.prepared_menu_actions_for_source_position(4)

    assert snapshot.ready is True
    assert snapshot.diagnostic_id is None
    assert snapshot.actions == ()
    assert editor.read_count == 0


def test_controller_prepared_menu_actions_report_stale_source_identity() -> None:
    """Prepared diagnostic menu reads should fail closed on stale source identity."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    editor = _FakeEditor("beut", cursor_position=0)
    controller = _diagnostics_controller(
        editor,
        _FakeSurface(),
        _FakeService(diagnostic),
    )
    controller.refresh_now()
    editor.set_text("beautiful")
    editor.read_count = 0

    snapshot = controller.prepared_menu_actions_for_source_position(2)

    assert snapshot.ready is False
    assert snapshot.stale is True
    assert snapshot.actions == ()
    assert snapshot.unavailable_reason == "stale_diagnostics_snapshot"
    assert editor.read_count == 0


def test_controller_context_lookup_ignores_stale_snapshot_ranges() -> None:
    """Context lookup should not offer actions from stale source text snapshots."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")
    editor = _FakeEditor("beut", cursor_position=0)
    controller = _diagnostics_controller(
        editor,
        _FakeSurface(),
        _FakeService(diagnostic),
    )
    controller.refresh_now()

    editor.set_text("beautiful")

    assert controller.context_diagnostic_at_source_position(2) is None


def test_controller_replace_spelling_diagnostic_routes_command() -> None:
    """Suggestion replacement should route through the diagnostic command boundary."""

    diagnostic = _spelling_diagnostic(4, 8, "typo")
    editor = _FakeEditor("one typo")
    controller = _diagnostics_controller(
        editor,
        _FakeSurface(),
        _FakeService(diagnostic),
    )

    controller.replace_spelling_diagnostic(diagnostic, "type")

    assert editor.toPlainText() == "one type"
    assert editor.focused is True


def test_controller_filters_active_wildcard_diagnostic_while_editing() -> None:
    """Missing wildcard diagnostics should stay hidden while the placeholder is active."""

    diagnostic = _wildcard_diagnostic(0, 9, "missing")
    service = _FakeService(diagnostic)
    surface = _FakeSurface()
    editor = _FakeEditor("{missing}", cursor_position=9)
    controller = _diagnostics_controller(editor, surface, service)

    controller.refresh_now()

    assert not surface.diagnostics
    assert controller.context_diagnostic_at_source_position(2) == diagnostic

    editor.set_text("{missing}, suffix")
    service._diagnostic = _wildcard_diagnostic(0, 9, "missing")  # noqa: SLF001
    controller.refresh_now()

    assert surface.diagnostics == (diagnostic,)


def test_wildcard_diagnostics_add_context_menu_explainer() -> None:
    """Wildcard diagnostics should add one disabled context-menu explanation."""

    diagnostic = _wildcard_diagnostic(0, 9, "missing")
    controller = _diagnostics_controller(
        _FakeEditor("{missing}"),
        _FakeSurface(),
        _FakeService(diagnostic),
    )

    actions = controller.actions_for_diagnostic(diagnostic)

    assert len(actions) == 1
    assert actions[0].label == "Wildcard not found"
    assert actions[0].callback is None
    assert actions[0].enabled is False


def test_controller_prepares_wildcard_menu_action_explainer() -> None:
    """Wildcard diagnostic explainers should be prepared before menu open."""

    diagnostic = _wildcard_diagnostic(0, 9, "missing")
    controller = _diagnostics_controller(
        _FakeEditor("{missing}"),
        _FakeSurface(),
        _FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.prepared_menu_actions_for_source_position(2)

    assert len(snapshot.actions) == 1
    assert snapshot.actions[0].label == "Wildcard not found"
    assert snapshot.actions[0].callback is None
    assert snapshot.actions[0].enabled is False


def test_controller_prepares_duplicate_menu_actions() -> None:
    """Duplicate diagnostics should prepare their context actions before menu open."""

    diagnostic = _duplicate_diagnostic(
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )
    controller = _diagnostics_controller(
        _FakeEditor("alpha, beta, beta"),
        _FakeSurface(),
        _FakeService(diagnostic),
    )

    controller.refresh_now()
    snapshot = controller.prepared_menu_actions_for_source_position(14)

    assert [action.label for action in snapshot.actions] == [
        "Remove duplicate",
        "Emphasize first",
        "Ignore duplicate",
    ]


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


def _wildcard_diagnostic(
    source_start: int,
    source_end: int,
    identifier: str,
) -> PromptDiagnostic:
    """Return one deterministic missing-wildcard diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"wildcard:{source_start}:{source_end}:simple:{identifier}:",
        kind=PromptDiagnosticKind.WILDCARD,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=source_start,
        source_end=source_end,
        message=f"Missing wildcard: {identifier}",
        payload=PromptWildcardDiagnosticPayload(
            identifier=identifier,
            wildcard_form="simple",
        ),
    )


def _duplicate_diagnostic(
    *,
    normalized_segment: str,
    first_start: int,
    first_end: int,
    duplicate_start: int,
    duplicate_end: int,
) -> PromptDiagnostic:
    """Return one deterministic duplicate-segment diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"duplicate:{duplicate_start}:{duplicate_end}:{normalized_segment}",
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
