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

"""Own pure autocomplete query construction for prompt-editor features."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    PromptDocumentService,
    PromptDocumentView,
    PromptEditorFeature,
    PromptLoraAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.autocomplete_refresh_intent import (
    PromptAutocompleteRefreshIntent,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptFeatureSnapshotIdentity,
)
from substitute.presentation.editor.prompt_editor.features.feature_profile_controller import (
    PromptFeatureGateSnapshot,
    PromptFeatureProfileController,
)


class PromptAutocompleteQuerySourceSnapshot(Protocol):
    """Describe prepared source state consumed by autocomplete query construction."""

    @property
    def source_revision(self) -> int:
        """Return the source revision used to reject stale query results."""
        ...

    @property
    def source_length(self) -> int:
        """Return the source length used to reject stale query results."""
        ...

    @property
    def source_text(self) -> str:
        """Return the prepared source text for query construction."""
        ...

    @property
    def cursor_position(self) -> int:
        """Return the source cursor position for query construction."""
        ...

    @property
    def has_selection(self) -> bool:
        """Return whether the source snapshot had an active selection."""
        ...

    @property
    def source_identity(self) -> object | None:
        """Return the opaque source identity carried to stale-result consumers."""
        ...

    @property
    def document_view(self) -> PromptDocumentView:
        """Return the prepared document view for tag query construction."""
        ...

    @property
    def feature_profile_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the feature-profile identity for query-state freshness."""
        ...

    @property
    def refresh_intent(self) -> PromptAutocompleteRefreshIntent:
        """Return whether this snapshot may create an active autocomplete session."""
        ...


@dataclass(frozen=True, slots=True)
class PromptAutocompleteQueryState:
    """Carry source-safe identity for one autocomplete query refresh."""

    source_revision: int
    source_length: int
    source_text: str
    cursor_position: int
    has_selection: bool
    source_identity: object | None = None
    feature_profile_identity: PromptFeatureSnapshotIdentity | None = None
    refresh_intent: PromptAutocompleteRefreshIntent = "programmatic"
    query_identity: Hashable | None = None
    tag_query: PromptAutocompleteQuery | None = None
    lora_query: PromptLoraAutocompleteQuery | None = None
    wildcard_query: PromptWildcardAutocompleteQuery | None = None
    scene_query: PromptSceneAutocompleteQuery | None = None


class PromptAutocompleteQueryController:
    """Build typed autocomplete queries from prepared source snapshots."""

    def __init__(
        self,
        *,
        document_service: PromptDocumentService,
        feature_profile: PromptFeatureProfileController,
        minimum_prefix_length: int,
    ) -> None:
        """Store pure query collaborators without owning widgets or results."""

        self._document_service = document_service
        self._feature_snapshot: PromptFeatureGateSnapshot = feature_profile.snapshot
        self._minimum_prefix_length = minimum_prefix_length

    def query_state_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteQuerySourceSnapshot,
    ) -> PromptAutocompleteQueryState:
        """Return the first applicable query for one prepared source snapshot."""

        prompt_text = snapshot.source_text
        if self._feature_snapshot.supports(PromptEditorFeature.LORA_AUTOCOMPLETE):
            lora_query = self._document_service.lora_autocomplete_query_at_cursor(
                text=prompt_text,
                cursor_position=snapshot.cursor_position,
                has_selection=snapshot.has_selection,
            )
            if lora_query is not None:
                return self._query_state(
                    snapshot,
                    query_identity=("lora", lora_query.query_text),
                    lora_query=lora_query,
                )

        if self._feature_snapshot.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE):
            wildcard_query = (
                self._document_service.wildcard_autocomplete_query_at_cursor(
                    text=prompt_text,
                    cursor_position=snapshot.cursor_position,
                    has_selection=snapshot.has_selection,
                )
            )
            if wildcard_query is not None:
                return self._query_state(
                    snapshot,
                    query_identity=("wildcard", wildcard_query.prefix),
                    wildcard_query=wildcard_query,
                )

        scene_query = self._document_service.scene_autocomplete_query_at_cursor(
            text=prompt_text,
            cursor_position=snapshot.cursor_position,
            has_selection=snapshot.has_selection,
        )
        if scene_query is not None:
            return self._query_state(
                snapshot,
                query_identity=("scene", scene_query.prefix),
                scene_query=scene_query,
            )

        tag_query = self._document_service.autocomplete_query_at_cursor(
            snapshot.document_view,
            text=prompt_text,
            cursor_position=snapshot.cursor_position,
            has_selection=snapshot.has_selection,
            minimum_prefix_length=self._minimum_prefix_length,
        )
        query_identity: Hashable | None = None
        if tag_query is not None:
            query_identity = (
                "tag",
                tag_query.prefix,
                tag_query.word_start,
                tag_query.word_end,
                tag_query.active_tag_end,
            )
        return self._query_state(
            snapshot,
            query_identity=query_identity,
            tag_query=tag_query,
        )

    @staticmethod
    def _query_state(
        snapshot: PromptAutocompleteQuerySourceSnapshot,
        *,
        query_identity: Hashable | None,
        tag_query: PromptAutocompleteQuery | None = None,
        lora_query: PromptLoraAutocompleteQuery | None = None,
        wildcard_query: PromptWildcardAutocompleteQuery | None = None,
        scene_query: PromptSceneAutocompleteQuery | None = None,
    ) -> PromptAutocompleteQueryState:
        """Return a query state carrying the source snapshot identity."""

        return PromptAutocompleteQueryState(
            source_revision=snapshot.source_revision,
            source_length=snapshot.source_length,
            source_text=snapshot.source_text,
            cursor_position=snapshot.cursor_position,
            has_selection=snapshot.has_selection,
            source_identity=snapshot.source_identity,
            feature_profile_identity=snapshot.feature_profile_identity,
            refresh_intent=snapshot.refresh_intent,
            query_identity=query_identity,
            tag_query=tag_query,
            lora_query=lora_query,
            wildcard_query=wildcard_query,
            scene_query=scene_query,
        )


__all__ = [
    "PromptAutocompleteQueryController",
    "PromptAutocompleteQuerySourceSnapshot",
    "PromptAutocompleteQueryState",
]
