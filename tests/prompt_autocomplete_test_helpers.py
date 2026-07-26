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

"""Provide deterministic prompt autocomplete gateway doubles for tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.ports import (
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.devtools.prompt_editor_performance.syntax_profile import (
    prompt_syntax_profile as prompt_syntax_profile,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptScheduledLoraContextProvider,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryResultLifecycle,
    PromptAutocompleteQueryState,
    PromptAutocompleteLoraCatalogSnapshotProvider,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteWildcardResultProvider,
    PromptFeatureProfileController,
    PromptSceneContextPublication,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
)
from substitute.presentation.editor.prompt_editor.commands.autocomplete_commands import (
    PromptAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance import (
    PromptAutocompleteAcceptanceController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance_lifecycle import (
    PromptAutocompleteAcceptanceLifecycle,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller import (
    PromptAutocompleteInputAdapter,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session_publication import (
    PromptAutocompleteSessionPublication,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePresenter,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
)


class EmptyPromptAutocompleteGateway:
    """Return no prompt autocomplete suggestions."""

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return an empty suggestion set for every lookup."""

        _ = (prefix, limit)
        return ()


class RecordingPromptAutocompleteGateway:
    """Return configured suggestions while recording each lookup request."""

    def __init__(
        self,
        results_by_prefix: Mapping[str, tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Store deterministic lookup results for each tested prefix."""

        self._results_by_prefix = dict(results_by_prefix)
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Record one search and return the configured suggestion tuple."""

        self.calls.append((prefix, limit))
        return self._results_by_prefix.get(prefix, ())


class EmptyPromptWildcardCatalogGateway:
    """Return unresolved wildcard metadata for every prompt snapshot."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard file suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return unresolved metadata aligned with the supplied reference order."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


@dataclass(slots=True)
class PromptAutocompleteTestStack:
    """Expose the real autocomplete owners assembled for focused integration tests."""

    input_adapter: PromptAutocompleteInputAdapter
    query_result_lifecycle: PromptAutocompleteQueryResultLifecycle
    session_controller: PromptAutocompleteSessionController


def build_autocomplete_query_state(
    *,
    source_text: str = "",
    source_identity: object | None = None,
    tag_query: PromptAutocompleteQuery | None = None,
    wildcard_query: PromptWildcardAutocompleteQuery | None = None,
    scene_query: PromptSceneAutocompleteQuery | None = None,
    lora_query: PromptLoraAutocompleteQuery | None = None,
) -> PromptAutocompleteQueryState:
    """Build immutable test input for the real query/result lifecycle."""

    return PromptAutocompleteQueryState(
        source_revision=getattr(source_identity, "source_revision", 0),
        source_length=len(source_text),
        source_text=source_text,
        cursor_position=len(source_text),
        has_selection=False,
        source_identity=source_identity,
        tag_query=tag_query,
        wildcard_query=wildcard_query,
        scene_query=scene_query,
        lora_query=lora_query,
    )


class PromptAutocompleteTimingTestDouble:
    """Provide an inert timing boundary for interaction tests outside autocomplete."""

    def __init__(self, *, on_clear: Callable[[], None] | None = None) -> None:
        """Store optional lifecycle clearing behavior required by one interaction test."""

        self._on_clear = on_clear

    def clear_for_non_text_interaction(self) -> None:
        """Ignore interaction resets unrelated to the current assertion."""

        if self._on_clear is not None:
            self._on_clear()

    def cancel_pending_caret_refresh(self) -> None:
        """Ignore timer cancellation unrelated to the current assertion."""

    def handle_post_key_press(self, _event: object) -> None:
        """Ignore post-key timing outside autocomplete-focused tests."""

    def suppress_for_mouse_navigation(self) -> None:
        """Ignore mouse-navigation suppression outside autocomplete tests."""

    def handle_focus_out(self) -> None:
        """Ignore focus teardown outside autocomplete-focused tests."""

    def handle_hide(self) -> None:
        """Ignore hide teardown outside autocomplete-focused tests."""


def build_test_autocomplete_stack(
    editor: object,
    *,
    prompt_autocomplete_gateway: object | None = None,
    limit: int = 10,
    scene_publication: PromptSceneContextPublication | None = None,
    wildcard_feature: PromptAutocompleteWildcardResultProvider | None = None,
    prompt_lora_catalog_service: (
        PromptAutocompleteLoraCatalogSnapshotProvider | None
    ) = None,
    scheduled_lora_context_provider: (PromptScheduledLoraContextProvider | None) = None,
    autocomplete_presenter: PromptAutocompletePresenter | None = None,
    autocomplete_ghost_text_publisher: PromptAutocompleteGhostTextPublisher
    | None = None,
    autocomplete_session_controller: PromptAutocompleteSessionController | None = None,
    autocomplete_ghost_text_enabled: bool = True,
    lora_autocomplete_enabled: bool = True,
    trigger_word_suggestions_enabled: bool = True,
    lora_thumbnail_cache_available: bool = False,
) -> PromptAutocompleteTestStack:
    """Build real session, lifecycle, and input owners for focused autocomplete tests."""

    scheduled_lora_context = PromptAutocompleteScheduledLoraContextController(
        context_provider=scheduled_lora_context_provider,
        enabled=trigger_word_suggestions_enabled,
    )
    result_controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=(
            cast(Any, prompt_autocomplete_gateway)
            if prompt_autocomplete_gateway is not None
            else EmptyPromptAutocompleteGateway()
        ),
        limit=limit,
        scene_autocomplete_state=(
            None
            if scene_publication is None
            else lambda: scene_publication.snapshot.autocomplete
        ),
        wildcard_feature=wildcard_feature,
        prompt_lora_catalog_service=prompt_lora_catalog_service,
        trigger_word_provider=scheduled_lora_context,
    )
    session_controller = (
        autocomplete_session_controller
        if autocomplete_session_controller is not None
        else PromptAutocompleteSessionController()
    )
    session_publication = PromptAutocompleteSessionPublication(
        sessions=session_controller,
        presenter=autocomplete_presenter,
        ghost_text_publisher=autocomplete_ghost_text_publisher,
        ghost_text_enabled=autocomplete_ghost_text_enabled,
    )

    def current_source_identity() -> PromptSourceIdentity | None:
        """Read source identity when the focused double exposes that query."""

        source_identity = getattr(editor, "prompt_command_source_identity", None)
        return (
            cast(PromptSourceIdentity | None, source_identity())
            if callable(source_identity)
            else None
        )

    def execute_acceptance(
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Execute acceptance when the focused double exercises that path."""

        execute = getattr(editor, "execute_autocomplete_acceptance", None)
        if callable(execute):
            return cast(PromptCommandResult[object], execute(acceptance))
        return PromptCommandResult.completed("accept_autocomplete")

    def complete_lora_replacement() -> None:
        """Complete LoRA replacement when the focused double exposes that path."""

        complete = getattr(editor, "commit_lora_autocomplete_replacement", None)
        if callable(complete):
            complete()

    coordinator = PromptAutocompleteInputAdapter(
        cast(Any, editor),
        restore_focus=lambda: cast(Any, editor).setFocus(),
        acceptance_lifecycle=PromptAutocompleteAcceptanceLifecycle(
            acceptance_controller=PromptAutocompleteAcceptanceController(
                cursor_position=lambda: cast(Any, editor).textCursor().position(),
                current_source_identity=current_source_identity,
                execute_acceptance=execute_acceptance,
                complete_lora_replacement=complete_lora_replacement,
            ),
            session_publication=session_publication,
        ),
        session_publication=session_publication,
    )
    lifecycle = PromptAutocompleteQueryResultLifecycle(
        query_controller=PromptAutocompleteQueryController(
            document_service=PromptDocumentService(),
            feature_profile=PromptFeatureProfileController.from_legacy_syntax(None),
            minimum_prefix_length=2,
        ),
        result_controller=result_controller,
        scene_context_controller=PromptAutocompleteSceneContextController(
            scene_context_identity=(
                None
                if scene_publication is None
                else lambda: scene_publication.scene_context_identity
            ),
        ),
        publication=session_publication,
        current_source_identity=lambda: getattr(
            editor,
            "prompt_command_source_identity",
            lambda: None,
        )(),
        lora_autocomplete_enabled=lambda: lora_autocomplete_enabled,
        lora_thumbnail_cache_available=lambda: lora_thumbnail_cache_available,
    )
    scheduled_lora_context.bind_current_context(lifecycle)
    return PromptAutocompleteTestStack(
        input_adapter=coordinator,
        query_result_lifecycle=lifecycle,
        session_controller=session_controller,
    )
