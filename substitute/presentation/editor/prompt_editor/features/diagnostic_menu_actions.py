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

"""Prepare prompt diagnostic context-menu actions for hot-path consumers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptSpellingSuggestionSet,
)
from substitute.application.prompt_editor.prompt_unsupported_scene_marker_diagnostic_provider import (
    UNSUPPORTED_SCENE_MARKER_MESSAGE,
)

from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from .wildcard_controller import PromptWildcardContextAction


@dataclass(frozen=True, slots=True)
class PromptContextMenuAction:
    """Describe one diagnostic context-menu action without binding to Qt."""

    label: str
    callback: Callable[[], None] | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class PromptDiagnosticMenuActionEntry:
    """Publish prepared context-menu actions for one diagnostic range."""

    identity: PromptFeatureSnapshotIdentity
    diagnostic_id: str
    diagnostic_kind: PromptDiagnosticKind
    source_start: int
    source_end: int
    actions: tuple[PromptContextMenuAction, ...]

    def __post_init__(self) -> None:
        """Reject invalid diagnostic action ranges before menu snapshots use them."""

        if not self.diagnostic_id.strip():
            raise ValueError("diagnostic_id must not be blank.")
        if self.source_start < 0:
            raise ValueError("source_start must be non-negative.")
        if self.source_end < self.source_start:
            raise ValueError("source_end must not precede source_start.")


@dataclass(frozen=True, slots=True)
class PromptDiagnosticMenuActionSnapshot:
    """Publish prepared diagnostic context-menu actions for one source position."""

    identity: PromptFeatureSnapshotIdentity
    source_position: int
    diagnostic_id: str | None
    source_range: tuple[int, int] | None
    actions: tuple[PromptContextMenuAction, ...]
    ready: bool
    stale: bool = False
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous diagnostic menu-action snapshot states."""

        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")
        if self.ready and self.unavailable_reason is not None:
            raise ValueError("ready snapshots must not be unavailable.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")


class PromptSpellingReplacementCallback(Protocol):
    """Describe spelling replacement callbacks bound by diagnostics ownership."""

    def __call__(
        self,
        diagnostic: PromptDiagnostic,
        replacement: str,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Replace one spelling diagnostic."""


class PromptDiagnosticCallback(Protocol):
    """Describe diagnostic callbacks bound by diagnostics ownership."""

    def __call__(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
    ) -> None:
        """Handle one prepared diagnostic action."""


class PromptWildcardActionSource(Protocol):
    """Describe wildcard diagnostic actions consumed by preparation."""

    def actions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
    ) -> tuple[PromptWildcardContextAction, ...]:
        """Return wildcard diagnostic actions."""


def prepare_diagnostic_menu_action_entries(
    *,
    diagnostics: tuple[PromptDiagnostic, ...],
    source_identity: PromptCommandSourceIdentity | None,
    base_identity: PromptFeatureSnapshotIdentity,
    spelling_suggestions: dict[str, PromptSpellingSuggestionSet],
    dictionary_add_supported: bool,
    wildcard_feature: PromptWildcardActionSource,
    replace_spelling_diagnostic: PromptSpellingReplacementCallback,
    ignore_spelling_diagnostic_for_session: PromptDiagnosticCallback,
    add_spelling_diagnostic_to_dictionary: PromptDiagnosticCallback,
    remove_duplicate_diagnostic: PromptDiagnosticCallback,
    emphasize_first_duplicate_diagnostic: PromptDiagnosticCallback,
    ignore_duplicate_diagnostic: PromptDiagnosticCallback,
) -> tuple[PromptDiagnosticMenuActionEntry, ...]:
    """Prepare diagnostic menu action entries outside context-menu opening."""

    return tuple(
        PromptDiagnosticMenuActionEntry(
            identity=_diagnostic_menu_action_identity(
                base_identity=base_identity,
                source_position=diagnostic.source_start,
                diagnostic_id=diagnostic.diagnostic_id,
                source_range=(diagnostic.source_start, diagnostic.source_end),
                stale=False,
                unavailable_reason=None,
            ),
            diagnostic_id=diagnostic.diagnostic_id,
            diagnostic_kind=diagnostic.kind,
            source_start=diagnostic.source_start,
            source_end=diagnostic.source_end,
            actions=_actions_for_diagnostic(
                diagnostic=diagnostic,
                source_identity=source_identity,
                spelling_suggestions=spelling_suggestions,
                dictionary_add_supported=dictionary_add_supported,
                wildcard_feature=wildcard_feature,
                replace_spelling_diagnostic=replace_spelling_diagnostic,
                ignore_spelling_diagnostic_for_session=(
                    ignore_spelling_diagnostic_for_session
                ),
                add_spelling_diagnostic_to_dictionary=(
                    add_spelling_diagnostic_to_dictionary
                ),
                remove_duplicate_diagnostic=remove_duplicate_diagnostic,
                emphasize_first_duplicate_diagnostic=(
                    emphasize_first_duplicate_diagnostic
                ),
                ignore_duplicate_diagnostic=ignore_duplicate_diagnostic,
            ),
        )
        for diagnostic in diagnostics
    )


def diagnostic_menu_action_snapshot_for_position(
    *,
    source_position: int,
    entries: tuple[PromptDiagnosticMenuActionEntry, ...],
    active_diagnostic_ids: frozenset[str],
    base_identity: PromptFeatureSnapshotIdentity,
    current_source_identity: PromptCommandSourceIdentity | None,
    unavailable_reason: str | None,
) -> PromptDiagnosticMenuActionSnapshot:
    """Return prepared diagnostic menu actions for one source position."""

    if source_position < 0:
        raise ValueError("source_position must be non-negative.")
    if current_source_identity is None:
        return _unavailable_menu_action_snapshot(
            source_position=source_position,
            base_identity=base_identity,
            unavailable_reason="source_revision_unavailable",
        )
    if base_identity.source_revision is None:
        return _unavailable_menu_action_snapshot(
            source_position=source_position,
            base_identity=base_identity,
            unavailable_reason="diagnostics_source_revision_unavailable",
        )
    if current_source_identity.source_revision != base_identity.source_revision:
        return _unavailable_menu_action_snapshot(
            source_position=source_position,
            base_identity=base_identity,
            unavailable_reason="stale_diagnostics_snapshot",
        )
    if base_identity.stale or unavailable_reason is not None:
        return _unavailable_menu_action_snapshot(
            source_position=source_position,
            base_identity=base_identity,
            unavailable_reason=unavailable_reason or "stale_snapshot",
        )
    entry = diagnostic_action_entry_at_source_position(
        tuple(
            entry for entry in entries if entry.diagnostic_id in active_diagnostic_ids
        ),
        source_position,
    )
    if entry is None:
        return PromptDiagnosticMenuActionSnapshot(
            identity=_diagnostic_menu_action_identity(
                base_identity=base_identity,
                source_position=source_position,
                diagnostic_id=None,
                source_range=None,
                stale=False,
                unavailable_reason=None,
            ),
            source_position=source_position,
            diagnostic_id=None,
            source_range=None,
            actions=(),
            ready=True,
        )
    return PromptDiagnosticMenuActionSnapshot(
        identity=entry.identity,
        source_position=source_position,
        diagnostic_id=entry.diagnostic_id,
        source_range=(entry.source_start, entry.source_end),
        actions=entry.actions,
        ready=True,
    )


def actions_for_prepared_diagnostic(
    *,
    diagnostic: PromptDiagnostic,
    source_identity: PromptCommandSourceIdentity | None,
    spelling_suggestions: dict[str, PromptSpellingSuggestionSet],
    dictionary_add_supported: bool,
    wildcard_feature: PromptWildcardActionSource,
    replace_spelling_diagnostic: PromptSpellingReplacementCallback,
    ignore_spelling_diagnostic_for_session: PromptDiagnosticCallback,
    add_spelling_diagnostic_to_dictionary: PromptDiagnosticCallback,
    remove_duplicate_diagnostic: PromptDiagnosticCallback,
    emphasize_first_duplicate_diagnostic: PromptDiagnosticCallback,
    ignore_duplicate_diagnostic: PromptDiagnosticCallback,
) -> tuple[PromptContextMenuAction, ...]:
    """Return diagnostic actions for compatibility callers."""

    return _actions_for_diagnostic(
        diagnostic=diagnostic,
        source_identity=source_identity,
        spelling_suggestions=spelling_suggestions,
        dictionary_add_supported=dictionary_add_supported,
        wildcard_feature=wildcard_feature,
        replace_spelling_diagnostic=replace_spelling_diagnostic,
        ignore_spelling_diagnostic_for_session=ignore_spelling_diagnostic_for_session,
        add_spelling_diagnostic_to_dictionary=add_spelling_diagnostic_to_dictionary,
        remove_duplicate_diagnostic=remove_duplicate_diagnostic,
        emphasize_first_duplicate_diagnostic=emphasize_first_duplicate_diagnostic,
        ignore_duplicate_diagnostic=ignore_duplicate_diagnostic,
    )


def diagnostic_action_entry_at_source_position(
    entries: tuple[PromptDiagnosticMenuActionEntry, ...],
    source_position: int,
) -> PromptDiagnosticMenuActionEntry | None:
    """Return the prepared action entry containing one source position."""

    for entry in entries:
        if entry.source_start <= source_position < entry.source_end:
            return entry
    return None


def _actions_for_diagnostic(
    *,
    diagnostic: PromptDiagnostic,
    source_identity: PromptCommandSourceIdentity | None,
    spelling_suggestions: dict[str, PromptSpellingSuggestionSet],
    dictionary_add_supported: bool,
    wildcard_feature: PromptWildcardActionSource,
    replace_spelling_diagnostic: PromptSpellingReplacementCallback,
    ignore_spelling_diagnostic_for_session: PromptDiagnosticCallback,
    add_spelling_diagnostic_to_dictionary: PromptDiagnosticCallback,
    remove_duplicate_diagnostic: PromptDiagnosticCallback,
    emphasize_first_duplicate_diagnostic: PromptDiagnosticCallback,
    ignore_duplicate_diagnostic: PromptDiagnosticCallback,
) -> tuple[PromptContextMenuAction, ...]:
    """Return prepared menu actions for one diagnostic."""

    if diagnostic.kind is PromptDiagnosticKind.SPELLING:
        return _spelling_actions(
            diagnostic=diagnostic,
            source_identity=source_identity,
            spelling_suggestions=spelling_suggestions,
            dictionary_add_supported=dictionary_add_supported,
            replace_spelling_diagnostic=replace_spelling_diagnostic,
            ignore_spelling_diagnostic_for_session=(
                ignore_spelling_diagnostic_for_session
            ),
            add_spelling_diagnostic_to_dictionary=(
                add_spelling_diagnostic_to_dictionary
            ),
        )
    if diagnostic.kind is PromptDiagnosticKind.DUPLICATE_SEGMENT:
        return _duplicate_segment_actions(
            diagnostic=diagnostic,
            source_identity=source_identity,
            remove_duplicate_diagnostic=remove_duplicate_diagnostic,
            emphasize_first_duplicate_diagnostic=emphasize_first_duplicate_diagnostic,
            ignore_duplicate_diagnostic=ignore_duplicate_diagnostic,
        )
    if diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER:
        return actions_for_unsupported_scene_marker_diagnostic(diagnostic)
    if diagnostic.kind is PromptDiagnosticKind.WILDCARD:
        return _wildcard_actions(
            diagnostic=diagnostic, wildcard_feature=wildcard_feature
        )
    return ()


def actions_for_unsupported_scene_marker_diagnostic(
    diagnostic: PromptDiagnostic,
) -> tuple[PromptContextMenuAction, ...]:
    """Return the non-mutating explanation for one rejected scene marker."""

    if diagnostic.kind is not PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER:
        return ()
    return (
        PromptContextMenuAction(
            label=UNSUPPORTED_SCENE_MARKER_MESSAGE,
            callback=None,
            enabled=False,
        ),
    )


def _spelling_actions(
    *,
    diagnostic: PromptDiagnostic,
    source_identity: PromptCommandSourceIdentity | None,
    spelling_suggestions: dict[str, PromptSpellingSuggestionSet],
    dictionary_add_supported: bool,
    replace_spelling_diagnostic: PromptSpellingReplacementCallback,
    ignore_spelling_diagnostic_for_session: PromptDiagnosticCallback,
    add_spelling_diagnostic_to_dictionary: PromptDiagnosticCallback,
) -> tuple[PromptContextMenuAction, ...]:
    """Return spelling suggestion and dictionary actions."""

    suggestions = spelling_suggestions.get(diagnostic.diagnostic_id)
    actions: list[PromptContextMenuAction] = []
    if suggestions is not None and suggestions.suggestions:

        def replacement_callback(replacement_text: str) -> Callable[[], None]:
            """Return a callback that applies one prepared spelling replacement."""

            def replace_spelling() -> None:
                """Apply the prepared spelling replacement."""

                replace_spelling_diagnostic(
                    diagnostic,
                    replacement_text,
                    source_identity=source_identity,
                )

            return replace_spelling

        for suggestion in suggestions.suggestions[:8]:
            replacement = suggestion
            actions.append(
                PromptContextMenuAction(
                    label=replacement,
                    callback=replacement_callback(replacement),
                )
            )
    else:
        actions.append(
            PromptContextMenuAction(
                label="No spelling suggestions",
                callback=None,
                enabled=False,
            )
        )
    actions.append(
        PromptContextMenuAction(
            label="Ignore spelling",
            callback=lambda: ignore_spelling_diagnostic_for_session(
                diagnostic,
                source_identity=source_identity,
            ),
        )
    )
    if dictionary_add_supported:
        actions.append(
            PromptContextMenuAction(
                label="Add to dictionary",
                callback=lambda: add_spelling_diagnostic_to_dictionary(
                    diagnostic,
                    source_identity=source_identity,
                ),
            )
        )
    return tuple(actions)


def _duplicate_segment_actions(
    *,
    diagnostic: PromptDiagnostic,
    source_identity: PromptCommandSourceIdentity | None,
    remove_duplicate_diagnostic: PromptDiagnosticCallback,
    emphasize_first_duplicate_diagnostic: PromptDiagnosticCallback,
    ignore_duplicate_diagnostic: PromptDiagnosticCallback,
) -> tuple[PromptContextMenuAction, ...]:
    """Return duplicate-segment cleanup actions."""

    return (
        PromptContextMenuAction(
            label="Remove duplicate",
            callback=lambda: remove_duplicate_diagnostic(
                diagnostic,
                source_identity=source_identity,
            ),
        ),
        PromptContextMenuAction(
            label="Emphasize first",
            callback=lambda: emphasize_first_duplicate_diagnostic(
                diagnostic,
                source_identity=source_identity,
            ),
        ),
        PromptContextMenuAction(
            label="Ignore duplicate",
            callback=lambda: ignore_duplicate_diagnostic(
                diagnostic,
                source_identity=source_identity,
            ),
        ),
    )


def _wildcard_actions(
    *,
    diagnostic: PromptDiagnostic,
    wildcard_feature: PromptWildcardActionSource,
) -> tuple[PromptContextMenuAction, ...]:
    """Return a non-mutating explainer for missing wildcard diagnostics."""

    return tuple(
        PromptContextMenuAction(
            label=action.label,
            callback=None,
            enabled=action.callback_ready,
        )
        for action in wildcard_feature.actions_for_diagnostic(diagnostic)
    )


def _unavailable_menu_action_snapshot(
    *,
    source_position: int,
    base_identity: PromptFeatureSnapshotIdentity,
    unavailable_reason: str,
) -> PromptDiagnosticMenuActionSnapshot:
    """Return an explicit unavailable diagnostic menu-action snapshot."""

    return PromptDiagnosticMenuActionSnapshot(
        identity=_diagnostic_menu_action_identity(
            base_identity=base_identity,
            source_position=source_position,
            diagnostic_id=None,
            source_range=None,
            stale=True,
            unavailable_reason=unavailable_reason,
        ),
        source_position=source_position,
        diagnostic_id=None,
        source_range=None,
        actions=(),
        ready=False,
        stale=True,
        unavailable_reason=unavailable_reason,
    )


def _diagnostic_menu_action_identity(
    *,
    base_identity: PromptFeatureSnapshotIdentity,
    source_position: int,
    diagnostic_id: str | None,
    source_range: tuple[int, int] | None,
    stale: bool,
    unavailable_reason: str | None,
) -> PromptFeatureSnapshotIdentity:
    """Return freshness identity for prepared diagnostic menu actions."""

    return PromptFeatureSnapshotIdentity(
        source_revision=base_identity.source_revision,
        feature_profile_id=base_identity.feature_profile_id,
        stale=stale,
        query_identity=(
            "diagnostic_menu_actions",
            source_position,
            diagnostic_id,
            source_range,
            unavailable_reason,
        ),
    )


__all__ = [
    "PromptContextMenuAction",
    "PromptDiagnosticMenuActionEntry",
    "PromptDiagnosticMenuActionSnapshot",
    "actions_for_unsupported_scene_marker_diagnostic",
    "actions_for_prepared_diagnostic",
    "diagnostic_action_entry_at_source_position",
    "diagnostic_menu_action_snapshot_for_position",
    "prepare_diagnostic_menu_action_entries",
]
