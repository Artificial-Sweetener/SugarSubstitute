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

"""Own prompt diagnostics refresh, snapshots, and prepared actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticDisplayPolicy,
    PromptDiagnosticKind,
    PromptDiagnosticProvider,
    PromptDiagnosticSnapshot as ApplicationPromptDiagnosticSnapshot,
    PromptDiagnosticsService,
    PromptDuplicateSegmentDiagnosticProvider,
    PromptSpellcheckDiagnosticProvider,
    PromptSpellcheckService,
    PromptSpellingDiagnosticPayload,
    PromptSpellingSuggestionSet,
)
from substitute.shared.logging.logger import get_logger, log_timing

from ..async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorDebouncer,
    PromptEditorMainThreadDispatcher,
    PromptEditorRequestChannel,
    PromptFreshnessField,
    PromptStaleResultGuard,
    QtPromptEditorDebouncer,
    QtPromptEditorMainThreadDispatcher,
    log_prompt_async_warning,
    prompt_async_outcome_log_fields,
)
from ..commands import (
    PromptCommandSourceIdentity,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptDuplicateEmphasisDiagnosticAction,
    PromptDuplicateIgnoreDiagnosticAction,
    PromptDuplicateRemovalDiagnosticAction,
    PromptSpellingDictionaryAddDiagnosticAction,
    PromptSpellingIgnoreDiagnosticAction,
    PromptSpellingReplacementDiagnosticAction,
)
from ..commands import PromptFeatureSnapshotIdentity
from .feature_profile_controller import PromptFeatureProfileController
from .diagnostic_menu_actions import (
    PromptContextMenuAction,
    PromptDiagnosticMenuActionEntry,
    PromptDiagnosticMenuActionSnapshot,
    actions_for_prepared_diagnostic,
    diagnostic_menu_action_snapshot_for_position,
    prepare_diagnostic_menu_action_entries,
)
from .wildcard_controller import PromptWildcardFeatureController

_LOGGER = get_logger("presentation.editor.prompt_editor.features.diagnostics")
_VISIBLE_POLICY_ACTIVE_WORD = "hide_active_word"

type _VisibleDiagnosticsIdentity = tuple[
    tuple[str, PromptDiagnosticKind, int, int, str],
    ...,
]


class PromptDiagnosticsCursor(Protocol):
    """Describe cursor reads used by diagnostic display policy."""

    def position(self) -> int:
        """Return the current source-backed cursor position."""


class PromptDiagnosticsHost(Protocol):
    """Describe prompt-editor hooks needed by diagnostic feature ownership."""

    def toPlainText(self) -> str:
        """Return the current prompt source text."""

    def textCursor(self) -> PromptDiagnosticsCursor:
        """Return a source-backed cursor for visibility policy."""

    def setFocus(self) -> None:
        """Focus the prompt editor after accepted diagnostic actions."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity for prepared diagnostic commands."""

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one prepared diagnostic action through commands."""


class PromptDiagnosticsSurface(Protocol):
    """Describe the projection surface diagnostics API."""

    def set_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Replace painted diagnostics."""

    def clear_diagnostics(self) -> None:
        """Clear painted diagnostics."""


class PromptDiagnosticsSignalHost(Protocol):
    """Describe prompt-editor signals used by diagnostics refresh ownership."""

    textChanged: Any
    cursorPositionChanged: Any


@dataclass(frozen=True, slots=True)
class PromptDiagnosticsSnapshot:
    """Publish prepared diagnostic state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    diagnostics: tuple[PromptDiagnostic, ...]
    visible_diagnostics: tuple[PromptDiagnostic, ...]
    action_ready: bool
    active_word_policy: str
    unavailable_reason: str | None = None


class PromptDiagnosticsFeatureController:
    """Coordinate prompt diagnostics refresh and action presentation."""

    _DEBOUNCE_MS = 280

    def __init__(
        self,
        *,
        host: PromptDiagnosticsHost,
        surface: PromptDiagnosticsSurface,
        feature_profile: PromptFeatureProfileController,
        wildcard_feature: PromptWildcardFeatureController,
        spellcheck_service: PromptSpellcheckService | None = None,
        parent: object | None = None,
        bind_signals: Callable[
            ["PromptDiagnosticsFeatureController"],
            None,
        ]
        | None = None,
        debouncer: PromptEditorDebouncer | None = None,
        request_channel: PromptEditorRequestChannel[ApplicationPromptDiagnosticSnapshot]
        | None = None,
        main_thread_dispatcher: PromptEditorMainThreadDispatcher | None = None,
        display_policy: PromptDiagnosticDisplayPolicy | None = None,
        debounce_ms: int = _DEBOUNCE_MS,
    ) -> None:
        """Store diagnostics collaborators without activating providers yet."""

        self._host = host
        self._surface = surface
        self._feature_profile = feature_profile
        self._wildcard_feature = wildcard_feature
        self._spellcheck_service = spellcheck_service
        self._bind_signals = bind_signals
        self._display_policy = display_policy or PromptDiagnosticDisplayPolicy()
        self._snapshot: ApplicationPromptDiagnosticSnapshot | None = None
        self._service = PromptDiagnosticsService(())
        self._published_snapshot = PromptDiagnosticsSnapshot(
            identity=self._snapshot_identity(stale=False),
            diagnostics=(),
            visible_diagnostics=(),
            action_ready=False,
            active_word_policy=_VISIBLE_POLICY_ACTIVE_WORD,
        )
        self._visible_diagnostics: tuple[PromptDiagnostic, ...] = ()
        self._visible_diagnostics_identity: _VisibleDiagnosticsIdentity | None = None
        self._ignored_diagnostic_ids: set[str] = set()
        self._prepared_spelling_suggestions: dict[str, PromptSpellingSuggestionSet] = {}
        self._prepared_menu_action_entries: tuple[
            PromptDiagnosticMenuActionEntry,
            ...,
        ] = ()
        self._request_id = 0
        self._activated = False
        self._activation_pending = False
        self._spellcheck_provider: PromptSpellcheckDiagnosticProvider | None = None
        dispatcher = main_thread_dispatcher or QtPromptEditorMainThreadDispatcher(
            cast(Any, parent)
        )
        self._activation_dispatcher = dispatcher
        self._debouncer = debouncer or QtPromptEditorDebouncer(
            interval_ms=debounce_ms,
            parent=cast(Any, parent),
        )
        if request_channel is None:
            raise TypeError("request_channel is required for prompt diagnostics.")
        self._request_channel = request_channel
        self._stale_guard = PromptStaleResultGuard()

    @property
    def is_active(self) -> bool:
        """Return whether diagnostics providers have been activated."""

        return self._activated

    @property
    def activation_pending(self) -> bool:
        """Return whether deferred activation is already queued."""

        return self._activation_pending

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return the last prepared diagnostics snapshot."""

        return self._published_snapshot

    def can_activate(self) -> bool:
        """Return whether any prompt diagnostics provider can be enabled."""

        spellcheck_available = (
            self._spellcheck_service is not None
            and self._feature_profile.spellcheck_enabled
        )
        wildcard_available = self._wildcard_feature.diagnostic_provider_ready()
        duplicate_available = (
            self._feature_profile.duplicate_segment_diagnostics_enabled
        )
        return spellcheck_available or wildcard_available or duplicate_available

    def schedule_activation(self) -> None:
        """Schedule optional diagnostics activation after construction settles."""

        if self._activation_pending or self._activated or not self.can_activate():
            return
        self._activation_pending = True
        self._activation_dispatcher.publish(
            self.activate,
            reason="diagnostics_activation",
        )

    def activate(self) -> None:
        """Create optional providers and queue an initial diagnostics refresh."""

        self._activation_pending = False
        if self._activated or not self.can_activate():
            return
        started_at = perf_counter()
        providers: list[PromptDiagnosticProvider] = []
        self._spellcheck_provider = None
        if (
            self._spellcheck_service is not None
            and self._feature_profile.spellcheck_enabled
        ):
            self._spellcheck_provider = PromptSpellcheckDiagnosticProvider(
                self._spellcheck_service
            )
            providers.append(self._spellcheck_provider)
        providers.extend(self._wildcard_feature.diagnostic_providers())
        if self._feature_profile.duplicate_segment_diagnostics_enabled:
            providers.append(PromptDuplicateSegmentDiagnosticProvider())
        self._service = PromptDiagnosticsService(tuple(providers))
        if self._bind_signals is not None:
            self._bind_signals(self)
        self._activated = True
        self.handle_text_changed()
        log_timing(
            _LOGGER,
            "Initialized deferred prompt editor diagnostics services",
            started_at=started_at,
            level="debug",
        )

    def handle_text_changed(self) -> None:
        """Schedule a diagnostics refresh for the current prompt text."""

        if not self._activated:
            return
        self._debouncer.request(
            self.refresh_now,
            reason="diagnostics_text_changed",
        )

    def refresh_now(self) -> None:
        """Refresh diagnostics for the current prompt text."""

        if not self._activated:
            return
        self._debouncer.cancel(reason="diagnostics_refresh_now")
        source_text = self._host.toPlainText()
        if not source_text.strip():
            self._request_channel.cancel_pending(reason="diagnostics_empty_source")
            self._snapshot = ApplicationPromptDiagnosticSnapshot(
                source_text=source_text,
                diagnostics=(),
            )
            self._visible_diagnostics = ()
            self._prepared_spelling_suggestions.clear()
            self._prepared_menu_action_entries = ()
            self._set_visible_diagnostics(())
            self._publish_snapshot(stale=False)
            return

        self._request_id += 1
        source_identity = self._host.prompt_command_source_identity()
        request_identity = self._async_identity(
            request_id=self._request_id,
            source_text=source_text,
            source_identity=source_identity,
        )
        service = self._service
        request = PromptAsyncRequest(
            identity=request_identity,
            context=PromptAsyncRequestContext(
                operation="diagnostics_refresh",
                reason="text_changed",
                safe_fields=(("source_length", len(source_text)),),
            ),
            work=lambda _token: service.snapshot_for_text(source_text),
        )
        handle = self._request_channel.submit_latest(request)
        handle.add_done_callback(
            self._handle_async_outcome,
            reason="diagnostics_refresh_completed",
        )

    def visible_diagnostic_at_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnostic | None:
        """Return the painted diagnostic under one raw prompt source position."""

        return _diagnostic_at_source_position(
            self._visible_diagnostics, source_position
        )

    def context_diagnostic_at_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnostic | None:
        """Return the actionable diagnostic under one raw prompt source position."""

        snapshot = self._snapshot
        if snapshot is None:
            return None
        if snapshot.source_text != self._host.toPlainText():
            return None
        return _diagnostic_at_source_position(
            self._active_diagnostics(snapshot),
            source_position,
        )

    def actions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic | None,
    ) -> tuple[PromptContextMenuAction, ...]:
        """Return context-menu actions for the supplied diagnostic."""

        if diagnostic is None:
            return ()
        source_identity = self.source_identity_for_diagnostic_action()
        return actions_for_prepared_diagnostic(
            diagnostic=diagnostic,
            source_identity=source_identity,
            spelling_suggestions=self._prepared_spelling_suggestions,
            dictionary_add_supported=self.dictionary_add_supported(),
            wildcard_feature=self._wildcard_feature,
            replace_spelling_diagnostic=self.replace_spelling_diagnostic,
            ignore_spelling_diagnostic_for_session=(
                self.ignore_spelling_diagnostic_for_session
            ),
            add_spelling_diagnostic_to_dictionary=(
                self.add_spelling_diagnostic_to_dictionary
            ),
            remove_duplicate_diagnostic=self.remove_duplicate_diagnostic,
            emphasize_first_duplicate_diagnostic=(
                self.emphasize_first_duplicate_diagnostic
            ),
            ignore_duplicate_diagnostic=self.ignore_duplicate_diagnostic,
        )

    def prepared_menu_actions_for_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnosticMenuActionSnapshot:
        """Return prepared diagnostic actions without menu-open derivation."""

        snapshot = self._published_snapshot
        return diagnostic_menu_action_snapshot_for_position(
            source_position=source_position,
            entries=self._prepared_menu_action_entries,
            active_diagnostic_ids=frozenset(
                diagnostic.diagnostic_id for diagnostic in snapshot.diagnostics
            ),
            base_identity=snapshot.identity,
            current_source_identity=self._host.prompt_command_source_identity(),
            unavailable_reason=snapshot.unavailable_reason,
        )

    def suggestions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
    ) -> PromptSpellingSuggestionSet | None:
        """Return prepared spelling suggestions for a spelling diagnostic."""

        if diagnostic.kind is not PromptDiagnosticKind.SPELLING:
            return None
        return self._prepared_spelling_suggestions.get(diagnostic.diagnostic_id)

    def source_identity_for_diagnostic_action(
        self,
    ) -> PromptCommandSourceIdentity | None:
        """Return the current source identity for menu-built diagnostic actions."""

        return self._host.prompt_command_source_identity()

    def replace_spelling_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        replacement: str,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Replace one spelling diagnostic range in the prompt editor."""

        result = self._host.execute_diagnostic_action(
            PromptSpellingReplacementDiagnosticAction(
                diagnostic=diagnostic,
                replacement_text=replacement,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def ignore_spelling_diagnostic_for_session(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Ignore one spelling diagnostic word for the current session."""

        provider = self._spellcheck_provider
        if provider is None:
            return
        result = self._host.execute_diagnostic_action(
            PromptSpellingIgnoreDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status == "rejected" or result.spelling_word is None:
            return
        provider.ignore_word_for_session(result.spelling_word)
        self.refresh_now()

    def add_spelling_diagnostic_to_dictionary(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Persist one spelling diagnostic word when supported by the backend."""

        provider = self._spellcheck_provider
        if provider is None:
            return
        result = self._host.execute_diagnostic_action(
            PromptSpellingDictionaryAddDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status == "rejected" or result.spelling_word is None:
            return
        if provider.add_word_to_dictionary(result.spelling_word):
            self.refresh_now()

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""

        provider = self._spellcheck_provider
        return False if provider is None else provider.dictionary_add_supported()

    def remove_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Remove one duplicate-segment diagnostic occurrence from the prompt."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateRemovalDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def emphasize_first_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Remove the duplicate occurrence and emphasize the first occurrence."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateEmphasisDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def ignore_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Suppress one duplicate diagnostic for the current editor session."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateIgnoreDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._diagnostic_action_identity(source_identity),
            )
        )
        if result.status == "rejected" or result.ignored_diagnostic_id is None:
            return
        self._ignored_diagnostic_ids.add(result.ignored_diagnostic_id)
        self.refresh_visible_diagnostics()

    def clear(self) -> None:
        """Clear current diagnostics."""

        self._snapshot = None
        self._visible_diagnostics = ()
        self._prepared_spelling_suggestions.clear()
        self._prepared_menu_action_entries = ()
        self._request_channel.cancel_pending(reason="diagnostics_clear")
        self._set_visible_diagnostics(())
        self._publish_snapshot(stale=False)

    def refresh_visible_diagnostics(self) -> None:
        """Refresh displayed diagnostics from the cached snapshot without backend work."""

        self._refresh_visible_diagnostics_measured()

    def _refresh_visible_diagnostics_measured(self) -> None:
        """Refresh displayed diagnostics after the public method starts probe timing."""

        snapshot = self._snapshot
        if snapshot is None:
            self._visible_diagnostics = ()
            self._set_visible_diagnostics(())
            self._publish_snapshot(stale=False)
            return
        visible_snapshot = ApplicationPromptDiagnosticSnapshot(
            source_text=snapshot.source_text,
            diagnostics=self._active_diagnostics(snapshot),
            unavailable_reason=snapshot.unavailable_reason,
        )
        cursor_position = self._host.textCursor().position()
        self._visible_diagnostics = self._display_policy.visible_diagnostics(
            snapshot=visible_snapshot,
            cursor_position=cursor_position,
        )
        self._set_visible_diagnostics(self._visible_diagnostics)
        self._publish_snapshot(stale=False)

    def _set_visible_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Push visible diagnostics only when their material identity changes."""

        next_identity = _visible_diagnostics_identity(diagnostics)
        if next_identity == self._visible_diagnostics_identity:
            return
        self._visible_diagnostics_identity = next_identity
        if diagnostics:
            self._surface.set_diagnostics(diagnostics)
            return
        self._surface.clear_diagnostics()

    def _active_diagnostics(
        self,
        snapshot: ApplicationPromptDiagnosticSnapshot,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return snapshot diagnostics after session-scoped ignores."""

        return tuple(
            diagnostic
            for diagnostic in snapshot.diagnostics
            if diagnostic.diagnostic_id not in self._ignored_diagnostic_ids
        )

    def _diagnostic_action_identity(
        self,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> PromptCommandSourceIdentity | None:
        """Return the supplied or current source identity for a diagnostic action."""

        if source_identity is not None:
            return source_identity
        return self._host.prompt_command_source_identity()

    def _handle_async_outcome(
        self,
        outcome: PromptAsyncTaskOutcome[ApplicationPromptDiagnosticSnapshot],
    ) -> None:
        """Apply the newest async result and ignore stale prompt snapshots."""

        if outcome.cancelled:
            return
        if outcome.error is not None:
            log_prompt_async_warning(
                _LOGGER,
                "prompt_diagnostics.refresh.failed",
                error=outcome.error,
                **prompt_async_outcome_log_fields(outcome),
            )
            self._publish_failure_snapshot(outcome.error)
            return
        result = outcome.result
        if result is None:
            return
        current_identity = self._async_identity(
            request_id=self._request_id,
            source_text=self._host.toPlainText(),
            source_identity=self._host.prompt_command_source_identity(),
        )
        required_fields: list[PromptFreshnessField] = [
            "request_id",
            "feature_profile_id",
        ]
        if current_identity.source_revision is not None:
            required_fields.append("source_revision")
        freshness = self._stale_guard.validate(
            result_identity=outcome.identity,
            current_identity=current_identity,
            required_fields=required_fields,
        )
        if not freshness.is_fresh:
            return
        if result.source_text != self._host.toPlainText():
            return
        self._snapshot = result
        self._prepare_context_action_state(
            result,
            source_identity=self._host.prompt_command_source_identity(),
        )
        self.refresh_visible_diagnostics()

    def _prepare_context_action_state(
        self,
        snapshot: ApplicationPromptDiagnosticSnapshot,
        *,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> None:
        """Prepare diagnostic menu action data outside context-menu opening."""

        self._prepared_spelling_suggestions.clear()
        self._prepared_menu_action_entries = ()
        provider = self._spellcheck_provider
        for diagnostic in self._active_diagnostics(snapshot):
            if (
                provider is not None
                and diagnostic.kind is PromptDiagnosticKind.SPELLING
            ):
                payload = diagnostic.payload
                if isinstance(payload, PromptSpellingDiagnosticPayload):
                    self._prepared_spelling_suggestions[diagnostic.diagnostic_id] = (
                        cast(
                            PromptSpellingSuggestionSet,
                            provider.suggestions_for_word(payload.word),
                        )
                    )
        self._prepared_menu_action_entries = tuple(
            prepare_diagnostic_menu_action_entries(
                diagnostics=self._active_diagnostics(snapshot),
                source_identity=source_identity,
                base_identity=self._snapshot_identity(stale=False),
                spelling_suggestions=self._prepared_spelling_suggestions,
                dictionary_add_supported=self.dictionary_add_supported(),
                wildcard_feature=self._wildcard_feature,
                replace_spelling_diagnostic=self.replace_spelling_diagnostic,
                ignore_spelling_diagnostic_for_session=(
                    self.ignore_spelling_diagnostic_for_session
                ),
                add_spelling_diagnostic_to_dictionary=(
                    self.add_spelling_diagnostic_to_dictionary
                ),
                remove_duplicate_diagnostic=self.remove_duplicate_diagnostic,
                emphasize_first_duplicate_diagnostic=(
                    self.emphasize_first_duplicate_diagnostic
                ),
                ignore_duplicate_diagnostic=self.ignore_duplicate_diagnostic,
            )
        )

    def _publish_failure_snapshot(self, error: BaseException) -> None:
        """Publish a prompt-safe unavailable diagnostics snapshot."""

        self._snapshot = ApplicationPromptDiagnosticSnapshot(
            source_text=self._host.toPlainText(),
            diagnostics=(),
            unavailable_reason=type(error).__name__,
        )
        self._visible_diagnostics = ()
        self._prepared_spelling_suggestions.clear()
        self._prepared_menu_action_entries = ()
        self._set_visible_diagnostics(())
        self._publish_snapshot(stale=True)

    def _publish_snapshot(self, *, stale: bool) -> None:
        """Publish prepared diagnostics state for foreground consumers."""

        snapshot = self._snapshot
        diagnostics = () if snapshot is None else self._active_diagnostics(snapshot)
        unavailable_reason = None if snapshot is None else snapshot.unavailable_reason
        self._published_snapshot = PromptDiagnosticsSnapshot(
            identity=self._snapshot_identity(stale=stale),
            diagnostics=diagnostics,
            visible_diagnostics=self._visible_diagnostics,
            action_ready=bool(diagnostics),
            active_word_policy=_VISIBLE_POLICY_ACTIVE_WORD,
            unavailable_reason=unavailable_reason,
        )

    def _snapshot_identity(self, *, stale: bool) -> PromptFeatureSnapshotIdentity:
        """Return feature snapshot identity for the current source state."""

        source_identity = self._host.prompt_command_source_identity()
        source_revision = (
            None if source_identity is None else source_identity.source_revision
        )
        return PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
        )

    def _async_identity(
        self,
        *,
        request_id: int,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
    ) -> PromptAsyncResultIdentity:
        """Return stale-result identity for one diagnostics request."""

        return PromptAsyncResultIdentity(
            request_id=request_id,
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            source_length=len(source_text),
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
        )


def _diagnostic_at_source_position(
    diagnostics: tuple[PromptDiagnostic, ...],
    source_position: int,
) -> PromptDiagnostic | None:
    """Return the diagnostic containing one source position using half-open ranges."""

    for diagnostic in diagnostics:
        if diagnostic.source_start <= source_position < diagnostic.source_end:
            return diagnostic
    return None


def _visible_diagnostics_identity(
    diagnostics: tuple[PromptDiagnostic, ...],
) -> _VisibleDiagnosticsIdentity:
    """Return stable diagnostic display identity for surface change detection."""

    return tuple(
        (
            diagnostic.diagnostic_id,
            diagnostic.kind,
            diagnostic.source_start,
            diagnostic.source_end,
            diagnostic.message,
        )
        for diagnostic in diagnostics
    )


__all__ = [
    "PromptContextMenuAction",
    "PromptDiagnosticMenuActionEntry",
    "PromptDiagnosticMenuActionSnapshot",
    "PromptDiagnosticsFeatureController",
    "PromptDiagnosticsHost",
    "PromptDiagnosticsSignalHost",
    "PromptDiagnosticsSnapshot",
    "PromptDiagnosticsSurface",
]
