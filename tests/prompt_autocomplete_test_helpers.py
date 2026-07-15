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

from collections.abc import Hashable, Mapping
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
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteLoraCatalogSnapshotProvider,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteSceneContextProvider,
    PromptAutocompleteSceneResultProvider,
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteScheduledLoraCurrentContext,
    PromptAutocompleteWildcardResultProvider,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance import (
    PromptAutocompleteAcceptanceController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller import (
    PromptAutocompleteCoordinator,
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


class _AutocompleteCurrentContextBridge:
    """Bind scheduled-LoRA context to a test autocomplete coordinator."""

    def __init__(self) -> None:
        """Initialize an unbound current-context bridge."""

        self._current_context: PromptAutocompleteScheduledLoraCurrentContext | None = (
            None
        )

    def bind(
        self,
        current_context: PromptAutocompleteScheduledLoraCurrentContext,
    ) -> None:
        """Attach the live autocomplete current-context provider."""

        self._current_context = current_context

    def current_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the bound autocomplete source identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_source_identity()

    def current_query_identity(self) -> Hashable | None:
        """Return the bound autocomplete query identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_query_identity()

    def refresh_current_query(self) -> None:
        """Refresh the bound autocomplete query when available."""

        if self._current_context is not None:
            self._current_context.refresh_current_query()


def build_test_autocomplete_coordinator(
    editor: object,
    *,
    prompt_autocomplete_gateway: object | None = None,
    limit: int = 10,
    scene_feature: PromptAutocompleteSceneResultProvider
    | PromptAutocompleteSceneContextProvider
    | None = None,
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
) -> PromptAutocompleteCoordinator:
    """Build a coordinator with explicit Phase 27 owner wiring for tests."""

    current_context = _AutocompleteCurrentContextBridge()
    scheduled_lora_context = PromptAutocompleteScheduledLoraContextController(
        context_provider=scheduled_lora_context_provider,
        current_context=current_context,
        enabled=trigger_word_suggestions_enabled,
    )
    result_controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=(
            cast(Any, prompt_autocomplete_gateway)
            if prompt_autocomplete_gateway is not None
            else EmptyPromptAutocompleteGateway()
        ),
        limit=limit,
        scene_feature=cast(PromptAutocompleteSceneResultProvider | None, scene_feature),
        wildcard_feature=wildcard_feature,
        prompt_lora_catalog_service=prompt_lora_catalog_service,
        trigger_word_provider=scheduled_lora_context,
    )
    coordinator = PromptAutocompleteCoordinator(
        cast(Any, editor),
        autocomplete_result_controller=result_controller,
        autocomplete_scene_context_controller=PromptAutocompleteSceneContextController(
            scene_context_provider=cast(
                PromptAutocompleteSceneContextProvider | None,
                scene_feature,
            ),
        ),
        autocomplete_scheduled_lora_context_controller=scheduled_lora_context,
        autocomplete_presenter=autocomplete_presenter,
        autocomplete_ghost_text_publisher=autocomplete_ghost_text_publisher,
        autocomplete_ghost_text_enabled=autocomplete_ghost_text_enabled,
        autocomplete_acceptance_controller=PromptAutocompleteAcceptanceController(
            editor=cast(Any, editor),
        ),
        autocomplete_session_controller=(
            autocomplete_session_controller
            if autocomplete_session_controller is not None
            else PromptAutocompleteSessionController()
        ),
        lora_autocomplete_enabled=lora_autocomplete_enabled,
        lora_thumbnail_cache_available=lora_thumbnail_cache_available,
    )
    current_context.bind(coordinator)
    return coordinator
