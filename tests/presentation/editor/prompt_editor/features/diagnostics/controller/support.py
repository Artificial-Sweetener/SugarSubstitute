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

"""Provide deterministic diagnostics-controller test support."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from PySide6.QtGui import QTextCursor

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDiagnosticSnapshot,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptSpellingDiagnosticPayload,
    PromptWildcardDiagnosticPayload,
)
from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    PromptConditioningMode,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptEditorCommand,
)
from substitute.presentation.editor.prompt_editor.commands.diagnostic_commands import (
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
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
    PromptWildcardDiagnosticsPresentation,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.core.editing.transactions import (
    PromptUndoSnapshot,
)
from tests.support.prompt_editor.command_support import execute_prompt_command

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

    def prompt_command_source_identity(self) -> PromptSourceIdentity:
        """Return the current fake source identity for diagnostic commands."""

        return PromptSourceIdentity(
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
            execute_prompt_command(session, command),
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


class _DeferredTaskHandle(Generic[TResult]):
    """Hold one request outcome until a test explicitly completes it."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store the request and initialize its completion callback list."""

        self.request = request
        self._callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Queue one callback until explicit completion."""

        _ = reason
        self._callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Accept cancellation without suppressing a deliberately late outcome."""

        _ = reason

    def complete(self) -> None:
        """Execute and publish this request as a late asynchronous outcome."""

        result = self.request.work(_Token())
        outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
        )
        for callback in self._callbacks:
            callback(outcome)


class _DeferredRequestChannel(Generic[TResult]):
    """Capture latest-wins requests for explicit out-of-order completion."""

    def __init__(self) -> None:
        """Initialize an empty handle list and cancellation log."""

        self.handles: list[_DeferredTaskHandle[TResult]] = []
        self.cancelled_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> _DeferredTaskHandle[TResult]:
        """Capture one request without executing it."""

        handle = _DeferredTaskHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record cancellation while allowing late-result guard verification."""

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


def _diagnostics_controller(
    editor: _FakeEditor,
    surface: _FakeSurface,
    service: object,
    *,
    request_channel: Any | None = None,
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
        wildcard_feature=PromptWildcardDiagnosticsPresentation(
            feature_profile=PromptFeatureProfileController(
                PromptEditorFeatureProfile.enabled_profile(
                    (PromptEditorFeature.WILDCARD_SYNTAX,)
                )
            ),
            wildcard_catalog_gateway=cast(PromptWildcardCatalogGateway, object()),
        ),
        spellcheck_service=cast(Any, spellcheck_service),
        diagnostics_service_factory=lambda _providers: cast(Any, service),
        request_channel=request_channel or _ImmediateRequestChannel(),
        debouncer=debouncer or _FakeDebouncer(),
    )
    controller.activate()
    if debouncer is not None:
        debouncer.request_count = 0
        debouncer.cancel_count = 0
    return controller


def _conditioning_context(
    mode: PromptConditioningMode,
    *,
    topology_key: tuple[object, ...] = (),
) -> PromptConditioningContext:
    """Return one stable diagnostics conditioning context."""

    return PromptConditioningContext(
        mode=mode,
        endpoint=PromptEndpoint(
            cube_alias="cube",
            role=PromptRole.POSITIVE,
            node_name="prompt",
            field_key="value",
        ),
        topology_key=topology_key,
    )


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
