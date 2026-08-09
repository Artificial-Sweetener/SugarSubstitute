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

"""Own prepared diagnostics presentation, menu actions, and commands."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.application.prompt_editor.diagnostics.display_policy import (
    PromptDiagnosticDisplayPolicy,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSnapshot as ApplicationPromptDiagnosticSnapshot,
    PromptSpellingDiagnosticPayload,
)
from substitute.application.prompt_editor.diagnostics.spellcheck_models import (
    PromptSpellingSuggestionSet,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
    record_prompt_editor_work_count,
)

from ..commands.diagnostic_commands import (
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptDuplicateEmphasisDiagnosticAction,
    PromptDuplicateIgnoreDiagnosticAction,
    PromptDuplicateRemovalDiagnosticAction,
    PromptSpellingDictionaryAddDiagnosticAction,
    PromptSpellingIgnoreDiagnosticAction,
    PromptSpellingReplacementDiagnosticAction,
)
from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from .diagnostic_menu_actions import (
    PromptContextMenuAction,
    PromptDiagnosticMenuActionEntry,
    PromptDiagnosticMenuActionSnapshot,
    actions_for_prepared_diagnostic,
    diagnostic_menu_action_snapshot_for_position,
    prepare_diagnostic_menu_action_entries,
)
from .diagnostics_provider_lifecycle import PromptDiagnosticsProviderLifecycle
from .diagnostic_menu_actions import PromptWildcardActionSource

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
    """Describe editor commands and reads used by diagnostics presentation."""

    def toPlainText(self) -> str:
        """Return the current prompt source text."""

    def textCursor(self) -> PromptDiagnosticsCursor:
        """Return a source-backed cursor for visibility policy."""

    def setFocus(self) -> None:
        """Focus the prompt editor after accepted diagnostic actions."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return the source identity for prepared diagnostic commands."""

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


class PromptDiagnosticsRefreshRequester(Protocol):
    """Describe the narrow refresh command needed after accepted actions."""

    def refresh_now(self) -> None:
        """Request a current diagnostics refresh."""


@dataclass(frozen=True, slots=True)
class PromptDiagnosticsSnapshot:
    """Publish prepared diagnostic state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    diagnostics: tuple[PromptDiagnostic, ...]
    visible_diagnostics: tuple[PromptDiagnostic, ...]
    action_ready: bool
    active_word_policy: str
    unavailable_reason: str | None = None


class PromptDiagnosticsPresentation:
    """Own diagnostics display state, prepared menu data, and action commands."""

    def __init__(
        self,
        *,
        host: PromptDiagnosticsHost,
        surface: PromptDiagnosticsSurface,
        providers: PromptDiagnosticsProviderLifecycle,
        wildcard_feature: PromptWildcardActionSource,
        feature_profile_id: Hashable | None,
        refresh_requester: PromptDiagnosticsRefreshRequester,
        display_policy: PromptDiagnosticDisplayPolicy | None = None,
    ) -> None:
        """Store bounded diagnostics presentation collaborators."""

        self._host = host
        self._surface = surface
        self._providers = providers
        self._wildcard_feature = wildcard_feature
        self._feature_profile_id = feature_profile_id
        self._refresh_requester = refresh_requester
        self._display_policy = display_policy or PromptDiagnosticDisplayPolicy()
        self._snapshot: ApplicationPromptDiagnosticSnapshot | None = None
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

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return the latest prepared diagnostics snapshot."""

        return self._published_snapshot

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
        if snapshot is None or snapshot.source_text != self._host.toPlainText():
            return None
        return _diagnostic_at_source_position(
            self._active_diagnostics(snapshot),
            source_position,
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTICS_ACTION_PREPARE)
    def actions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic | None,
    ) -> tuple[PromptContextMenuAction, ...]:
        """Return context-menu actions for the supplied diagnostic."""

        if diagnostic is None:
            return ()
        return actions_for_prepared_diagnostic(
            diagnostic=diagnostic,
            source_identity=self.source_identity_for_diagnostic_action(),
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
    ) -> PromptSourceIdentity | None:
        """Return the source identity for menu-built diagnostic actions."""

        return self._host.prompt_command_source_identity()

    def replace_spelling_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        replacement: str,
        *,
        source_identity: PromptSourceIdentity | None = None,
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
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Ignore one spelling diagnostic word for the current session."""

        provider = self._providers.spellcheck_provider
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
        self._refresh_requester.refresh_now()

    def add_spelling_diagnostic_to_dictionary(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Persist one spelling diagnostic word when supported by the backend."""

        provider = self._providers.spellcheck_provider
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
            self._refresh_requester.refresh_now()

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""

        provider = self._providers.spellcheck_provider
        return False if provider is None else provider.dictionary_add_supported()

    def remove_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
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
        source_identity: PromptSourceIdentity | None = None,
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
        source_identity: PromptSourceIdentity | None = None,
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
        """Clear current diagnostics presentation state."""

        self._snapshot = None
        self._visible_diagnostics = ()
        self._prepared_spelling_suggestions.clear()
        self._prepared_menu_action_entries = ()
        self._set_visible_diagnostics(())
        self._publish_snapshot(stale=False)

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTICS_VISIBLE_REFRESH)
    def refresh_visible_diagnostics(self) -> None:
        """Refresh painted diagnostics from cached state without backend work."""

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
        self._visible_diagnostics = self._display_policy.visible_diagnostics(
            snapshot=visible_snapshot,
            cursor_position=self._host.textCursor().position(),
        )
        self._set_visible_diagnostics(self._visible_diagnostics)
        self._publish_snapshot(stale=False)

    def publish_diagnostics_result(
        self,
        snapshot: ApplicationPromptDiagnosticSnapshot,
    ) -> None:
        """Publish one freshness-validated result for diagnostics consumers."""

        self._snapshot = snapshot
        self._prepare_context_action_state(
            snapshot,
            source_identity=self._host.prompt_command_source_identity(),
        )
        self.refresh_visible_diagnostics()

    def publish_empty_diagnostics(self, source_text: str) -> None:
        """Publish the current empty-source diagnostics transition."""

        self._snapshot = ApplicationPromptDiagnosticSnapshot(
            source_text=source_text,
            diagnostics=(),
        )
        self._visible_diagnostics = ()
        self._prepared_spelling_suggestions.clear()
        self._prepared_menu_action_entries = ()
        self._set_visible_diagnostics(())
        self._publish_snapshot(stale=False)

    def publish_diagnostics_failure(self, error: BaseException) -> None:
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

    def _set_visible_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Push visible diagnostics only when their material identity changes."""

        next_identity = _visible_diagnostics_identity(diagnostics)
        if next_identity == self._visible_diagnostics_identity:
            return
        self._visible_diagnostics_identity = next_identity
        record_prompt_editor_work_count(
            PromptEditorWorkEvent.DIAGNOSTICS_VISIBLE_PUBLISH
        )
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
        source_identity: PromptSourceIdentity | None,
    ) -> PromptSourceIdentity | None:
        """Return the supplied or current source identity for an action."""

        return source_identity or self._host.prompt_command_source_identity()

    def _prepare_context_action_state(
        self,
        snapshot: ApplicationPromptDiagnosticSnapshot,
        *,
        source_identity: PromptSourceIdentity | None,
    ) -> None:
        """Prepare diagnostic menu data outside context-menu opening."""

        self._prepared_spelling_suggestions.clear()
        provider = self._providers.spellcheck_provider
        active_diagnostics = self._active_diagnostics(snapshot)
        if provider is not None:
            for diagnostic in active_diagnostics:
                if diagnostic.kind is not PromptDiagnosticKind.SPELLING:
                    continue
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
                diagnostics=active_diagnostics,
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
        return PromptFeatureSnapshotIdentity(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            feature_profile_id=self._feature_profile_id,
            stale=stale,
            query_identity=(
                "document_semantics",
                self._providers.document_semantics_identity,
                "conditioning_context",
                self._providers.conditioning_context_identity,
            ),
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
    "PromptDiagnosticsCursor",
    "PromptDiagnosticsHost",
    "PromptDiagnosticsPresentation",
    "PromptDiagnosticsRefreshRequester",
    "PromptDiagnosticsSnapshot",
    "PromptDiagnosticsSurface",
]
